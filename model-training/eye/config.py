"""
CliniXAI — Eye / Retinal Fundus Module Configuration.
"""

from pathlib import Path

MODULE_ID           = "RETINAL_FUNDUS"
MODULE_SLUG         = "eye"
DISPLAY_NAME        = "Eye Retinal Fundus Screening"
MODALITY            = "Retinal Fundus (Ophthalmology)"
ARCHITECTURE        = "ResNet50"

DATASET_LAYOUT      = "pre_split"   # "pre_split" | "folder_labels" | "csv"

CLASSIFICATION_MODE = "multiclass"
DEFAULT_CLASSES     = [
    "No Diabetic Retinopathy",
    "Mild DR",
    "Moderate DR",
    "Severe DR",
    "Proliferative DR",
]

MODULE_ROOT         = Path(__file__).parent
DATASET_DIR         = MODULE_ROOT / "dataset"
OUTPUTS_DIR         = MODULE_ROOT / "outputs"
MODEL_FILENAME      = "eye_model.keras"
METADATA_FILENAME   = "eye_metadata.json"
CLASS_MAP_FILENAME  = "eye_class_names.json"

IMAGE_SIZE          = (224, 224)
NUM_CHANNELS        = 3
PREPROCESSING_FN    = "resnet50"

GRADCAM_LAYER_NAME  = "conv5_block3_out"

# Retinal fundus: horizontal flip acceptable (symmetric retinal anatomy)
AUGMENT_HORIZONTAL_FLIP = True

MODEL_NAME    = "clinixai-eye-resnet50-v1"
MODEL_VERSION = "1.0.0"
