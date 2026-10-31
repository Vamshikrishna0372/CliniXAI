"""
CliniXAI Phase 7 — Grad-CAM Explainable AI (XAI) Validation Script.

Implements Gradient-weighted Class Activation Mapping (Grad-CAM) for ResNet50.

Pipeline
--------
Input image
→ Preprocessing (exact same contract as model: resnet50.preprocess_input)
→ Forward pass to target conv layer & output predictions
→ Compute gradients of target class output w.r.t. conv layer feature maps
→ Pool gradients across spatial dimensions (global average pooling)
→ Weight feature maps by gradient importances
→ ReLU activation (keep positive contributions only)
→ Upsample heatmap to 224x224 & normalize [0, 1]
→ Color map overlay (JET) on original image

Safety & Clinical Wording
-------------------------
Grad-CAM heatmaps highlight regions that contributed to the model prediction.
They do NOT prove causality, diagnostic validity, or clinical correctness.
They must be interpreted by a qualified medical professional.
"""

import sys
import json
import logging
from pathlib import Path
from typing import Optional, Tuple, Union

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent.parent))
import config as cfg

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
log = logging.getLogger("gradcam")


def compute_gradcam(
    model,
    preprocessed_img: np.ndarray,
    target_layer_name: Optional[str] = None,
    pred_index: Optional[int] = None,
) -> Tuple[np.ndarray, int, float]:
    """
    Compute Grad-CAM heatmap for a single preprocessed image.

    Parameters
    ----------
    model : tf.keras.Model
    preprocessed_img : np.ndarray
        Single preprocessed image of shape (224, 224, 3) or batch (1, 224, 224, 3).
    target_layer_name : str, optional
        Name of final conv layer. If None, auto-detected from model.
    pred_index : int, optional
        Class index to explain. If None, uses top predicted class.

    Returns
    -------
    heatmap : np.ndarray shape (224, 224), float32 range [0, 1]
    class_idx : int predicted/target class index
    confidence : float score for target class
    """
    import tensorflow as tf
    from scripts.model import get_gradcam_layer_name, _get_backbone

    if preprocessed_img.ndim == 3:
        img_batch = np.expand_dims(preprocessed_img, axis=0)
    else:
        img_batch = preprocessed_img

    if target_layer_name is None:
        target_layer_name = get_gradcam_layer_name(model)

    # Find the target layer in backbone or model
    backbone = _get_backbone(model)
    target_model = backbone if backbone is not None else model

    try:
        conv_layer = target_model.get_layer(target_layer_name)
    except ValueError:
        log.warning("Layer '%s' not found. Searching for last Conv2D layer...", target_layer_name)
        conv_layers = [l for l in target_model.layers if isinstance(l, tf.keras.layers.Conv2D)]
        if not conv_layers:
            raise RuntimeError("No Conv2D layer found in model for Grad-CAM.")
        conv_layer = conv_layers[-1]
        target_layer_name = conv_layer.name
        log.info("Using target conv layer: %s", target_layer_name)

    # Construct grad model mapping inputs to [conv_output, final_output]
    if backbone is not None:
        # Construct model from backbone input to target layer & final output
        grad_model = tf.keras.Model(
            inputs=model.inputs,
            outputs=[conv_layer.output, model.output]
        )
    else:
        grad_model = tf.keras.Model(
            inputs=model.inputs,
            outputs=[conv_layer.output, model.output]
        )

    with tf.GradientTape() as tape:
        conv_outputs, predictions = grad_model(img_batch)
        if pred_index is None:
            if predictions.shape[-1] == 1:
                # Binary classification
                pred_index = 0
                target_score = predictions[0][0]
                confidence = float(target_score) if target_score >= 0.5 else float(1.0 - target_score)
            else:
                pred_index = tf.argmax(predictions[0])
                target_score = predictions[0][pred_index]
                confidence = float(target_score)
        else:
            if predictions.shape[-1] == 1:
                target_score = predictions[0][0]
                confidence = float(target_score)
            else:
                target_score = predictions[0][pred_index]
                confidence = float(target_score)

    # Compute gradients of target output w.r.t. conv outputs
    grads = tape.gradient(target_score, conv_outputs)

    # Global average pooling of gradients
    pooled_grads = tf.reduce_mean(grads, axis=(0, 1, 2))

    # Weight feature maps by pooled gradients
    conv_outputs = conv_outputs[0]
    heatmap = conv_outputs @ pooled_grads[..., tf.newaxis]
    heatmap = tf.squeeze(heatmap)

    # Apply ReLU (only positive contributions)
    heatmap = tf.maximum(heatmap, 0.0)

    # Normalize heatmap between 0 and 1
    max_val = tf.math.reduce_max(heatmap)
    if max_val > 0:
        heatmap /= max_val

    heatmap_np = heatmap.numpy()

    # Resize heatmap to target 224x224 shape
    heatmap_pil = Image.fromarray(np.uint8(heatmap_np * 255)).resize(
        (cfg.IMAGE_SIZE[1], cfg.IMAGE_SIZE[0]), resample=Image.BILINEAR
    )
    heatmap_norm = np.array(heatmap_pil, dtype=np.float32) / 255.0

    return heatmap_norm, int(pred_index), confidence


