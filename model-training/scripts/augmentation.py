"""
CliniXAI Phase 7 — Data Augmentation.

RULE: Augmentation is applied to TRAINING data only.
      Validation and test sets receive ZERO stochastic augmentation —
      only deterministic preprocessing from preprocessing.py.

All transformations are conservative and medically safe by default.
Horizontal flip is OFF by default — enable only after confirming it is
clinically appropriate for the chosen imaging modality/task.
"""

import sys
from pathlib import Path
import tensorflow as tf

sys.path.insert(0, str(Path(__file__).parent.parent))
import config as cfg


def build_augmentation_layer(training: bool = True) -> tf.keras.Sequential:
    """
    Return a Keras Sequential model containing augmentation layers.

    When training=False, all layers are no-ops (pass-through).
    This keeps the model graph unified between train and eval.

    Parameters
    ----------
    training : bool
        True  → stochastic augmentation active during model.fit
        False → identity transform (for val/test pipelines)
    """
    if not training:
        return tf.keras.Sequential([
            tf.keras.layers.Identity(name="no_augmentation")
        ], name="augmentation_off")

    layers = [
        # Small rotation — safe for most medical modalities
        tf.keras.layers.RandomRotation(
            factor=cfg.AUGMENT_ROTATION_RANGE / 360.0,
            fill_mode="reflect",
            name="aug_rotation",
        ),
        # Small zoom
        tf.keras.layers.RandomZoom(
            height_factor=(-cfg.AUGMENT_ZOOM_RANGE, cfg.AUGMENT_ZOOM_RANGE),
            fill_mode="reflect",
            name="aug_zoom",
        ),
        # Small translation
        tf.keras.layers.RandomTranslation(
            height_factor=cfg.AUGMENT_HEIGHT_SHIFT,
            width_factor=cfg.AUGMENT_WIDTH_SHIFT,
            fill_mode="reflect",
            name="aug_translation",
        ),
        # Mild brightness — DOES NOT alter structural clinical features
        tf.keras.layers.RandomBrightness(
            factor=(
                cfg.AUGMENT_BRIGHTNESS_RANGE[0] - 1.0,
                cfg.AUGMENT_BRIGHTNESS_RANGE[1] - 1.0,
            ),
            name="aug_brightness",
        ),
    ]

    # Horizontal flip — disabled by default (see config.AUGMENT_HORIZONTAL_FLIP)
    if cfg.AUGMENT_HORIZONTAL_FLIP:
        layers.append(
            tf.keras.layers.RandomFlip(mode="horizontal", name="aug_hflip")
        )

    return tf.keras.Sequential(layers, name="augmentation_on")


def build_tf_datasets(
    class_names: list,
) -> tuple:
    """
    Build tf.data pipelines for train, val, and test splits.

    Processing pipeline (train)
    ---------------------------
    image_dataset_from_directory
    → resnet50.preprocess_input
    → augmentation layers
    → prefetch

    Processing pipeline (val / test)
    ---------------------------------
    image_dataset_from_directory
    → resnet50.preprocess_input
    → prefetch   (NO augmentation)

    Returns
    -------
    (train_ds, val_ds, test_ds, class_names)
    """
    from tensorflow.keras.applications.resnet50 import preprocess_input

    common_kwargs = dict(
        image_size=cfg.IMAGE_SIZE,
        batch_size=cfg.BATCH_SIZE,
        color_mode="rgb",
        shuffle=False,    # we shuffle manually below for train
        seed=cfg.RANDOM_SEED,
    )

    # ── Train ────────────────────────────────────────────────────────────────
    raw_train = tf.keras.utils.image_dataset_from_directory(
        str(cfg.TRAIN_DIR),
        labels="inferred",
        label_mode="categorical" if len(class_names) > 2 else "binary",
        class_names=class_names,
        shuffle=True,
        **{k: v for k, v in common_kwargs.items() if k != "shuffle"},
    )

    augment_fn = build_augmentation_layer(training=True)

    def train_map(x, y):
        x = preprocess_input(tf.cast(x, tf.float32))
        x = augment_fn(x, training=True)
        return x, y

    AUTOTUNE = tf.data.AUTOTUNE
    train_ds = (
        raw_train
        .map(train_map, num_parallel_calls=AUTOTUNE)
        .prefetch(AUTOTUNE)
    )

    def eval_map(x, y):
        x = preprocess_input(tf.cast(x, tf.float32))
        return x, y

    # ── Validation ───────────────────────────────────────────────────────────
    raw_val = tf.keras.utils.image_dataset_from_directory(
        str(cfg.VAL_DIR),
        labels="inferred",
        label_mode="categorical" if len(class_names) > 2 else "binary",
        class_names=class_names,
        **common_kwargs,
    )
    val_ds = raw_val.map(eval_map, num_parallel_calls=AUTOTUNE).prefetch(AUTOTUNE)

    # ── Test ─────────────────────────────────────────────────────────────────
    raw_test = tf.keras.utils.image_dataset_from_directory(
        str(cfg.TEST_DIR),
        labels="inferred",
        label_mode="categorical" if len(class_names) > 2 else "binary",
        class_names=class_names,
        **common_kwargs,
    )
    test_ds = raw_test.map(eval_map, num_parallel_calls=AUTOTUNE).prefetch(AUTOTUNE)

    return train_ds, val_ds, test_ds
