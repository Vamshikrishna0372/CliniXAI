"""
CliniXAI — Skin Dermoscopy Module Configuration.
"""

from pathlib import Path

MODULE_ID           = "SKIN_DERMOSCOPY"
MODULE_SLUG         = "skin"
DISPLAY_NAME        = "Skin Dermoscopy Lesion Analysis"
MODALITY            = "Skin Dermoscopy (Dermatology)"
ARCHITECTURE        = "ResNet50"

DATASET_LAYOUT      = "pre_split"   # "pre_split" | "folder_labels" | "csv"

CLASSIFICATION_MODE = "multiclass"
DEFAULT_CLASSES     = ["Melanoma", "Melanocytic Nevus", "Basal Cell Carcinoma", "Benign Keratosis"]

MODULE_ROOT         = Path(__file__).parent
DATASET_DIR         = MODULE_ROOT / "dataset"
OUTPUTS_DIR         = MODULE_ROOT / "outputs"
MODEL_FILENAME      = "skin_model.keras"
METADATA_FILENAME   = "skin_metadata.json"
CLASS_MAP_FILENAME  = "skin_class_names.json"

IMAGE_SIZE          = (224, 224)
NUM_CHANNELS        = 3
PREPROCESSING_FN    = "resnet50"

GRADCAM_LAYER_NAME  = "conv5_block3_out"

# Dermoscopy: horizontal and vertical flip generally safe
AUGMENT_HORIZONTAL_FLIP = True

MODEL_NAME    = "clinixai-skin-resnet50-v1"
MODEL_VERSION = "1.0.0"
