"""
CliniXAI — Chest X-Ray Module Configuration.

Override only values that differ from the shared defaults in common/base_config.py.
Leave fields unset to inherit shared defaults.
"""

from pathlib import Path

# ── Module Identity ──────────────────────────────────────────────────────────
MODULE_ID           = "CHEST_XRAY"
MODULE_SLUG         = "chest"
DISPLAY_NAME        = "Chest X-Ray Analysis"
MODALITY            = "Chest X-Ray (Radiography)"
ARCHITECTURE        = "ResNet50"

# ── Dataset Layout ───────────────────────────────────────────────────────────
# Expected: folder-labeled or pre-split layout inside dataset/
DATASET_LAYOUT      = "pre_split"   # "pre_split" | "folder_labels" | "csv"

# ── Classification ───────────────────────────────────────────────────────────
CLASSIFICATION_MODE = "multiclass"  # "binary" | "multiclass" | "multilabel"
# Actual class names will be auto-discovered from dataset; these are hints only
DEFAULT_CLASSES     = ["NORMAL", "PNEUMONIA"]

# ── Output Artifacts ─────────────────────────────────────────────────────────
MODULE_ROOT         = Path(__file__).parent
DATASET_DIR         = (MODULE_ROOT / "dataset" / "chest_xray") if (MODULE_ROOT / "dataset" / "chest_xray").exists() else (MODULE_ROOT / "dataset")
OUTPUTS_DIR         = MODULE_ROOT / "outputs"
MODEL_FILENAME      = "chest_xray_model_best.keras"
METADATA_FILENAME   = "chest_metadata.json"
CLASS_MAP_FILENAME  = "chest_class_names.json"

# ── Image Contract ───────────────────────────────────────────────────────────
IMAGE_SIZE          = (224, 224)
NUM_CHANNELS        = 3
PREPROCESSING_FN    = "resnet50"

# ── Grad-CAM ─────────────────────────────────────────────────────────────────
GRADCAM_LAYER_NAME  = "conv5_block3_out"

# ── Training Hyperparameters ─────────────────────────────────────────────────
# (inherits shared defaults; override here if needed)
# INITIAL_EPOCHS = 20
# FINE_TUNE_EPOCHS = 20
# BATCH_SIZE = 32
# INITIAL_LR = 1e-3
# FINE_TUNE_LR = 1e-5

# ── Augmentation Notes ───────────────────────────────────────────────────────
# Horizontal flip is DISABLED by default for chest X-rays
# (laterality matters clinically)
AUGMENT_HORIZONTAL_FLIP = False

MODEL_NAME    = f"clinixai-{MODULE_SLUG}-resnet50-v1"
MODEL_VERSION = "1.0.0"
