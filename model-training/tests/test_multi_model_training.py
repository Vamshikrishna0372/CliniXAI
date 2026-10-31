"""
Unit Tests for CliniXAI Multi-Model Model-Training Workspace.
"""

import sys
import unittest
from pathlib import Path

TRAINING_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(TRAINING_ROOT))

from common.config_base import get_module_config, SUPPORTED_MODULES
from common.dataset_validator import validate_module_dataset


class TestMultiModelTrainingWorkspace(unittest.TestCase):

    def test_01_all_modules_have_valid_configurations(self):
        """Verify all 5 modules (chest, brain, skin, eye, bone) resolve valid configurations."""
        self.assertEqual(len(SUPPORTED_MODULES), 5)
        for slug in SUPPORTED_MODULES:
            cfg = get_module_config(slug)
            self.assertEqual(cfg.MODULE_SLUG, slug)
            self.assertTrue(hasattr(cfg, "MODEL_FILENAME"))
            self.assertTrue(hasattr(cfg, "DATASET_DIR"))
            self.assertTrue(hasattr(cfg, "OUTPUTS_DIR"))
            self.assertTrue(cfg.MODEL_FILENAME.endswith(".keras"))

    def test_02_output_file_isolation(self):
        """Verify that each module has a distinct model output filename."""
        filenames = set()
        for slug in SUPPORTED_MODULES:
            cfg = get_module_config(slug)
            filenames.add(cfg.MODEL_FILENAME)
        self.assertEqual(len(filenames), 5)

    def test_03_dataset_directories_exist(self):
        """Verify that empty dataset folders exist for all 5 modules with .gitkeep."""
        for slug in SUPPORTED_MODULES:
            cfg = get_module_config(slug)
            dataset_path = Path(cfg.DATASET_DIR)
            self.assertTrue(dataset_path.exists(), f"Dataset dir missing for {slug}")
            gitkeep = dataset_path / ".gitkeep"
            self.assertTrue(gitkeep.exists(), f".gitkeep missing in dataset dir for {slug}")

    def test_04_outputs_directories_exist(self):
        """Verify that outputs folders exist for all 5 modules with .gitkeep."""
        for slug in SUPPORTED_MODULES:
            cfg = get_module_config(slug)
            outputs_path = Path(cfg.OUTPUTS_DIR)
            self.assertTrue(outputs_path.exists(), f"Outputs dir missing for {slug}")
            gitkeep = outputs_path / ".gitkeep"
            self.assertTrue(gitkeep.exists(), f".gitkeep missing in outputs dir for {slug}")

    def test_05_dataset_validator_runs_gracefully_when_empty(self):
        """Verify dataset validator handles empty dataset folder without crashing."""
        for slug in SUPPORTED_MODULES:
            cfg = get_module_config(slug)
            report = validate_module_dataset(cfg, raise_on_error=False)
            self.assertIn("status", report)
            self.assertIn("classes", report)


if __name__ == "__main__":
    unittest.main()
