"""
CliniXAI Phase 7 — Centralised Training Configuration.

All hyperparameters and path constants live here.
Import this module from every script instead of scattering magic numbers.
"""

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Root paths
# ---------------------------------------------------------------------------
ROOT_DIR       = Path(__file__).parent.resolve()
DATASET_DIR    = ROOT_DIR / "dataset"
TRAIN_DIR      = DATASET_DIR / "train"
VAL_DIR        = DATASET_DIR / "validation"
TEST_DIR       = DATASET_DIR / "test"
CHECKPOINT_DIR = ROOT_DIR / "checkpoints"
OUTPUTS_DIR    = ROOT_DIR / "outputs"
METRICS_DIR    = OUTPUTS_DIR / "metrics"
PLOTS_DIR      = OUTPUTS_DIR / "plots"
GRADCAM_DIR    = OUTPUTS_DIR / "gradcam"

# ---------------------------------------------------------------------------
# Model identity / versioning
# ---------------------------------------------------------------------------
MODEL_NAME    = "clinixai-resnet50-v1"
MODEL_VERSION = "1.0.0"
ARCHITECTURE  = "ResNet50"

# ---------------------------------------------------------------------------
# Image contract  (must match Phase 8 inference exactly)
# ---------------------------------------------------------------------------
IMAGE_SIZE          = (224, 224)           # ResNet50 native input
NUM_CHANNELS        = 3                    # RGB
PREPROCESSING_FN    = "resnet50.preprocess_input"   # for documentation
RESIZE_STRATEGY     = "resize"            # resize | pad | center_crop

# ---------------------------------------------------------------------------
# Training – Phase 1: transfer learning (backbone frozen)
# ---------------------------------------------------------------------------
INITIAL_EPOCHS          = 20
INITIAL_LR              = 1e-3
BATCH_SIZE              = 32
DROPOUT_RATE            = 0.3

# ---------------------------------------------------------------------------
# Training – Phase 2: fine-tuning (upper backbone unfrozen)
# ---------------------------------------------------------------------------
FINE_TUNE_EPOCHS        = 20              # additional epochs
FINE_TUNE_LR            = 1e-5
FINE_TUNE_AT_LAYER      = 143             # unfreeze from this layer index onward
                                          # (corresponds to ~last ResNet stage)

# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------
EARLY_STOPPING_PATIENCE  = 7
REDUCE_LR_PATIENCE       = 3
REDUCE_LR_FACTOR         = 0.3
REDUCE_LR_MIN            = 1e-7
MONITOR_METRIC           = "val_accuracy"

# ---------------------------------------------------------------------------
# Augmentation (training only — conservative, medically safe defaults)
# ---------------------------------------------------------------------------
AUGMENT_ROTATION_RANGE   = 10            # degrees — small rotation only
AUGMENT_ZOOM_RANGE       = 0.1
AUGMENT_WIDTH_SHIFT      = 0.05
AUGMENT_HEIGHT_SHIFT     = 0.05
AUGMENT_BRIGHTNESS_RANGE = (0.85, 1.15)
# Horizontal flip: set False unless confirmed safe for the chosen modality
AUGMENT_HORIZONTAL_FLIP  = False

# ---------------------------------------------------------------------------
# Classification threshold  (binary)
# ---------------------------------------------------------------------------
BINARY_THRESHOLD = 0.5    # default; re-evaluate on validation set

# ---------------------------------------------------------------------------
# Imbalance handling
# ---------------------------------------------------------------------------
USE_CLASS_WEIGHTS = True   # compute class weights from training distribution

# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------
RANDOM_SEED = 42

# ---------------------------------------------------------------------------
# Grad-CAM
# ---------------------------------------------------------------------------
GRADCAM_LAYER_NAME = "conv5_block3_out"   # ResNet50 final conv block
GRADCAM_SAMPLE_COUNT = 10                 # images per class to visualise

# ---------------------------------------------------------------------------
# Output file names
# ---------------------------------------------------------------------------
BEST_CHECKPOINT      = CHECKPOINT_DIR / "best_model.weights.h5"
EXPORTED_MODEL       = OUTPUTS_DIR / "model.keras"
CLASS_NAMES_FILE     = OUTPUTS_DIR / "class_names.json"
MODEL_METADATA_FILE  = OUTPUTS_DIR / "model_metadata.json"
TRAINING_HISTORY     = METRICS_DIR / "training_history.json"
EVALUATION_FILE      = METRICS_DIR / "evaluation.json"
CLASS_REPORT_FILE    = METRICS_DIR / "classification_report.json"
CONFUSION_CSV        = METRICS_DIR / "confusion_matrix.csv"
