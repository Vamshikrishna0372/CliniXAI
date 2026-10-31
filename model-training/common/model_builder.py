"""
Shared Model Architecture Builder for CliniXAI Multi-Model Medical AI.

Supports ResNet50 backbone (and configurable future backbones) with binary,
multiclass, and multilabel classification heads.
"""

import logging
from typing import Tuple, Optional, Any

log = logging.getLogger("model_builder")


def build_module_model(
    num_classes: int,
    classification_mode: str = "multiclass",
    architecture: str = "ResNet50",
    input_shape: Tuple[int, int, int] = (224, 224, 3),
    frozen: bool = True,
    dropout_rate: float = 0.3,
) -> Any:
    """
    Build neural network model according to module configuration.

    Parameters
    ----------
    num_classes         : int
    classification_mode : str — 'binary' | 'multiclass' | 'multilabel'
    architecture        : str — default 'ResNet50'
    input_shape         : (height, width, channels)
    frozen              : bool — freeze backbone weights for Stage 1 transfer learning
    dropout_rate        : float

    Returns
    -------
    tf.keras.Model
    """
    import tensorflow as tf
    from tensorflow.keras import layers, models

    log.info("Building %s backbone (input shape %s, num_classes=%d, mode=%s, frozen=%s)",
             architecture, input_shape, num_classes, classification_mode, frozen)

    if architecture.lower() == "resnet50":
        from tensorflow.keras.applications import ResNet50
        base_model = ResNet50(
            include_top=False,
            weights="imagenet",
            input_shape=input_shape,
        )
    else:
        # Fallback to ResNet50 if unknown architecture specified
        from tensorflow.keras.applications import ResNet50
        base_model = ResNet50(
            include_top=False,
            weights="imagenet",
            input_shape=input_shape,
        )

    base_model.trainable = not frozen

    inputs = layers.Input(shape=input_shape, name="image_input")
    x = base_model(inputs, training=False)
    x = layers.GlobalAveragePooling2D(name="global_avg_pool")(x)
    x = layers.BatchNormalization()(x)
    x = layers.Dropout(dropout_rate, name="head_dropout")(x)

    # Output Layer based on Classification Mode
    if classification_mode == "multilabel":
        outputs = layers.Dense(num_classes, activation="sigmoid", name="predictions")(x)
        loss = "binary_crossentropy"
        metrics = ["accuracy", tf.keras.metrics.AUC(name="auc", multi_label=True)]

    elif classification_mode == "binary":
        outputs = layers.Dense(1, activation="sigmoid", name="predictions")(x)
        loss = "binary_crossentropy"
        metrics = ["accuracy", tf.keras.metrics.AUC(name="auc")]

    else:
        outputs = layers.Dense(num_classes, activation="softmax", name="predictions")(x)
        loss = "categorical_crossentropy"
        metrics = ["accuracy"]
        if num_classes > 2:
            metrics.append(tf.keras.metrics.TopKCategoricalAccuracy(k=min(3, num_classes), name="top_3_acc"))

    model = models.Model(inputs=inputs, outputs=outputs, name=f"clinixai_{architecture.lower()}")

    optimizer = tf.keras.optimizers.Adam(learning_rate=1e-3)
    model.compile(optimizer=optimizer, loss=loss, metrics=metrics)

    return model


def get_gradcam_layer_name(model: Any, default_name: str = "conv5_block3_out") -> str:
    """Find target convolutional layer for Grad-CAM."""
    try:
        layer = model.get_layer(default_name)
        return layer.name
    except Exception:
        # Find last Conv2D layer in base model
        for l in reversed(model.layers):
            if hasattr(l, "layers"):  # nested model
                for nl in reversed(l.layers):
                    if "conv" in nl.name.lower():
                        return nl.name
            elif "conv" in l.name.lower():
                return l.name
    return default_name
