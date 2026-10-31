"""
CliniXAI — Bone X-Ray Module Configuration.
"""

from pathlib import Path

MODULE_ID           = "BONE_XRAY"
MODULE_SLUG         = "bone"
DISPLAY_NAME        = "Bone X-Ray Fracture Detection"
MODALITY            = "Bone Radiography (Orthopedics)"
ARCHITECTURE        = "ResNet50"

DATASET_LAYOUT      = "pre_split"   # "pre_split" | "folder_labels" | "csv"

CLASSIFICATION_MODE = "binary"
DEFAULT_CLASSES     = ["Normal", "Fracture Detected"]

MODULE_ROOT         = Path(__file__).parent
DATASET_DIR         = MODULE_ROOT / "dataset"
OUTPUTS_DIR         = MODULE_ROOT / "outputs"
MODEL_FILENAME      = "bone_model.keras"
METADATA_FILENAME   = "bone_metadata.json"
CLASS_MAP_FILENAME  = "bone_class_names.json"

IMAGE_SIZE          = (224, 224)
NUM_CHANNELS        = 3
PREPROCESSING_FN    = "resnet50"

GRADCAM_LAYER_NAME  = "conv5_block3_out"

# Bone X-Ray: horizontal flip is disabled by default for limb laterality safety
AUGMENT_HORIZONTAL_FLIP = False

MODEL_NAME    = "clinixai-bone-resnet50-v1"
MODEL_VERSION = "1.0.0"
