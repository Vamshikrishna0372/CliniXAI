"""
CliniXAI Phase 7 — Image Preprocessing.

This module defines the SINGLE authoritative preprocessing contract.
Phase 8 FastAPI inference MUST reproduce the exact same logic.

Contract
--------
Input  : file path or PIL Image (any channel count)
Output : np.ndarray shape (224, 224, 3), dtype float32
         values after tf.keras.applications.resnet50.preprocess_input
         (BGR channel order, mean-subtracted by [103.939, 116.779, 123.68])

Resize strategy : RESIZE (no padding, no cropping)
    Rationale: keeps full image context; distortion is minimal at 224×224.
    Phase 8 must use the same strategy — see config.RESIZE_STRATEGY.
"""

import sys
import numpy as np
from pathlib import Path
from typing import Union
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent.parent))
import config as cfg


def load_and_preprocess(
    image_source: Union[str, Path, "Image.Image"],
    *,
    target_size: tuple = cfg.IMAGE_SIZE,
) -> np.ndarray:
    """
    Load an image from path (or accept a PIL Image) and preprocess it for
    ResNet50 inference.

    Steps
    -----
    1. Open image and convert to RGB (handles grayscale, RGBA, palette modes).
    2. Resize to target_size using BILINEAR resampling.
    3. Convert to float32 numpy array shaped (H, W, 3).
    4. Apply ResNet50 preprocessing (RGB→BGR, mean subtraction).

    Parameters
    ----------
    image_source : str | Path | PIL.Image.Image
    target_size  : (height, width) — default cfg.IMAGE_SIZE = (224, 224)

    Returns
    -------
    np.ndarray  shape (H, W, 3)  dtype float32
    """
    if isinstance(image_source, (str, Path)):
        img = Image.open(image_source)
    else:
        img = image_source  # already a PIL Image

    # ── 1. Force RGB (handles grayscale L, LA, RGBA, P modes) ──────────────
    if img.mode != "RGB":
        img = img.convert("RGB")

    # ── 2. Resize ───────────────────────────────────────────────────────────
    # target_size is (height, width) but PIL.resize wants (width, height)
    pil_size = (target_size[1], target_size[0])
    img = img.resize(pil_size, Image.BILINEAR)

    # ── 3. To numpy float32 ─────────────────────────────────────────────────
    arr = np.array(img, dtype=np.float32)          # (H, W, 3)  range [0, 255]

    # ── 4. ResNet50 preprocessing ───────────────────────────────────────────
    try:
        from tensorflow.keras.applications.resnet50 import preprocess_input
        arr = preprocess_input(arr)
    except ImportError:
        # Pure numpy ResNet50 Caffe-style preprocessing fallback if TF is not installed
        # RGB -> BGR
        arr = arr[..., ::-1]
        # Zero-center by ImageNet means [B, G, R]
        arr[..., 0] -= 103.939
        arr[..., 1] -= 116.779
        arr[..., 2] -= 123.68

    return arr


def preprocess_batch(
    paths: list,
    *,
    target_size: tuple = cfg.IMAGE_SIZE,
) -> np.ndarray:
    """
    Preprocess a list of image paths into a batch array.

    Returns
    -------
    np.ndarray  shape (N, H, W, 3)  dtype float32
    """
    batch = [load_and_preprocess(p, target_size=target_size) for p in paths]
    return np.stack(batch, axis=0)


def get_tf_preprocessing_layer():
    """Return Keras preprocessing layer if TensorFlow is present."""
    import tensorflow as tf
    from tensorflow.keras.applications.resnet50 import preprocess_input
    return tf.keras.layers.Lambda(
        lambda x: preprocess_input(x),
        name="resnet50_preprocessing",
    )
