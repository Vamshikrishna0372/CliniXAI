"""
Backend Image Preprocessing Module for CliniXAI Multi-Model Architecture.

Maintains strict equality with Phase 7/8 training contracts while supporting
module-configurable input dimensions and preprocessing strategies:
- Resizes to module target size (default (224, 224)) RGB using Bilinear resampling
- Converts to float32 NumPy tensor shape (H, W, 3)
- Applies module preprocessing (e.g. resnet50.preprocess_input)
"""

import io
from pathlib import Path
from typing import Union, Tuple, Optional
import numpy as np
from PIL import Image

TARGET_SIZE = (224, 224)


def load_and_preprocess_backend_image(
    image_input: Union[str, Path, bytes, Image.Image],
    target_size: Tuple[int, int] = TARGET_SIZE,
    strategy: str = "resnet50",
) -> np.ndarray:
    """
    Load image from bytes, path, or PIL Image and preprocess for specified target size & strategy.

    Parameters
    ----------
    image_input : str | Path | bytes | PIL.Image.Image
    target_size  : (height, width) — default (224, 224)
    strategy     : str — default 'resnet50'

    Returns
    -------
    np.ndarray shape (H, W, 3), dtype float32
    """
    if isinstance(image_input, bytes):
        img = Image.open(io.BytesIO(image_input))
    elif isinstance(image_input, (str, Path)):
        img = Image.open(image_input)
    else:
        img = image_input  # PIL Image

    # 1. Force RGB
    if img.mode != "RGB":
        img = img.convert("RGB")

    # 2. Resize (PIL uses (width, height))
    pil_size = (target_size[1], target_size[0])
    img = img.resize(pil_size, Image.BILINEAR)

    # 3. Convert to float32 array
    arr = np.array(img, dtype=np.float32)

    # 4. Strategy preprocessing
    if strategy.lower() == "resnet50":
        try:
            from tensorflow.keras.applications.resnet50 import preprocess_input
            arr = preprocess_input(arr)
        except ImportError:
            # Fallback pure NumPy Caffe ResNet50 preprocessing
            arr = arr[..., ::-1]
            arr[..., 0] -= 103.939
            arr[..., 1] -= 116.779
            arr[..., 2] -= 123.68
    elif strategy.lower() in {"scale_0_1", "normalize"}:
        arr = arr / 255.0
    elif strategy.lower() in {"scale_minus1_1", "mobilenet"}:
        arr = (arr / 127.5) - 1.0

    return arr
