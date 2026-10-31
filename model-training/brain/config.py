"""
CliniXAI — Brain MRI Module Configuration.
"""

from pathlib import Path

MODULE_ID           = "BRAIN_MRI"
MODULE_SLUG         = "brain"
DISPLAY_NAME        = "Brain MRI Tumor Classification"
MODALITY            = "Brain MRI (Magnetic Resonance Imaging)"
ARCHITECTURE        = "ResNet50"

DATASET_LAYOUT      = "pre_split"   # "pre_split" | "folder_labels" | "csv"

CLASSIFICATION_MODE = "multiclass"
DEFAULT_CLASSES     = ["Glioma", "Meningioma", "Pituitary", "No Tumor"]

MODULE_ROOT         = Path(__file__).parent
DATASET_DIR         = MODULE_ROOT / "dataset"
OUTPUTS_DIR         = MODULE_ROOT / "outputs"
MODEL_FILENAME      = "brain_model.keras"
METADATA_FILENAME   = "brain_metadata.json"
CLASS_MAP_FILENAME  = "brain_class_names.json"

IMAGE_SIZE          = (224, 224)
NUM_CHANNELS        = 3
PREPROCESSING_FN    = "resnet50"

GRADCAM_LAYER_NAME  = "conv5_block3_out"

# Brain MRI: horizontal flip may be acceptable (symmetric anatomy)
AUGMENT_HORIZONTAL_FLIP = True

MODEL_NAME    = "clinixai-brain-resnet50-v1"
MODEL_VERSION = "1.0.0"
