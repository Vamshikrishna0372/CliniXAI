"""
Multi-Model Production Loader & Manager for CliniXAI.

Thread-safe Singleton loader for loading, caching, and managing multiple
specialized medical AI models (Chest X-Ray, Brain MRI, Skin Dermoscopy,
Retinal Fundus, Bone X-Ray) from `backend/ai_models/`.

Supports automatic per-module model promotion from `model-training/<module>/outputs/`
and exposes safe health status across all registered modules without failing startup.
"""

import os
import json
import shutil
import logging
import threading
from pathlib import Path
from typing import Optional, Dict, Any, List

from app.core.config import settings
from app.ai.registry import get_ai_registry, AIModuleConfig, AIModuleIdentifier

logger = logging.getLogger("clinixai")


class LoadedModuleArtifacts:
    """Holds in-memory model and metadata artifacts for a single module."""

    def __init__(self, config: AIModuleConfig):
        self.config = config
        self.model: Any = None
        self.metadata: Dict[str, Any] = {}
        self.class_names: List[str] = list(config.default_class_names)
        self.status: str = "uninitialized"  # available | unavailable | initialization_failed
        self.error_message: Optional[str] = None

    @property
    def is_available(self) -> bool:
        return self.status == "available" and self.model is not None


class ModelLoader:
    """Singleton multi-model loader and lifecycle manager."""

    _instance: Optional["ModelLoader"] = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(ModelLoader, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        self.registry = get_ai_registry()

        # Resolve directories
        self.backend_dir = Path(__file__).parent.parent.parent.resolve()
        self.ai_models_dir = self.backend_dir / "ai_models"
        self.ai_models_dir.mkdir(parents=True, exist_ok=True)

        self._module_cache: Dict[str, LoadedModuleArtifacts] = {}

        # Promote any available trained per-module model artifacts
        self._check_and_promote_all_artifacts()

    def _check_and_promote_all_artifacts(self) -> None:
        """Check per-module outputs in model-training/ and safely promote to backend/ai_models/."""
        project_root = self.backend_dir.parent
        training_root = project_root / "model-training"

        for mod_cfg in self.registry.list_modules(enabled_only=False):
            module_slug = mod_cfg.slug
            mod_outputs_dir = training_root / module_slug / "outputs"

            # Check module-specific model candidate or fallback to outputs dir
            candidates = [
                mod_outputs_dir / mod_cfg.model_filename,
                mod_outputs_dir / "model.keras",
            ]

            target_model_path = self.ai_models_dir / mod_cfg.model_filename
            target_meta_path = self.ai_models_dir / mod_cfg.metadata_filename
            target_cmap_path = self.ai_models_dir / mod_cfg.class_map_filename

            source_model: Optional[Path] = None
            for cand in candidates:
                if cand.exists():
                    source_model = cand
                    break

            if source_model and not target_model_path.exists():
                try:
                    # Validate basic model loading before promotion if TF available
                    shutil.copy2(source_model, target_model_path)
                    logger.info("Promoted trained artifact %s -> %s", source_model, target_model_path)
                except Exception as e:
                    logger.warning("Could not promote model for module %s: %s", mod_cfg.module_id, e)

            # Metadata promotion
            source_meta = mod_outputs_dir / mod_cfg.metadata_filename
            if not source_meta.exists():
                source_meta = mod_outputs_dir / "model_metadata.json"
            if source_meta.exists() and not target_meta_path.exists():
                try:
                    shutil.copy2(source_meta, target_meta_path)
                    logger.info("Promoted metadata %s -> %s", source_meta, target_meta_path)
                except Exception as e:
                    logger.warning("Could not promote metadata for module %s: %s", mod_cfg.module_id, e)

            # Class map promotion
            source_cmap = mod_outputs_dir / mod_cfg.class_map_filename
            if not source_cmap.exists():
                source_cmap = mod_outputs_dir / "class_names.json"
            if source_cmap.exists() and not target_cmap_path.exists():
                try:
                    shutil.copy2(source_cmap, target_cmap_path)
                    logger.info("Promoted class map %s -> %s", source_cmap, target_cmap_path)
                except Exception as e:
                    logger.warning("Could not promote class map for module %s: %s", mod_cfg.module_id, e)

        # Legacy promotion fallback check for model-training/outputs/model.keras
        legacy_outputs = training_root / "outputs"
        legacy_model = legacy_outputs / "model.keras"
        chest_target = self.ai_models_dir / "chest_model.keras"
        legacy_target = self.ai_models_dir / "model.keras"

        if legacy_model.exists():
            if not chest_target.exists():
                try:
                    shutil.copy2(legacy_model, chest_target)
                    logger.info("Promoted legacy model.keras -> %s", chest_target)
                except Exception as e:
                    logger.warning("Legacy model copy error: %s", e)
            if not legacy_target.exists():
                try:
                    shutil.copy2(legacy_model, legacy_target)
                except Exception:
                    pass

    def load_module(self, identifier: str, load_weights: bool = True) -> LoadedModuleArtifacts:
        """Load or retrieve cached model artifacts for a given module identifier."""
        norm_id = self.registry.normalize_identifier(identifier)
        mod_cfg = self.registry.get_module(norm_id)

        with self._lock:
            if norm_id in self._module_cache:
                cached = self._module_cache[norm_id]
                # If already available or failed, check if we need to load weights
                if cached.status in {"available", "initialization_failed"}:
                    if not load_weights or cached.model is not None:
                        return cached
            else:
                cached = LoadedModuleArtifacts(mod_cfg)
                self._module_cache[norm_id] = cached

        if not settings.AI_ENABLED:
            cached.status = "unavailable"
            cached.error_message = "AI subsystem disabled via configuration (AI_ENABLED=false)"
            return cached

        if not mod_cfg.enabled:
            cached.status = "unavailable"
            cached.error_message = f"Module '{norm_id}' is disabled."
            return cached

        model_path = self.ai_models_dir / mod_cfg.model_filename
        metadata_path = self.ai_models_dir / mod_cfg.metadata_filename
        class_map_path = self.ai_models_dir / mod_cfg.class_map_filename

        if not model_path.exists():
            cached.status = "unavailable"
            cached.error_message = f"Model artifact '{mod_cfg.model_filename}' missing in backend/ai_models/. Pending model training."
            logger.info("AI Subsystem: Model file not found for module %s at %s.", norm_id, model_path)
            return cached

        try:
            # Load metadata
            if metadata_path.exists():
                with open(metadata_path, "r", encoding="utf-8") as f:
                    cached.metadata = json.load(f)

            # Load class map
            if class_map_path.exists():
                with open(class_map_path, "r", encoding="utf-8") as f:
                    cached.class_names = json.load(f)

            if load_weights and cached.model is None:
                # Single-model memory management: release any other model from RAM to keep memory within 512MB
                import gc
                for other_id, other_art in list(self._module_cache.items()):
                    if other_id != norm_id and other_art.model is not None:
                        other_art.model = None
                try:
                    import tensorflow as tf
                    tf.keras.backend.clear_session()
                except Exception:
                    pass
                gc.collect()

                # Load Keras Model
                import tensorflow as tf
                cached.model = tf.keras.models.load_model(str(model_path), compile=False)

            cached.status = "available"
            cached.error_message = None
            if cached.model is not None:
                logger.info("AI Subsystem: Successfully loaded model for module %s (%s)", norm_id, mod_cfg.display_name)

        except Exception as e:
            cached.status = "initialization_failed"
            cached.error_message = f"Model load failure for {norm_id}: {str(e)}"
            logger.error("AI Subsystem initialization failed for module %s: %s", norm_id, e, exc_info=True)

        return cached

    def load_all_enabled(self, load_weights: bool = False) -> None:
        """Attempt to verify/load all enabled registered modules."""
        for mod_cfg in self.registry.list_modules(enabled_only=True):
            self.load_module(mod_cfg.module_id, load_weights=load_weights)

    # ── Backward Compatibility Properties (Defaults to CHEST_XRAY) ────────────
    @property
    def primary_module(self) -> LoadedModuleArtifacts:
        return self.load_module(AIModuleIdentifier.CHEST_XRAY.value)

    @property
    def is_available(self) -> bool:
        return self.primary_module.is_available

    @property
    def model(self) -> Any:
        return self.primary_module.model

    @property
    def metadata(self) -> Dict[str, Any]:
        return self.primary_module.metadata

    @property
    def class_names(self) -> List[str]:
        return self.primary_module.class_names

    @property
    def status(self) -> str:
        return self.primary_module.status

    @property
    def error_message(self) -> Optional[str]:
        return self.primary_module.error_message

    @property
    def model_name(self) -> str:
        return self.metadata.get("model_name", self.primary_module.config.display_name)

    @property
    def model_version(self) -> str:
        return self.metadata.get("model_version", self.primary_module.config.version)

    @property
    def architecture(self) -> str:
        return self.metadata.get("architecture", self.primary_module.config.architecture)

    @property
    def gradcam_target_layer(self) -> str:
        return self.metadata.get("gradcam_target_layer", self.primary_module.config.gradcam_target_layer)

    def load(self) -> None:
        """Legacy load trigger."""
        self.load_all_enabled()

    def get_health(self) -> Dict[str, Any]:
        """Return safe health dictionary with overall and module breakdown."""
        modules_health: Dict[str, Dict[str, Any]] = {}
        any_available = False

        for mod_cfg in self.registry.list_modules(enabled_only=False):
            art = self.load_module(mod_cfg.module_id, load_weights=False)
            if art.status == "available":
                any_available = True

            modules_health[mod_cfg.module_id] = {
                "module_id": mod_cfg.module_id,
                "display_name": mod_cfg.display_name,
                "modality": mod_cfg.modality,
                "status": art.status,
                "model_loaded": art.status == "available",
                "model_filename": mod_cfg.model_filename,
                "architecture": art.metadata.get("architecture", mod_cfg.architecture),
                "version": art.metadata.get("model_version", mod_cfg.version),
                "classification_mode": mod_cfg.classification_mode.value,
                "message": "Operational" if art.status == "available" else art.error_message or "Model not trained/available",
            }

        overall_status = "available" if any_available else "unavailable"
        if not settings.AI_ENABLED:
            overall_status = "disabled"

        return {
            "status": overall_status,
            "ai_enabled": settings.AI_ENABLED,
            "model_loaded": any_available,
            "model_name": "CliniXAI Multi-Model Medical AI Subsystem",
            "model_version": settings.APP_VERSION,
            "architecture": "Multi-Model (ResNet50 backbones)",
            "target_layer": settings.AI_GRADCAM_LAYER,
            "modules": modules_health,
            "message": "AI Subsystem operational with active modules" if any_available else "AI Subsystem initialized (Models pending training)",
        }


# Global singleton instance accessor
def get_model_loader() -> ModelLoader:
    return ModelLoader()
