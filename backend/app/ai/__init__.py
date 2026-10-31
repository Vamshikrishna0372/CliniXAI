"""
CliniXAI Multi-Model Medical AI/XAI Subsystem Package.
"""

from app.ai.registry import get_ai_registry, AIModuleIdentifier, AIModuleConfig
from app.ai.model_loader import get_model_loader, ModelLoader
from app.ai.preprocessing import load_and_preprocess_backend_image
from app.ai.inference import run_inference
from app.ai.gradcam import generate_gradcam_overlay_bytes

__all__ = [
    "get_ai_registry",
    "AIModuleIdentifier",
    "AIModuleConfig",
    "get_model_loader",
    "ModelLoader",
    "load_and_preprocess_backend_image",
    "run_inference",
    "generate_gradcam_overlay_bytes",
]
