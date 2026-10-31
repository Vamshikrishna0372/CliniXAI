"""
CliniXAI Phase 7 — Master Training Script.

Usage:
    python scripts/train.py

Pipeline
--------
1.  Reproducibility seeds
2.  Hardware detection
3.  Dataset validation
4.  Class discovery + distribution report
5.  Class-weight computation (imbalance handling)
6.  Build tf.data pipelines (train / val / test)
7.  Stage 1 — Transfer learning  (backbone frozen)
8.  Stage 2 — Fine-tuning        (upper backbone unfrozen)
9.  Save training history JSON
10. Generate accuracy + loss plots
"""

import os
import sys
import json
import random
import logging
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

# ── path bootstrap ───────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent.parent))
import config as cfg
from scripts.validate_dataset import validate_dataset

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
log = logging.getLogger("train")


# ---------------------------------------------------------------------------
# 1. Reproducibility
# ---------------------------------------------------------------------------
def set_seeds(seed: int = cfg.RANDOM_SEED) -> None:
    os.environ["PYTHONHASHSEED"] = str(seed)
    random.seed(seed)
    np.random.seed(seed)
    import tensorflow as tf
    tf.random.set_seed(seed)
    log.info("Random seed set to %d  (full GPU determinism not guaranteed)", seed)


# ---------------------------------------------------------------------------
# 2. Hardware detection
# ---------------------------------------------------------------------------
def report_hardware() -> None:
    import tensorflow as tf
    log.info("TensorFlow version : %s", tf.__version__)
    gpus = tf.config.list_physical_devices("GPU")
    if gpus:
        log.info("GPUs detected      : %d", len(gpus))
        for g in gpus:
            log.info("  %s", g)
    else:
        log.warning("No GPU detected — training will run on CPU (slower).")


# ---------------------------------------------------------------------------
# 4. Class distribution
# ---------------------------------------------------------------------------
def compute_class_distribution(class_names: list) -> dict:
    """Count images per class in the training split."""
    distribution = {}
    total = 0
    for cls in class_names:
        cls_dir = cfg.TRAIN_DIR / cls
        count = len([
            f for f in cls_dir.iterdir()
            if f.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"}
        ]) if cls_dir.exists() else 0
        distribution[cls] = count
        total += count

    log.info("Training class distribution:")
    for cls, cnt in distribution.items():
        pct = 100 * cnt / total if total else 0
        log.info("  %-25s  %5d images  (%5.1f%%)", cls, cnt, pct)
    log.info("  Total: %d images", total)
    return distribution


# ---------------------------------------------------------------------------
# 5. Class weights
# ---------------------------------------------------------------------------
def compute_class_weights(distribution: dict) -> dict:
    """
    Compute sklearn-style class weights to compensate for imbalance.
    Returns {class_index: weight} dict for Keras model.fit(class_weight=...).
    """
    from sklearn.utils.class_weight import compute_class_weight

    class_names = list(distribution.keys())
    counts = [distribution[c] for c in class_names]
    total  = sum(counts)

    # Build flat label array matching the distribution
    labels = []
    for idx, cnt in enumerate(counts):
        labels.extend([idx] * cnt)
    labels = np.array(labels)

    weights = compute_class_weight(
        class_weight="balanced",
        classes=np.arange(len(class_names)),
        y=labels,
    )
    weight_dict = {i: float(w) for i, w in enumerate(weights)}
    log.info("Class weights: %s", weight_dict)
    return weight_dict


# ---------------------------------------------------------------------------
# 9. Save history
# ---------------------------------------------------------------------------
def save_history(history_stage1, history_stage2=None) -> None:
    cfg.METRICS_DIR.mkdir(parents=True, exist_ok=True)

    combined = {}
    for key, values in history_stage1.history.items():
        combined[f"stage1_{key}"] = [float(v) for v in values]

    if history_stage2:
        for key, values in history_stage2.history.items():
            combined[f"stage2_{key}"] = [float(v) for v in values]

    with open(cfg.TRAINING_HISTORY, "w") as f:
        json.dump(combined, f, indent=2)
    log.info("Training history saved → %s", cfg.TRAINING_HISTORY)


