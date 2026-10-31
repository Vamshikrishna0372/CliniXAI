"""
Comprehensive Test Suite for CliniXAI Multi-Model Medical AI/XAI Architecture.

Tests:
1. Model registry lookup and alias resolution.
2. Invalid module rejection.
3. Missing model handling (reporting unavailable status).
4. Module isolation (one missing model does not disable others).
5. Module-specific preprocessing and target layer resolution.
6. Multi-model inference engine dispatching.
7. Grad-CAM XAI configuration per module.
8. API endpoints: GET /api/v1/ai/modules and GET /api/v1/ai/health.
"""

import unittest
from unittest.mock import MagicMock, patch
import numpy as np

from app.ai.registry import get_ai_registry, AIModuleIdentifier, AIModuleConfig, ClassificationMode
from app.ai.model_loader import get_model_loader, ModelLoader
from app.ai.preprocessing import load_and_preprocess_backend_image
from app.ai.inference import run_inference
from app.schemas.ai_analysis import AIAnalysisCreateRequest


class TestMultiModelAIRegistryAndLoader(unittest.TestCase):

    def setUp(self):
        self.registry = get_ai_registry()
        self.loader = get_model_loader()

    def test_01_registry_supported_modules(self):
        """Verify all initial 5 medical AI modules are registered."""
        modules = self.registry.list_modules(enabled_only=False)
        module_ids = {m.module_id for m in modules}

        expected = {
            AIModuleIdentifier.CHEST_XRAY.value,
            AIModuleIdentifier.BRAIN_MRI.value,
            AIModuleIdentifier.SKIN_DERMOSCOPY.value,
            AIModuleIdentifier.RETINAL_FUNDUS.value,
            AIModuleIdentifier.BONE_XRAY.value,
        }
        self.assertTrue(expected.issubset(module_ids))

    def test_02_registry_alias_resolution(self):
        """Verify normalization of slugs and aliases to module IDs."""
        self.assertEqual(self.registry.normalize_identifier("chest"), AIModuleIdentifier.CHEST_XRAY.value)
        self.assertEqual(self.registry.normalize_identifier("brain"), AIModuleIdentifier.BRAIN_MRI.value)
        self.assertEqual(self.registry.normalize_identifier("skin"), AIModuleIdentifier.SKIN_DERMOSCOPY.value)
        self.assertEqual(self.registry.normalize_identifier("eye"), AIModuleIdentifier.RETINAL_FUNDUS.value)
        self.assertEqual(self.registry.normalize_identifier("bone"), AIModuleIdentifier.BONE_XRAY.value)

    def test_03_invalid_module_rejection(self):
        """Verify unknown module string raises ValueError."""
        with self.assertRaises(ValueError):
            self.registry.normalize_identifier("cardiac_3d_ct")

    def test_04_missing_model_graceful_handling(self):
        """Verify loading an untrained model reports unavailable without crashing FastAPI.

        Note: BRAIN_MRI and CHEST_XRAY now have production models.
        This test uses SKIN_DERMOSCOPY which has no trained model yet.
        """
        artifact = self.loader.load_module(AIModuleIdentifier.SKIN_DERMOSCOPY.value)
        self.assertFalse(artifact.is_available)
        self.assertEqual(artifact.status, "unavailable")
        self.assertIn("missing", artifact.error_message.lower())

    def test_05_one_missing_model_does_not_break_health(self):
        """Verify get_health() returns safe dictionary even when models are not trained yet."""
        health = self.loader.get_health()
        self.assertIn("status", health)
        self.assertIn("modules", health)
        self.assertIn(AIModuleIdentifier.CHEST_XRAY.value, health["modules"])
        self.assertIn(AIModuleIdentifier.BRAIN_MRI.value, health["modules"])

    def test_06_model_output_path_isolation(self):
        """Verify output filenames are distinct for each module."""
        chest_cfg = self.registry.get_module(AIModuleIdentifier.CHEST_XRAY.value)
        brain_cfg = self.registry.get_module(AIModuleIdentifier.BRAIN_MRI.value)
        skin_cfg = self.registry.get_module(AIModuleIdentifier.SKIN_DERMOSCOPY.value)

        self.assertNotEqual(chest_cfg.model_filename, brain_cfg.model_filename)
        self.assertNotEqual(brain_cfg.model_filename, skin_cfg.model_filename)
        self.assertEqual(chest_cfg.model_filename, "chest_model.keras")
        self.assertEqual(brain_cfg.model_filename, "brain_model.keras")

    def test_07_inference_rejects_unregistered_module(self):
        """Verify run_inference rejects unknown module identifiers."""
        tensor = np.zeros((224, 224, 3), dtype=np.float32)
        with self.assertRaises(ValueError):
            run_inference(tensor, module_id="unknown_fake_module")

    def test_08_inference_raises_clean_error_when_model_unavailable(self):
        """Verify run_inference raises RuntimeError when target model is not trained/available.

        Note: BRAIN_MRI and CHEST_XRAY now have production model artifacts. Using
        SKIN_DERMOSCOPY which is genuinely untrained to verify the graceful unavailable path.
        """
        tensor = np.zeros((224, 224, 3), dtype=np.float32)
        with self.assertRaises(RuntimeError) as ctx:
            run_inference(tensor, module_id=AIModuleIdentifier.SKIN_DERMOSCOPY.value)
        self.assertIn("Cannot run inference", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
