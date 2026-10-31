"""
CliniXAI Multi-Model Medical AI — Core Training Service.

Responsibilities
----------------
1. Build tf.data pipelines for train / validation / test splits.
2. Apply ResNet50-compatible preprocessing and training-time augmentation.
3. Run Stage 1 training: frozen backbone, head only (transfer learning).
4. Run Stage 2 training: upper-backbone fine-tuning at low LR.
5. Evaluate the best checkpoint against the held-out test split.
6. Persist training history, evaluation metrics, classification report, and
   confusion matrix.

Constraints
-----------
- Testing split is NEVER used during training or hyperparameter tuning.
- Validation split is carved from Training data (20 % by default) when a
  dedicated "val" directory is absent.
- Pre-trained ImageNet weights are always used for the backbone.
- All randomness is seeded for reproducibility.
"""

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

log = logging.getLogger("trainer")

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_training(
    mod_config: Any,
    class_names: List[str],
    validation_split: float = 0.20,
    initial_epochs: int = 20,
    fine_tune_epochs: int = 20,
    batch_size: int = 32,
    initial_lr: float = 1e-3,
    fine_tune_lr: float = 1e-5,
    fine_tune_at_layer: int = 143,
    dropout_rate: float = 0.3,
    early_stopping_patience: int = 7,
    reduce_lr_patience: int = 3,
    reduce_lr_factor: float = 0.3,
    reduce_lr_min_lr: float = 1e-7,
    random_seed: int = 42,
) -> Dict[str, Any]:
    """
    Execute the full two-stage training pipeline for one medical AI module.

    Stage 1 — Transfer Learning (frozen backbone)
        Train only the classification head for `initial_epochs`.

    Stage 2 — Fine-Tuning (upper backbone unfrozen)
        Unfreeze backbone layers from `fine_tune_at_layer` onward and
        continue training for up to `fine_tune_epochs` more epochs at a
        very low learning rate.

    The held-out Testing split is evaluated ONCE after training is done.

    Returns
    -------
    dict with keys: history, evaluation, class_names, model_path, ...
    """
    import tensorflow as tf

    _seed_everything(random_seed, tf)

    # ── Paths ────────────────────────────────────────────────────────────────
    dataset_dir    = Path(mod_config.DATASET_DIR)
    outputs_dir    = Path(mod_config.OUTPUTS_DIR)
    checkpoint_dir = outputs_dir / "checkpoints"
    metrics_dir    = outputs_dir / "metrics"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    metrics_dir.mkdir(parents=True, exist_ok=True)

    image_size   = tuple(mod_config.IMAGE_SIZE)       # e.g. (224, 224)
    num_channels = mod_config.NUM_CHANNELS             # 3
    input_shape  = image_size + (num_channels,)
    num_classes  = len(class_names)
    class_mode   = mod_config.CLASSIFICATION_MODE     # "multiclass"
    aug_hflip    = getattr(mod_config, "AUGMENT_HORIZONTAL_FLIP", False)

    # ── Locate split directories ─────────────────────────────────────────────
    train_dir, val_dir, test_dir = _resolve_split_dirs(dataset_dir)

    log.info("=" * 60)
    log.info("Training pipeline starting — module: %s", mod_config.MODULE_SLUG.upper())
    log.info("  Train dir : %s", train_dir)
    log.info("  Val dir   : %s  (None = carved from train)", val_dir)
    log.info("  Test dir  : %s", test_dir)
    log.info("  Classes   : %s", class_names)
    log.info("  Batch size: %d | Initial LR: %.1e | Seed: %d",
             batch_size, initial_lr, random_seed)
    log.info("=" * 60)

    # ── Build tf.data datasets ───────────────────────────────────────────────
    train_ds, val_ds, test_ds = _build_datasets(
        train_dir=train_dir,
        val_dir=val_dir,
        test_dir=test_dir,
        class_names=class_names,
        image_size=image_size,
        batch_size=batch_size,
        class_mode=class_mode,
        validation_split=validation_split,
        aug_hflip=aug_hflip,
        random_seed=random_seed,
    )

    # ── Compute class weights ────────────────────────────────────────────────
    class_weights = _compute_class_weights(train_dir, class_names)
    log.info("Class weights: %s", class_weights)

    # ── Build model ──────────────────────────────────────────────────────────
    from common.model_builder import build_module_model, get_gradcam_layer_name

    model = build_module_model(
        num_classes=num_classes,
        classification_mode=class_mode,
        architecture=mod_config.ARCHITECTURE,
        input_shape=input_shape,
        frozen=True,
        dropout_rate=dropout_rate,
    )
    model.summary(print_fn=log.info)

    best_ckpt_s1 = str(checkpoint_dir / "best_stage1.weights.h5")

    # ── Stage 1: Train classification head (backbone frozen) ─────────────────
    log.info("=" * 60)
    log.info("STAGE 1 — Transfer Learning (backbone frozen, up to %d epochs)", initial_epochs)
    log.info("=" * 60)

    callbacks_s1 = _build_callbacks(
        checkpoint_path=best_ckpt_s1,
        log_dir=checkpoint_dir,
        early_stopping_patience=early_stopping_patience,
        reduce_lr_patience=reduce_lr_patience,
        reduce_lr_factor=reduce_lr_factor,
        reduce_lr_min_lr=reduce_lr_min_lr,
        csv_name="stage1_log.csv",
    )

    t0 = time.time()
    history_s1 = model.fit(
        train_ds,
        epochs=initial_epochs,
        validation_data=val_ds,
        class_weight=class_weights,
        callbacks=callbacks_s1,
        verbose=1,
    )
    stage1_duration = time.time() - t0
    s1_epochs_run = len(history_s1.history["loss"])
    log.info("Stage 1 finished: %d epochs in %.1f s", s1_epochs_run, stage1_duration)

    # Load best Stage-1 weights before unlocking backbone
    try:
        model.load_weights(best_ckpt_s1)
        log.info("Loaded best Stage-1 checkpoint for fine-tuning.")
    except Exception as e:
        log.warning("Could not load Stage-1 checkpoint (%s). Continuing with final weights.", e)

    # ── Stage 2: Fine-tune upper backbone ────────────────────────────────────
    log.info("=" * 60)
    log.info("STAGE 2 — Fine-Tuning (backbone unfrozen from layer %d, up to %d extra epochs)",
             fine_tune_at_layer, fine_tune_epochs)
    log.info("=" * 60)

    base_model = _get_base_model(model)
    if base_model is not None:
        base_model.trainable = True
        for layer in base_model.layers[:fine_tune_at_layer]:
            layer.trainable = False
        trainable_count = sum(1 for l in base_model.layers if l.trainable)
        log.info("Unfrozen %d backbone layers (of %d total).",
                 trainable_count, len(base_model.layers))
    else:
        log.warning("Base model sub-layer not found; fine-tuning entire model.")
        model.trainable = True

    _recompile_model(model, class_mode, num_classes, fine_tune_lr)

    best_ckpt_s2 = str(checkpoint_dir / "best_stage2.weights.h5")
    callbacks_s2 = _build_callbacks(
        checkpoint_path=best_ckpt_s2,
        log_dir=checkpoint_dir,
        early_stopping_patience=early_stopping_patience,
        reduce_lr_patience=reduce_lr_patience,
        reduce_lr_factor=reduce_lr_factor,
        reduce_lr_min_lr=reduce_lr_min_lr,
        csv_name="stage2_log.csv",
    )

    t1 = time.time()
    history_s2 = model.fit(
        train_ds,
        epochs=s1_epochs_run + fine_tune_epochs,
        initial_epoch=s1_epochs_run,
        validation_data=val_ds,
        class_weight=class_weights,
        callbacks=callbacks_s2,
        verbose=1,
    )
    stage2_duration = time.time() - t1
    s2_epochs_run = len(history_s2.history["loss"])
    log.info("Stage 2 finished: %d epochs in %.1f s", s2_epochs_run, stage2_duration)

    # Load best checkpoint across Stage 1 and Stage 2 for export
    best_s1_acc = max(history_s1.history.get("val_accuracy", [0]))
    best_s2_acc = max(history_s2.history.get("val_accuracy", [0])) if history_s2.history.get("val_accuracy") else -1.0
    log.info("Best Stage 1 val_accuracy: %.4f | Best Stage 2 val_accuracy: %.4f", best_s1_acc, best_s2_acc)

    if best_s2_acc >= best_s1_acc and Path(best_ckpt_s2).exists():
        try:
            model.load_weights(best_ckpt_s2)
            log.info("Loaded best Stage-2 checkpoint (val_acc=%.4f) for final export.", best_s2_acc)
        except Exception as e:
            log.warning("Could not load Stage-2 checkpoint (%s). Continuing with current weights.", e)
    elif Path(best_ckpt_s1).exists():
        try:
            if base_model is not None:
                base_model.trainable = False
            model.load_weights(best_ckpt_s1)
            log.info("Loaded best Stage-1 checkpoint (val_acc=%.4f) as Stage 2 did not improve.", best_s1_acc)
        except Exception as e:
            log.warning("Could not load Stage-1 checkpoint (%s). Continuing with current weights.", e)

    # ── Evaluate on held-out TEST split ──────────────────────────────────────
    eval_metrics: Dict[str, Any] = {}
    if test_ds is not None:
        log.info("=" * 60)
        log.info("EVALUATION — Held-out Test Split (untouched during all training)")
        log.info("=" * 60)
        raw_results = model.evaluate(test_ds, verbose=1, return_dict=True)
        eval_metrics = {k: float(v) for k, v in raw_results.items()}
        log.info("Test results: %s", eval_metrics)

        eval_path = metrics_dir / "evaluation.json"
        with open(eval_path, "w") as f:
            json.dump(eval_metrics, f, indent=2)
        log.info("Evaluation saved -> %s", eval_path)

        _save_classification_report(model, test_ds, class_names, class_mode, metrics_dir)
    else:
        log.warning("No test directory found — skipping final evaluation.")

    # ── Save final trained model ─────────────────────────────────────────────
    model_path = outputs_dir / mod_config.MODEL_FILENAME
    model.save(str(model_path))
    log.info("Trained model saved -> %s", model_path)

    # ── Calculate Model SHA-256 Checksum ─────────────────────────────────────
    import hashlib
    sha256 = hashlib.sha256()
    with open(model_path, "rb") as f:
        while chunk := f.read(65536):
            sha256.update(chunk)
    model_sha256 = sha256.hexdigest()
    log.info("Model SHA-256: %s", model_sha256)

    # ── Merge and save training history ──────────────────────────────────────
    combined_history = _merge_histories(history_s1.history, history_s2.history)
    _save_history(combined_history, metrics_dir)

    val_accs = combined_history.get("val_accuracy", [])
    val_losses = combined_history.get("val_loss", [])
    if val_accs:
        best_epoch_idx = int(np.argmax(val_accs))
        best_epoch = best_epoch_idx + 1
        best_val_metrics = {
            "val_accuracy": float(val_accs[best_epoch_idx]),
            "val_loss": float(val_losses[best_epoch_idx]) if val_losses else None,
        }
    else:
        best_epoch = s1_epochs_run + s2_epochs_run
        best_val_metrics = {}

    gradcam_layer = get_gradcam_layer_name(model, mod_config.GRADCAM_LAYER_NAME)

    return {
        "model": model,
        "model_path": model_path,
        "model_sha256": model_sha256,
        "best_epoch": best_epoch,
        "best_val_metrics": best_val_metrics,
        "class_names": class_names,
        "gradcam_layer": gradcam_layer,
        "history": combined_history,
        "evaluation": eval_metrics,
        "stage1_epochs": s1_epochs_run,
        "stage2_epochs": s2_epochs_run,
        "total_duration_s": stage1_duration + stage2_duration,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _seed_everything(seed: int, tf: Any) -> None:
    import os
    import random
    os.environ["PYTHONHASHSEED"] = str(seed)
    random.seed(seed)
    np.random.seed(seed)
    tf.random.set_seed(seed)


def _resolve_split_dirs(
    dataset_dir: Path,
) -> Tuple[Path, Optional[Path], Optional[Path]]:
    """
    Return (train_dir, val_dir, test_dir) from a pre-split dataset root.
    Accepts both lower-case (train/val/test) and title-case (Training/Testing).
    val_dir / test_dir may be None.
    """
    aliases = {
        "train":      "train",
        "training":   "train",
        "val":        "val",
        "validation": "val",
        "test":       "test",
        "testing":    "test",
    }
    resolved: Dict[str, Path] = {}
    for d in dataset_dir.iterdir():
        if not d.is_dir() or d.name.startswith("."):
            continue
        key = aliases.get(d.name.lower())
        if key and key not in resolved:
            resolved[key] = d

    if "train" not in resolved:
        # Check if an immediate subfolder contains the splits (e.g. chest_xray/)
        for child in dataset_dir.iterdir():
            if child.is_dir() and not child.name.startswith("."):
                sub_resolved: Dict[str, Path] = {}
                for d in child.iterdir():
                    if d.is_dir() and not d.name.startswith("."):
                        key = aliases.get(d.name.lower())
                        if key and key not in sub_resolved:
                            sub_resolved[key] = d
                if "train" in sub_resolved:
                    resolved = sub_resolved
                    break

    if "train" not in resolved:
        raise FileNotFoundError(
            f"No training directory found inside {dataset_dir}. "
            "Expected a folder named 'train' or 'Training'."
        )
    return resolved["train"], resolved.get("val"), resolved.get("test")


def _preprocess_map(image: Any, label: Any) -> Tuple[Any, Any]:
    """Apply ResNet50 preprocessing (scales to [-1, 1])."""
    import tensorflow as tf
    image = tf.cast(image, tf.float32)
    image = tf.keras.applications.resnet50.preprocess_input(image)
    return image, label


def _build_aug_fn(aug_hflip: bool) -> Any:
    """Return a Keras Sequential augmentation model for training-time use."""
    import tensorflow as tf
    aug_layers = []
    if aug_hflip:
        aug_layers.append(tf.keras.layers.RandomFlip("horizontal"))
    aug_layers += [
        tf.keras.layers.RandomRotation(10 / 360),
        tf.keras.layers.RandomZoom(0.10),
        tf.keras.layers.RandomTranslation(0.05, 0.05),
    ]
    return tf.keras.Sequential(aug_layers, name="augmentation")


def _build_datasets(
    train_dir: Path,
    val_dir: Optional[Path],
    test_dir: Optional[Path],
    class_names: List[str],
    image_size: Tuple[int, int],
    batch_size: int,
    class_mode: str,
    validation_split: float,
    aug_hflip: bool,
    random_seed: int,
) -> Tuple[Any, Any, Optional[Any]]:
    import tensorflow as tf

    AUTOTUNE = tf.data.AUTOTUNE
    label_mode = "categorical" if class_mode in ("multiclass", "multilabel") else "binary"
    aug = _build_aug_fn(aug_hflip)

    def _load(directory: Path, subset: Optional[str] = None,
               val_split: float = 0.0, shuffle: bool = True) -> Any:
        kw: Dict[str, Any] = dict(
            directory=str(directory),
            labels="inferred",
            label_mode=label_mode,
            class_names=class_names,
            color_mode="rgb",
            batch_size=batch_size,
            image_size=image_size,
            shuffle=shuffle,
            seed=random_seed,
            interpolation="bilinear",
        )
        if subset is not None:
            kw["validation_split"] = val_split
            kw["subset"] = subset
        return tf.keras.utils.image_dataset_from_directory(**kw)

    # ── Training + validation ────────────────────────────────────────────────
    if val_dir is not None:
        log.info("Dedicated val dir found: %s", val_dir)
        raw_train = _load(train_dir, shuffle=True)
        raw_val   = _load(val_dir, shuffle=False)
    else:
        log.info("No dedicated val dir — carving %.0f%% validation from training data.",
                 validation_split * 100)
        raw_train = _load(train_dir, subset="training",
                          val_split=validation_split, shuffle=True)
        raw_val   = _load(train_dir, subset="validation",
                          val_split=validation_split, shuffle=False)

    train_ds = (
        raw_train
        .cache()
        .map(lambda img, lbl: (aug(img, training=True), lbl),
             num_parallel_calls=AUTOTUNE)
        .map(_preprocess_map, num_parallel_calls=AUTOTUNE)
        .prefetch(AUTOTUNE)
    )
    val_ds = (
        raw_val
        .cache()
        .map(_preprocess_map, num_parallel_calls=AUTOTUNE)
        .prefetch(AUTOTUNE)
    )

    # ── Test split (never touched during training) ───────────────────────────
    test_ds = None
    if test_dir is not None:
        log.info("Test dir found (held-out): %s", test_dir)
        raw_test = _load(test_dir, shuffle=False)
        test_ds = (
            raw_test
            .cache()
            .map(_preprocess_map, num_parallel_calls=AUTOTUNE)
            .prefetch(AUTOTUNE)
        )

    return train_ds, val_ds, test_ds


def _compute_class_weights(train_dir: Path, class_names: List[str]) -> Dict[int, float]:
    """Inverse-frequency class weights from image counts in train_dir."""
    VALID_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"}
    counts = []
    for cls in class_names:
        cls_dir = train_dir / cls
        n = sum(1 for f in cls_dir.iterdir() if f.suffix.lower() in VALID_EXT) \
            if cls_dir.exists() else 0
        counts.append(max(n, 1))
    total = sum(counts)
    n_cls = len(class_names)
    return {i: total / (n_cls * counts[i]) for i in range(n_cls)}


def _build_callbacks(
    checkpoint_path: str,
    log_dir: Path,
    early_stopping_patience: int,
    reduce_lr_patience: int,
    reduce_lr_factor: float,
    reduce_lr_min_lr: float,
    csv_name: str = "training_log.csv",
) -> List[Any]:
    import tensorflow as tf
    return [
        tf.keras.callbacks.ModelCheckpoint(
            filepath=checkpoint_path,
            monitor="val_accuracy",
            save_best_only=True,
            save_weights_only=True,
            verbose=1,
        ),
        tf.keras.callbacks.EarlyStopping(
            monitor="val_accuracy",
            patience=early_stopping_patience,
            restore_best_weights=False,
            verbose=1,
        ),
        tf.keras.callbacks.ReduceLROnPlateau(
            monitor="val_loss",
            factor=reduce_lr_factor,
            patience=reduce_lr_patience,
            min_lr=reduce_lr_min_lr,
            verbose=1,
        ),
        tf.keras.callbacks.CSVLogger(
            str(log_dir / csv_name),
            append=False,
        ),
    ]


def _get_base_model(model: Any) -> Optional[Any]:
    """Walk top-level layers to find the ResNet50 sub-model."""
    for layer in model.layers:
        sub_layers = getattr(layer, "layers", [])
        if len(sub_layers) > 10:
            return layer
    return None


def _recompile_model(model: Any, class_mode: str, num_classes: int, lr: float) -> None:
    import tensorflow as tf
    if class_mode == "multilabel":
        loss = "binary_crossentropy"
        metrics = ["accuracy", tf.keras.metrics.AUC(name="auc", multi_label=True)]
    elif class_mode == "binary":
        loss = "binary_crossentropy"
        metrics = ["accuracy", tf.keras.metrics.AUC(name="auc")]
    else:
        loss = "categorical_crossentropy"
        metrics = ["accuracy"]
        if num_classes > 2:
            metrics.append(tf.keras.metrics.TopKCategoricalAccuracy(k=min(3, num_classes), name="top_3_acc"))
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=lr),
        loss=loss,
        metrics=metrics,
    )
    log.info("Recompiled for fine-tuning  LR=%.1e, loss=%s.", lr, loss)