def overlay_heatmap(
    original_img_path_or_pil: Union[str, Path, Image.Image],
    heatmap: np.ndarray,
    alpha: float = 0.4,
) -> Tuple[Image.Image, Image.Image]:
    """
    Overlay a Grad-CAM heatmap onto the original image.

    Returns
    -------
    heatmap_colored : PIL.Image  (JET colormapped heatmap)
    overlay_img     : PIL.Image  (blended original + heatmap)
    """
    import matplotlib.cm as cm

    if isinstance(original_img_path_or_pil, (str, Path)):
        orig = Image.open(original_img_path_or_pil).convert("RGB")
    else:
        orig = original_img_path_or_pil.convert("RGB")

    orig = orig.resize((cfg.IMAGE_SIZE[1], cfg.IMAGE_SIZE[0]), Image.BILINEAR)

    # Apply JET colormap
    jet = cm.get_cmap("jet")
    jet_colors = jet(heatmap)  # shape (224, 224, 4)
    jet_img_np = np.uint8(jet_colors[:, :, :3] * 255)
    heatmap_colored = Image.fromarray(jet_img_np)

    # Blend original and heatmap overlay
    overlay_np = np.uint8(np.array(orig) * (1.0 - alpha) + jet_img_np * alpha)
    overlay_img = Image.fromarray(overlay_np)

    return heatmap_colored, overlay_img


def run_gradcam_validation() -> None:
    """Run Grad-CAM generation on test set samples and output visual artifact grids."""
    import tensorflow as tf
    from scripts.preprocessing import load_and_preprocess
    from scripts.model import build_model

    log.info("=" * 60)
    log.info("CliniXAI Phase 7 — Grad-CAM Explainable AI Validation")
    log.info("=" * 60)

    cfg.GRADCAM_DIR.mkdir(parents=True, exist_ok=True)

    if not cfg.CLASS_NAMES_FILE.exists():
        log.error("class_names.json missing. Run train.py first.")
        sys.exit(1)

    with open(cfg.CLASS_NAMES_FILE) as f:
        class_names = json.load(f)

    if cfg.EXPORTED_MODEL.exists():
        log.info("Loading model: %s", cfg.EXPORTED_MODEL)
        model = tf.keras.models.load_model(str(cfg.EXPORTED_MODEL))
    elif cfg.BEST_CHECKPOINT.exists():
        log.info("Loading weights from checkpoint: %s", cfg.BEST_CHECKPOINT)
        model = build_model(len(class_names), frozen=False)
        model.load_weights(str(cfg.BEST_CHECKPOINT))
    else:
        log.error("No trained model found.")
        sys.exit(1)

    # Scan test split for sample images
    test_dir = cfg.TEST_DIR
    if not test_dir.exists():
        log.error("Test directory missing: %s", test_dir)
        sys.exit(1)

    sample_count = 0
    for cls in class_names:
        cls_dir = test_dir / cls
        if not cls_dir.exists():
            continue
        files = [
            f for f in cls_dir.iterdir()
            if f.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp"}
        ][: cfg.GRADCAM_SAMPLE_COUNT]

        for img_path in files:
            try:
                prep_img = load_and_preprocess(img_path)
                heatmap, pred_idx, conf = compute_gradcam(model, prep_img)
                pred_cls = class_names[pred_idx] if pred_idx < len(class_names) else str(pred_idx)

                _, overlay = overlay_heatmap(img_path, heatmap)

                out_name = f"gradcam_{cls}_vs_{pred_cls}_{img_path.stem}.png"
                out_path = cfg.GRADCAM_DIR / out_name
                overlay.save(out_path)
                log.info("Saved Grad-CAM overlay: %s (True: %s | Pred: %s | Conf: %.2f)",
                         out_name, cls, pred_cls, conf)
                sample_count += 1
            except Exception as e:
                log.error("Failed Grad-CAM for %s: %s", img_path.name, e)

    log.info("")
    log.info("Grad-CAM validation finished. %d heatmaps generated under %s",
             sample_count, cfg.GRADCAM_DIR)


if __name__ == "__main__":
    run_gradcam_validation()
