"""
Backend Grad-CAM Explainable AI (XAI) Engine for CliniXAI Multi-Model Medical Architecture.

Generates JET colormap activation overlays for registered medical imaging model predictions.
"""

import io
import logging
import numpy as np
from PIL import Image
from typing import Tuple, Optional, Union

from app.core.logging import logger
from app.ai.model_loader import get_model_loader
from app.ai.registry import get_ai_registry
from app.ai.preprocessing import TARGET_SIZE


def generate_gradcam_overlay_bytes(
    original_image_input: Union[bytes, Image.Image],
    preprocessed_tensor: np.ndarray,
    module_id: str = "CHEST_XRAY",
    target_class_index: Optional[int] = None,
) -> Tuple[bytes, str]:
    """
    Generate Grad-CAM activation heatmap overlay as PNG bytes for specified medical module.

    Parameters
    ----------
    original_image_input : bytes | PIL.Image.Image
    preprocessed_tensor  : np.ndarray shape (H, W, C)
    module_id           : str — Module identifier or slug
    target_class_index   : int, optional

    Returns
    -------
    (png_bytes, target_layer_name)
    """
    registry = get_ai_registry()
    norm_id = registry.normalize_identifier(module_id)
    mod_cfg = registry.get_module(norm_id)

    loader = get_model_loader()
    artifact = loader.load_module(norm_id)

    if not artifact.is_available:
        raise RuntimeError(f"Cannot generate Grad-CAM for module '{norm_id}': {artifact.error_message}")

    import tensorflow as tf
    import matplotlib.cm as cm

    model = artifact.model
    target_layer_name = artifact.metadata.get("gradcam_target_layer", mod_cfg.gradcam_target_layer)

    if preprocessed_tensor.ndim == 3:
        img_batch = np.expand_dims(preprocessed_tensor, axis=0)
    else:
        img_batch = preprocessed_tensor

    # Locate conv layer & model owner
    target_owner = model
    conv_layer = None

    try:
        conv_layer = model.get_layer(target_layer_name)
    except Exception:
        # Check inside nested submodel layers (e.g. resnet50 backbone)
        for layer in model.layers:
            if hasattr(layer, "get_layer"):
                try:
                    conv_layer = layer.get_layer(target_layer_name)
                    target_owner = layer
                    break
                except Exception:
                    pass

    if conv_layer is None:
        # Search recursively for any conv layer ending in target_layer_name or fallback to last conv layer
        def find_conv_layers(m):
            found = []
            for l in m.layers:
                if "conv" in l.name.lower():
                    found.append((m, l))
                elif hasattr(l, "layers"):
                    found.extend(find_conv_layers(l))
            return found

        all_convs = find_conv_layers(model)
        if all_convs:
            target_owner, conv_layer = all_convs[-1]
            target_layer_name = conv_layer.name
        else:
            raise RuntimeError(f"No conv layer found in model for module '{norm_id}' Grad-CAM.")

    # Compute activation map & gradients
    try:
        if target_owner == model:
            grad_model = tf.keras.Model(
                inputs=model.inputs,
                outputs=[conv_layer.output, model.output]
            )
            with tf.GradientTape() as tape:
                conv_outputs, predictions = grad_model(img_batch)
                if target_class_index is None:
                    if predictions.shape[-1] == 1:
                        target_score = predictions[0][0]
                    else:
                        target_class_index = int(tf.argmax(predictions[0]))
                        target_score = predictions[0][target_class_index]
                else:
                    if predictions.shape[-1] == 1:
                        target_score = predictions[0][0]
                    else:
                        target_score = predictions[0][target_class_index]
        else:
            # Target layer is inside nested submodel (e.g. resnet50)
            grad_model = tf.keras.Model(
                inputs=target_owner.inputs,
                outputs=[conv_layer.output, target_owner.output]
            )
            top_layers = model.layers[model.layers.index(target_owner) + 1:]
            with tf.GradientTape() as tape:
                conv_outputs, sub_outputs = grad_model(img_batch)
                x = sub_outputs
                for top_l in top_layers:
                    x = top_l(x)
                predictions = x
                if target_class_index is None:
                    if predictions.shape[-1] == 1:
                        target_score = predictions[0][0]
                    else:
                        target_class_index = int(tf.argmax(predictions[0]))
                        target_score = predictions[0][target_class_index]
                else:
                    if predictions.shape[-1] == 1:
                        target_score = predictions[0][0]
                    else:
                        target_score = predictions[0][target_class_index]

        grads = tape.gradient(target_score, conv_outputs)
        pooled_grads = tf.reduce_mean(grads, axis=(0, 1, 2))

        conv_outputs = conv_outputs[0]
        heatmap = conv_outputs @ pooled_grads[..., tf.newaxis]
        heatmap = tf.squeeze(heatmap)

        heatmap = tf.maximum(heatmap, 0.0)
        max_val = tf.math.reduce_max(heatmap)
        if max_val > 0:
            heatmap /= max_val

        heatmap_np = heatmap.numpy()
    except Exception as e:
        logger.warning("Grad-CAM gradient computation failed for %s: %s", norm_id, e)
        raise RuntimeError(f"Grad-CAM generation error for module '{norm_id}': {e}")

    target_h, target_w = mod_cfg.input_shape[0], mod_cfg.input_shape[1]

    # Resize heatmap to target input size
    heatmap_pil = Image.fromarray(np.uint8(heatmap_np * 255)).resize(
        (target_w, target_h), resample=Image.BILINEAR
    )
    heatmap_norm = np.array(heatmap_pil, dtype=np.float32) / 255.0

    # Load original image
    if isinstance(original_image_input, bytes):
        orig = Image.open(io.BytesIO(original_image_input)).convert("RGB")
    else:
        orig = original_image_input.convert("RGB")

    orig = orig.resize((target_w, target_h), Image.BILINEAR)

    # Apply JET colormap overlay
    try:
        import matplotlib as mpl
        jet = mpl.colormaps["jet"]
    except Exception:
        jet = cm.get_cmap("jet")
    jet_colors = jet(heatmap_norm)
    jet_img_np = np.uint8(jet_colors[:, :, :3] * 255)

    alpha = 0.4
    overlay_np = np.uint8(np.array(orig) * (1.0 - alpha) + jet_img_np * alpha)
    overlay_img = Image.fromarray(overlay_np)

    output_buffer = io.BytesIO()
    overlay_img.save(output_buffer, format="PNG")
    png_bytes = output_buffer.getvalue()

    return png_bytes, target_layer_name

