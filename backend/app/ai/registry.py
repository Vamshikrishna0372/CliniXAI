"""
AI Module Registry for CliniXAI Multi-Model Medical AI/XAI Architecture.

Defines supported medical imaging AI modules, their configurations, metadata,
and registration interfaces.
"""

from enum import Enum
from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel, Field


class AIModuleIdentifier(str, Enum):
    """Supported Medical AI Module Identifiers."""
    CHEST_XRAY = "CHEST_XRAY"
    BRAIN_MRI = "BRAIN_MRI"
    SKIN_DERMOSCOPY = "SKIN_DERMOSCOPY"
    RETINAL_FUNDUS = "RETINAL_FUNDUS"
    BONE_XRAY = "BONE_XRAY"


class ClassificationMode(str, Enum):
    """Classification modes supported by CliniXAI medical modules."""
    BINARY = "binary"
    MULTICLASS = "multiclass"
    MULTILABEL = "multilabel"


class AIModuleConfig(BaseModel):
    """Configuration contract for a registered medical AI module."""
    module_id: str = Field(..., description="Unique upper-case identifier, e.g. CHEST_XRAY")
    slug: str = Field(..., description="Short folder/filename slug, e.g. chest")
    display_name: str = Field(..., description="Human-readable module title")
    modality: str = Field(..., description="Medical imaging modality description")
    model_filename: str = Field(..., description="Target model filename in backend/ai_models/")
    metadata_filename: str = Field(..., description="Metadata filename in backend/ai_models/")
    class_map_filename: str = Field(..., description="Class mapping filename in backend/ai_models/")
    input_shape: Tuple[int, int, int] = Field(default=(224, 224, 3), description="Expected image input shape (H, W, C)")
    preprocessing_strategy: str = Field(default="resnet50", description="Preprocessing function identifier")
    architecture: str = Field(default="ResNet50", description="Neural network backbone architecture")
    classification_mode: ClassificationMode = Field(default=ClassificationMode.MULTICLASS)
    default_class_names: List[str] = Field(default_factory=lambda: ["Normal", "Abnormal"])
    gradcam_target_layer: str = Field(default="conv5_block3_out", description="Target layer for Grad-CAM XAI")
    enabled: bool = Field(default=True, description="Whether module is enabled in backend")
    version: str = Field(default="1.0.0", description="Module/Model version")
    supported_image_types: List[str] = Field(default_factory=lambda: ["image/jpeg", "image/png", "image/webp"])
    description: str = Field(default="", description="Clinical description of the module")


# Default registry configuration mapping
DEFAULT_REGISTRY: Dict[str, AIModuleConfig] = {
    AIModuleIdentifier.CHEST_XRAY.value: AIModuleConfig(
        module_id=AIModuleIdentifier.CHEST_XRAY.value,
        slug="chest",
        display_name="Chest X-Ray Analysis",
        modality="Chest X-Ray (Radiography)",
        model_filename="chest_model.keras",
        metadata_filename="chest_metadata.json",
        class_map_filename="chest_class_names.json",
        input_shape=(224, 224, 3),
        preprocessing_strategy="resnet50",
        architecture="ResNet50",
        classification_mode=ClassificationMode.MULTICLASS,
        default_class_names=["NORMAL", "PNEUMONIA"],
        gradcam_target_layer="conv5_block3_out",
        enabled=True,
        version="1.0.0",
        description="Detection of pulmonary findings and abnormalities in chest radiographs.",
    ),
    AIModuleIdentifier.BRAIN_MRI.value: AIModuleConfig(
        module_id=AIModuleIdentifier.BRAIN_MRI.value,
        slug="brain",
        display_name="Brain MRI Tumor Classification",
        modality="Brain MRI (Magnetic Resonance Imaging)",
        model_filename="brain_model.keras",
        metadata_filename="brain_metadata.json",
        class_map_filename="brain_class_names.json",
        input_shape=(224, 224, 3),
        preprocessing_strategy="resnet50",
        architecture="ResNet50",
        classification_mode=ClassificationMode.MULTICLASS,
        default_class_names=["glioma", "meningioma", "notumor", "pituitary"],
        gradcam_target_layer="conv5_block3_out",
        enabled=True,
        version="1.0.0",
        description="Classification of brain neoplasms and structural lesions from MRI scans.",
    ),
    AIModuleIdentifier.SKIN_DERMOSCOPY.value: AIModuleConfig(
        module_id=AIModuleIdentifier.SKIN_DERMOSCOPY.value,
        slug="skin",
        display_name="Skin Dermoscopy Lesion Analysis",
        modality="Skin Dermoscopy (Dermatology)",
        model_filename="skin_model.keras",
        metadata_filename="skin_metadata.json",
        class_map_filename="skin_class_names.json",
        input_shape=(224, 224, 3),
        preprocessing_strategy="resnet50",
        architecture="ResNet50",
        classification_mode=ClassificationMode.MULTICLASS,
        default_class_names=["Melanoma", "Melanocytic Nevus", "Basal Cell Carcinoma", "Benign Keratosis"],
        gradcam_target_layer="conv5_block3_out",
        enabled=True,
        version="1.0.0",
        description="Screening and classification of cutaneous lesions in dermoscopic images.",
    ),
    AIModuleIdentifier.RETINAL_FUNDUS.value: AIModuleConfig(
        module_id=AIModuleIdentifier.RETINAL_FUNDUS.value,
        slug="eye",
        display_name="Eye Retinal Fundus Screening",
        modality="Retinal Fundus (Ophthalmology)",
        model_filename="eye_model.keras",
        metadata_filename="eye_metadata.json",
        class_map_filename="eye_class_names.json",
        input_shape=(224, 224, 3),
        preprocessing_strategy="resnet50",
        architecture="ResNet50",
        classification_mode=ClassificationMode.MULTICLASS,
        default_class_names=["No Diabetic Retinopathy", "Mild DR", "Moderate DR", "Severe DR", "Proliferative DR"],
        gradcam_target_layer="conv5_block3_out",
        enabled=True,
        version="1.0.0",
        description="Grading of diabetic retinopathy and retinal microvascular abnormalities.",
    ),
    AIModuleIdentifier.BONE_XRAY.value: AIModuleConfig(
        module_id=AIModuleIdentifier.BONE_XRAY.value,
        slug="bone",
        display_name="Bone X-Ray Fracture Detection",
        modality="Bone Radiography (Orthopedics)",
        model_filename="bone_model.keras",
        metadata_filename="bone_metadata.json",
        class_map_filename="bone_class_names.json",
        input_shape=(224, 224, 3),
        preprocessing_strategy="resnet50",
        architecture="ResNet50",
        classification_mode=ClassificationMode.BINARY,
        default_class_names=["Normal", "Fracture Detected"],
        gradcam_target_layer="conv5_block3_out",
        enabled=True,
        version="1.0.0",
        description="Identification of acute skeletal fractures and cortical disruptions in bone X-rays.",
    ),
}


