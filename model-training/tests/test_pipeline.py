"""
Unit & Pipeline Tests for CliniXAI Phase 7 Deep Learning Training System.

Usage:
    python tests/test_pipeline.py
"""

import os
import sys
import unittest
import numpy as np
from pathlib import Path
from PIL import Image

# bootstrap model-training path
TRAINING_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(TRAINING_ROOT))

import config as cfg

try:
    import tensorflow as tf
    TF_AVAILABLE = True
except ImportError:
    TF_AVAILABLE = False


class TestPhase7Pipeline(unittest.TestCase):

    def setUp(self):
        # Create a temporary RGB PIL image for testing
        self.test_img_dir = TRAINING_ROOT / "tests" / "temp"
        self.test_img_dir.mkdir(parents=True, exist_ok=True)
        self.test_img_path = self.test_img_dir / "test_sample.jpg"

        img = Image.new("RGB", (300, 300), color=(128, 64, 32))
        img.save(self.test_img_path)

    def tearDown(self):
        if self.test_img_path.exists():
            self.test_img_path.unlink()
        if self.test_img_dir.exists():
            try:
                self.test_img_dir.rmdir()
            except OSError:
                pass

    def test_01_config_paths_and_hyperparameters(self):
        """Verify configuration paths and hyperparameter bounds."""
        self.assertEqual(cfg.IMAGE_SIZE, (224, 224))
        self.assertEqual(cfg.NUM_CHANNELS, 3)
        self.assertTrue(cfg.TRAIN_DIR.name == "train")
        self.assertTrue(cfg.VAL_DIR.name == "validation")
        self.assertTrue(cfg.TEST_DIR.name == "test")
        self.assertGreater(cfg.INITIAL_LR, 0)
        self.assertGreater(cfg.FINE_TUNE_LR, 0)

    def test_02_preprocessing_contract(self):
        """Verify preprocessing converts image to (224, 224, 3) float32 array."""
        from scripts.preprocessing import load_and_preprocess

        arr = load_and_preprocess(self.test_img_path)
        self.assertIsInstance(arr, np.ndarray)
        self.assertEqual(arr.shape, (224, 224, 3))
        self.assertEqual(arr.dtype, np.float32)

    def test_03_preprocessing_grayscale_conversion(self):
        """Verify grayscale images are converted to 3-channel RGB array."""
        from scripts.preprocessing import load_and_preprocess

        gray_path = self.test_img_dir / "gray_sample.png"
        gray_img = Image.new("L", (100, 100), color=200)
        gray_img.save(gray_path)

        try:
            arr = load_and_preprocess(gray_path)
            self.assertEqual(arr.shape, (224, 224, 3))
            self.assertEqual(arr.dtype, np.float32)
        finally:
            if gray_path.exists():
                gray_path.unlink()

    def test_04_dataset_validation_missing_dataset_handled(self):
        """Verify dataset validator reports status without crashing."""
        from scripts.validate_dataset import validate_dataset

        report = validate_dataset(raise_on_error=False)
        self.assertIn("status", report)
        self.assertIn("splits", report)
        self.assertIn("classes", report)

    @unittest.skipUnless(TF_AVAILABLE, "TensorFlow not installed in current Python environment")
    def test_05_resnet50_model_building(self):
        """Verify ResNet50 binary and multiclass model shapes."""
        from scripts.model import build_model

        # Binary
        model_binary = build_model(num_classes=2, frozen=True)
        self.assertEqual(model_binary.input_shape, (None, 224, 224, 3))
        self.assertEqual(model_binary.output_shape, (None, 1))

        # Multiclass
        model_multi = build_model(num_classes=4, frozen=True)
        self.assertEqual(model_multi.output_shape, (None, 4))

    @unittest.skipUnless(TF_AVAILABLE, "TensorFlow not installed in current Python environment")
    def test_06_gradcam_layer_detection(self):
        """Verify Grad-CAM target layer detection on built model."""
        from scripts.model import build_model, get_gradcam_layer_name

        model = build_model(num_classes=2, frozen=True)
        layer_name = get_gradcam_layer_name(model)
        self.assertIsInstance(layer_name, str)
        self.assertTrue(len(layer_name) > 0)

    @unittest.skipUnless(TF_AVAILABLE, "TensorFlow not installed in current Python environment")
    def test_07_gradcam_heatmap_computation(self):
        """Verify Grad-CAM returns normalized 224x224 heatmap array."""
        from scripts.model import build_model
        from scripts.preprocessing import load_and_preprocess
        from scripts.gradcam_validation import compute_gradcam

        model = build_model(num_classes=2, frozen=True)
        prep_img = load_and_preprocess(self.test_img_path)

        heatmap, pred_idx, conf = compute_gradcam(model, prep_img)
        self.assertEqual(heatmap.shape, (224, 224))
        self.assertGreaterEqual(np.min(heatmap), 0.0)
        self.assertLessEqual(np.max(heatmap), 1.0)
        self.assertIsInstance(pred_idx, int)
        self.assertIsInstance(conf, float)


if __name__ == "__main__":
    unittest.main()
