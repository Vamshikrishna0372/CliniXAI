"""
CliniXAI Phase 7 — ResNet50 Model Builder.

Builds a transfer-learning + fine-tuning ready ResNet50 model with a
task-appropriate classification head.

Two-stage training strategy
---------------------------
Stage 1 (transfer learning)
    ResNet50 backbone  → FROZEN
    Classification head → trained

Stage 2 (fine-tuning)
    ResNet50 upper layers (from cfg.FINE_TUNE_AT_LAYER onward) → UNFROZEN
    Entire model trained at a much lower learning rate

BatchNormalization handling
---------------------------
During fine-tuning, BN layers inside the frozen backbone section are kept
in inference mode (training=False at call site) to avoid corrupting the
pre-trained running statistics. Only BN layers in the unfrozen section
receive gradient updates, and only when model.fit is called with
training=True propagating through them.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import config as cfg


def build_model(num_classes: int, *, frozen: bool = True) -> "tf.keras.Model":
    """
    Build and compile the CliniXAI ResNet50 classification model.

    Parameters
    ----------
    num_classes : int
        Number of target classes (2 → binary, >2 → multiclass).
    frozen : bool
        True  → Stage 1: backbone fully frozen (transfer learning).
        False → Stage 2: upper backbone unfrozen (fine-tuning).
        Use freeze_backbone() / unfreeze_top_layers() to switch after build.

    Returns
    -------
    tf.keras.Model  compiled and ready for model.fit
    """
    import tensorflow as tf
    from tensorflow.keras import layers, Model
    from tensorflow.keras.applications import ResNet50
    from tensorflow.keras.optimizers import Adam

    lr = cfg.INITIAL_LR if frozen else cfg.FINE_TUNE_LR

    # ── Backbone ─────────────────────────────────────────────────────────────
    backbone = ResNet50(
        include_top=False,
        weights="imagenet",
        input_shape=(*cfg.IMAGE_SIZE, cfg.NUM_CHANNELS),
    )
    backbone.trainable = not frozen   # freeze for stage 1

    # ── Classification head ───────────────────────────────────────────────────
    inputs = tf.keras.Input(shape=(*cfg.IMAGE_SIZE, cfg.NUM_CHANNELS), name="image_input")
    x = backbone(inputs, training=False)   # training=False keeps BN in inference mode
    x = layers.GlobalAveragePooling2D(name="gap")(x)
    x = layers.Dropout(cfg.DROPOUT_RATE, name="dropout")(x)

    if num_classes == 2:
        # Binary: single sigmoid output
        outputs = layers.Dense(1, activation="sigmoid", name="output")(x)
        loss    = "binary_crossentropy"
        metrics = [
            tf.keras.metrics.BinaryAccuracy(name="accuracy"),
            tf.keras.metrics.AUC(name="auc"),
            tf.keras.metrics.Precision(name="precision"),
            tf.keras.metrics.Recall(name="recall"),
        ]
    else:
        # Multi-class: softmax
        outputs = layers.Dense(num_classes, activation="softmax", name="output")(x)
        loss    = "categorical_crossentropy"
        metrics = [
            tf.keras.metrics.CategoricalAccuracy(name="accuracy"),
            tf.keras.metrics.AUC(name="auc", multi_label=False),
        ]

    model = Model(inputs, outputs, name=cfg.MODEL_NAME)
    model.compile(optimizer=Adam(learning_rate=lr), loss=loss, metrics=metrics)

    return model


def freeze_backbone(model: "tf.keras.Model") -> None:
    """Set backbone (ResNet50 sub-model) to fully frozen. Recompile after calling."""
    _set_backbone_trainable(model, trainable=False)


def unfreeze_top_layers(model: "tf.keras.Model") -> None:
    """
    Unfreeze ResNet50 layers from cfg.FINE_TUNE_AT_LAYER onward.

    Lower layers remain frozen to preserve low-level ImageNet features.
    The model must be recompiled after calling this.
    """
    import tensorflow as tf
    backbone = _get_backbone(model)
    if backbone is None:
        raise RuntimeError("Cannot locate ResNet50 backbone inside model.")

    # First freeze everything
    backbone.trainable = True
    for layer in backbone.layers[: cfg.FINE_TUNE_AT_LAYER]:
        layer.trainable = False
        # Keep BN layers in frozen section in inference mode
        if isinstance(layer, tf.keras.layers.BatchNormalization):
            layer.trainable = False


def _set_backbone_trainable(model: "tf.keras.Model", trainable: bool) -> None:
    backbone = _get_backbone(model)
    if backbone is not None:
        backbone.trainable = trainable


def _get_backbone(model: "tf.keras.Model"):
    """Return the embedded ResNet50 sub-model, or None if not found."""
    for layer in model.layers:
        if "resnet50" in layer.name.lower():
            return layer
    return None


def recompile_for_finetuning(model: "tf.keras.Model", num_classes: int) -> None:
    """Recompile the model with the fine-tuning learning rate."""
    import tensorflow as tf
    from tensorflow.keras.optimizers import Adam

    if num_classes == 2:
        loss    = "binary_crossentropy"
        metrics = [
            tf.keras.metrics.BinaryAccuracy(name="accuracy"),
            tf.keras.metrics.AUC(name="auc"),
            tf.keras.metrics.Precision(name="precision"),
            tf.keras.metrics.Recall(name="recall"),
        ]
    else:
        loss    = "categorical_crossentropy"
        metrics = [
            tf.keras.metrics.CategoricalAccuracy(name="accuracy"),
            tf.keras.metrics.AUC(name="auc", multi_label=False),
        ]

    model.compile(
        optimizer=Adam(learning_rate=cfg.FINE_TUNE_LR),
        loss=loss,
        metrics=metrics,
    )


def get_gradcam_layer_name(model: "tf.keras.Model") -> str:
    """
    Detect the correct Grad-CAM target layer name from the actual model graph
    rather than relying on a hard-coded assumption.

    Searches for the last Conv2D-producing layer in the backbone.
    Falls back to cfg.GRADCAM_LAYER_NAME if none is found.
    """
    import tensorflow as tf
    backbone = _get_backbone(model)
    if backbone is None:
        return cfg.GRADCAM_LAYER_NAME

    target = cfg.GRADCAM_LAYER_NAME
    for layer in backbone.layers:
        if isinstance(layer, (tf.keras.layers.Conv2D,)):
            target = layer.name
        # ResNet uses Add + Activation after blocks — conv5_block3_out is the
        # final activation of the last residual block
        if layer.name == "conv5_block3_out":
            return layer.name
    return target


def build_callbacks(monitor: str = cfg.MONITOR_METRIC) -> list:
    """Return the standard callback set for training."""
    import tensorflow as tf

    cfg.CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)

    callbacks = [
        tf.keras.callbacks.ModelCheckpoint(
            filepath=str(cfg.BEST_CHECKPOINT),
            monitor=monitor,
            save_best_only=True,
            save_weights_only=True,
            verbose=1,
        ),
        tf.keras.callbacks.EarlyStopping(
            monitor=monitor,
            patience=cfg.EARLY_STOPPING_PATIENCE,
            restore_best_weights=True,
            verbose=1,
        ),
        tf.keras.callbacks.ReduceLROnPlateau(
            monitor=monitor,
            factor=cfg.REDUCE_LR_FACTOR,
            patience=cfg.REDUCE_LR_PATIENCE,
            min_lr=cfg.REDUCE_LR_MIN,
            verbose=1,
        ),
    ]
    return callbacks