class AIModuleRegistry:
    """Registry maintaining active medical AI module configurations."""

    def __init__(self):
        self._modules: Dict[str, AIModuleConfig] = dict(DEFAULT_REGISTRY)

    def normalize_identifier(self, identifier: Optional[str]) -> str:
        """
        Normalize input string or alias to authoritative module ID.
        e.g., 'chest' -> 'CHEST_XRAY', 'BRAIN_MRI' -> 'BRAIN_MRI', None -> 'CHEST_XRAY'
        """
        if not identifier:
            return AIModuleIdentifier.CHEST_XRAY.value

        clean = str(identifier).strip().upper()
        if clean in self._modules:
            return clean

        # Map common slugs / aliases
        alias_map = {
            "CHEST": AIModuleIdentifier.CHEST_XRAY.value,
            "CHEST_XRAY": AIModuleIdentifier.CHEST_XRAY.value,
            "CHESTXRAY": AIModuleIdentifier.CHEST_XRAY.value,
            "BRAIN": AIModuleIdentifier.BRAIN_MRI.value,
            "BRAIN_MRI": AIModuleIdentifier.BRAIN_MRI.value,
            "BRAINMRI": AIModuleIdentifier.BRAIN_MRI.value,
            "SKIN": AIModuleIdentifier.SKIN_DERMOSCOPY.value,
            "SKIN_DERMOSCOPY": AIModuleIdentifier.SKIN_DERMOSCOPY.value,
            "DERMOSCOPY": AIModuleIdentifier.SKIN_DERMOSCOPY.value,
            "EYE": AIModuleIdentifier.RETINAL_FUNDUS.value,
            "RETINAL": AIModuleIdentifier.RETINAL_FUNDUS.value,
            "RETINAL_FUNDUS": AIModuleIdentifier.RETINAL_FUNDUS.value,
            "FUNDUS": AIModuleIdentifier.RETINAL_FUNDUS.value,
            "BONE": AIModuleIdentifier.BONE_XRAY.value,
            "BONE_XRAY": AIModuleIdentifier.BONE_XRAY.value,
        }
        if clean in alias_map:
            return alias_map[clean]

        # Lowercase slug search
        lower = str(identifier).strip().lower()
        for mod_id, cfg in self._modules.items():
            if cfg.slug.lower() == lower:
                return mod_id

        raise ValueError(
            f"Unknown medical AI module '{identifier}'. "
            f"Supported modules: {list(self._modules.keys())}"
        )

    def get_module(self, identifier: str) -> AIModuleConfig:
        """Retrieve module config by ID or alias."""
        norm_id = self.normalize_identifier(identifier)
        return self._modules[norm_id]

    def list_modules(self, enabled_only: bool = True) -> List[AIModuleConfig]:
        """List all registered modules."""
        if enabled_only:
            return [cfg for cfg in self._modules.values() if cfg.enabled]
        return list(self._modules.values())

    def register_module(self, config: AIModuleConfig) -> None:
        """Register or override a medical AI module configuration."""
        self._modules[config.module_id] = config


# Singleton registry instance
_registry_instance = AIModuleRegistry()


def get_ai_registry() -> AIModuleRegistry:
    """Access global AI Module Registry instance."""
    return _registry_instance