# ---------------------------------------------------------------------------
# 10. Training plots
# ---------------------------------------------------------------------------
def plot_history(history_stage1, history_stage2=None) -> None:
    import matplotlib
    matplotlib.use("Agg")          # headless — no GUI required
    import matplotlib.pyplot as plt

    cfg.PLOTS_DIR.mkdir(parents=True, exist_ok=True)

    def _concat(key):
        s1 = list(history_stage1.history.get(key, []))
        s2 = list(history_stage2.history.get(key, [])) if history_stage2 else []
        return s1 + s2

    acc      = _concat("accuracy")
    val_acc  = _concat("val_accuracy")
    loss     = _concat("loss")
    val_loss = _concat("val_loss")
    epochs   = range(1, len(acc) + 1)

    stage1_end = len(history_stage1.history.get("accuracy", []))

    # ── Accuracy ──────────────────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(epochs, acc,     label="Train accuracy")
    ax.plot(epochs, val_acc, label="Val accuracy")
    if history_stage2:
        ax.axvline(x=stage1_end + 0.5, color="grey", linestyle="--",
                   label="Fine-tuning start")
    ax.set_title("Model Accuracy — CliniXAI ResNet50")
    ax.set_xlabel("Epoch")
    ax.set_ylabel("Accuracy")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    acc_path = cfg.PLOTS_DIR / "accuracy.png"
    fig.savefig(acc_path, dpi=150)
    plt.close(fig)
    log.info("Accuracy plot saved → %s", acc_path)

    # ── Loss ──────────────────────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(epochs, loss,     label="Train loss")
    ax.plot(epochs, val_loss, label="Val loss")
    if history_stage2:
        ax.axvline(x=stage1_end + 0.5, color="grey", linestyle="--",
                   label="Fine-tuning start")
    ax.set_title("Model Loss — CliniXAI ResNet50")
    ax.set_xlabel("Epoch")
    ax.set_ylabel("Loss")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    loss_path = cfg.PLOTS_DIR / "loss.png"
    fig.savefig(loss_path, dpi=150)
    plt.close(fig)
    log.info("Loss plot saved → %s", loss_path)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    import tensorflow as tf
    from scripts.model import (
        build_model, unfreeze_top_layers,
        recompile_for_finetuning, build_callbacks, get_gradcam_layer_name,
    )
    from scripts.augmentation import build_tf_datasets

    log.info("=" * 60)
    log.info("CliniXAI Phase 7 — ResNet50 Training Pipeline")
    log.info("=" * 60)

    # 1. Seeds
    set_seeds()

    # 2. Hardware
    report_hardware()

    # 3. Dataset validation
    report = validate_dataset(raise_on_error=True)
    class_names = report["classes"]
    num_classes  = len(class_names)
    log.info("Classes: %s", class_names)

    # Save class names for Phase 8
    cfg.OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(cfg.CLASS_NAMES_FILE, "w") as f:
        json.dump(class_names, f, indent=2)
    log.info("Class names saved → %s", cfg.CLASS_NAMES_FILE)

    # 4. Class distribution
    distribution = compute_class_distribution(class_names)

    # 5. Class weights
    class_weight = compute_class_weights(distribution) if cfg.USE_CLASS_WEIGHTS else None

    # 6. Build datasets
    log.info("Building tf.data pipelines …")
    train_ds, val_ds, test_ds = build_tf_datasets(class_names)

    # 7. ── Stage 1: Transfer learning ─────────────────────────────────────────
    log.info("")
    log.info("STAGE 1 — Transfer Learning (backbone frozen)")
    log.info("  LR=%g  Epochs=%d  BatchSize=%d",
             cfg.INITIAL_LR, cfg.INITIAL_EPOCHS, cfg.BATCH_SIZE)

    model = build_model(num_classes, frozen=True)
    model.summary(print_fn=log.info)
    log.info("Trainable params (stage 1): %s",
             f"{sum(np.prod(v.shape) for v in model.trainable_variables):,}")

    callbacks = build_callbacks()

    history_s1 = model.fit(
        train_ds,
        epochs=cfg.INITIAL_EPOCHS,
        validation_data=val_ds,
        callbacks=callbacks,
        class_weight=class_weight,
        verbose=1,
    )

    # 8. ── Stage 2: Fine-tuning ────────────────────────────────────────────────
    log.info("")
    log.info("STAGE 2 — Fine-Tuning (upper backbone unfrozen from layer %d)",
             cfg.FINE_TUNE_AT_LAYER)
    log.info("  LR=%g  Epochs=%d", cfg.FINE_TUNE_LR, cfg.FINE_TUNE_EPOCHS)

    unfreeze_top_layers(model)
    recompile_for_finetuning(model, num_classes)
    log.info("Trainable params (stage 2): %s",
             f"{sum(np.prod(v.shape) for v in model.trainable_variables):,}")

    callbacks_ft = build_callbacks()

    history_s2 = model.fit(
        train_ds,
        initial_epoch=len(history_s1.history["loss"]),
        epochs=len(history_s1.history["loss"]) + cfg.FINE_TUNE_EPOCHS,
        validation_data=val_ds,
        callbacks=callbacks_ft,
        class_weight=class_weight,
        verbose=1,
    )

    # 9. Save history
    save_history(history_s1, history_s2)

    # 10. Plots
    plot_history(history_s1, history_s2)

    # Also detect and log Grad-CAM layer for metadata
    gradcam_layer = get_gradcam_layer_name(model)
    log.info("Grad-CAM target layer detected: %s", gradcam_layer)

    # Save gradcam layer name for other scripts
    meta_tmp = {"gradcam_layer": gradcam_layer, "class_names": class_names}
    cfg.METRICS_DIR.mkdir(parents=True, exist_ok=True)
    with open(cfg.METRICS_DIR / "training_meta.json", "w") as f:
        json.dump(meta_tmp, f, indent=2)

    log.info("")
    log.info("=" * 60)
    log.info("Training complete.")
    log.info("Run: python scripts/evaluate.py")
    log.info("Run: python scripts/gradcam_validation.py")
    log.info("Run: python scripts/export_model.py")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