def _merge_histories(h1: Dict, h2: Dict) -> Dict:
    merged: Dict[str, List] = {}
    for k in h1:
        merged[k] = list(h1[k]) + list(h2.get(k, []))
    for k in h2:
        if k not in merged:
            merged[k] = list(h2[k])
    return merged


def _save_history(history: Dict, metrics_dir: Path) -> None:
    out = metrics_dir / "training_history.json"
    with open(out, "w") as f:
        json.dump({k: [float(v) for v in vals] for k, vals in history.items()}, f, indent=2)
    log.info("Training history saved -> %s", out)
    for key in ["loss", "accuracy", "val_loss", "val_accuracy"]:
        if key in history and history[key]:
            vals = history[key]
            best = max(vals) if "acc" in key else min(vals)
            log.info("  Final %-20s : %.4f  (best: %.4f)", key, vals[-1], best)


def _save_classification_report(
    model: Any,
    test_ds: Any,
    class_names: List[str],
    class_mode: str,
    metrics_dir: Path,
) -> None:
    try:
        from sklearn.metrics import classification_report, confusion_matrix
        import pandas as pd

        y_true_all: List[int] = []
        y_pred_all: List[int] = []
        for images, labels in test_ds:
            preds = model.predict(images, verbose=0)
            if class_mode == "binary":
                y_pred = (preds[:, 0] > 0.5).astype(int)
                y_true = labels.numpy().astype(int).flatten()
            else:
                y_pred = np.argmax(preds, axis=1)
                y_true = np.argmax(labels.numpy(), axis=1)
            y_true_all.extend(y_true.tolist())
            y_pred_all.extend(y_pred.tolist())

        report = classification_report(
            y_true_all, y_pred_all,
            target_names=class_names,
            output_dict=True,
            zero_division=0,
        )
        rp = metrics_dir / "classification_report.json"
        with open(rp, "w") as f:
            json.dump(report, f, indent=2)
        log.info("Classification report -> %s", rp)

        cm = confusion_matrix(y_true_all, y_pred_all)
        cm_df = pd.DataFrame(cm, index=class_names, columns=class_names)
        cp = metrics_dir / "confusion_matrix.csv"
        cm_df.to_csv(cp)
        log.info("Confusion matrix -> %s", cp)
        log.info("Confusion Matrix:\n%s", cm_df.to_string())

    except ImportError as e:
        log.warning("sklearn/pandas not available — skipping report: %s", e)
    except Exception as e:
        log.warning("Classification report failed: %s", e, exc_info=True)
