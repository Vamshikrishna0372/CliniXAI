"""
CliniXAI Phase 7 — Production Model Export Script.

Exports:
1. Production Keras model file: outputs/model.keras
2. Model metadata JSON        : outputs/model_metadata.json
3. Class names JSON           : outputs/class_names.json

This metadata and class map establish the exact inference contract required by
Phase 8 FastAPI backend.
"""

import sys
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import config as cfg

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
log = logging.getLogger("export_model")


def export_production_model() -> None:
    import tensorflow as tf
    from scripts.model import build_model, get_gradcam_layer_name

    log.info("=" * 60)
    log.info("CliniXAI Phase 7 — Model Export")
    log.info("=" * 60)

    cfg.OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Load class names
    if not cfg.CLASS_NAMES_FILE.exists():
        log.error("class_names.json not found. Run train.py first.")
        sys.exit(1)

    with open(cfg.CLASS_NAMES_FILE) as f:
        class_names = json.load(f)

    num_classes = len(class_names)
    classification_type = "binary" if num_classes == 2 else "multiclass"

    # 2. Build model and load best checkpoint weights
    if not cfg.BEST_CHECKPOINT.exists():
        log.error("Checkpoint missing: %s. Cannot export model.", cfg.BEST_CHECKPOINT)
        sys.exit(1)

    log.info("Loading model weights from: %s", cfg.BEST_CHECKPOINT)
    model = build_model(num_classes, frozen=False)
    model.load_weights(str(cfg.BEST_CHECKPOINT))

    # 3. Export model to .keras format
    log.info("Saving production model to: %s", cfg.EXPORTED_MODEL)
    model.save(str(cfg.EXPORTED_MODEL))
    log.info("✓ Model saved successfully.")

    # 4. Detect Grad-CAM target layer
    gradcam_layer = get_gradcam_layer_name(model)
    log.info("Grad-CAM target layer: %s", gradcam_layer)

    # 5. Gather metrics if present
    eval_metrics = {}
    if cfg.EVALUATION_FILE.exists():
        with open(cfg.EVALUATION_FILE) as f:
            eval_metrics = json.load(f)

    # 6. Build model metadata
    metadata = {
        "model_name":          cfg.MODEL_NAME,
        "architecture":        cfg.ARCHITECTURE,
        "model_version":       cfg.MODEL_VERSION,
        "input_size":          list(cfg.IMAGE_SIZE),
        "num_channels":        cfg.NUM_CHANNELS,
        "preprocessing_method": cfg.PREPROCESSING_FN,
        "resize_strategy":     cfg.RESIZE_STRATEGY,
        "class_names":         class_names,
        "number_of_classes":   num_classes,
        "classification_type": classification_type,
        "export_timestamp":    datetime.now(timezone.utc).isoformat(),
        "tensorflow_version":  tf.__version__,
        "gradcam_target_layer": gradcam_layer,
        "decision_threshold":  cfg.BINARY_THRESHOLD if num_classes == 2 else None,
        "test_metrics":        eval_metrics,
        "clinical_safety_notice": (
            "This model provides Clinical Decision Support (CDS) only. "
            "It does NOT perform autonomous diagnosis and must be "
            "reviewed by a licensed medical professional."
        ),
    }

    # Write metadata JSON
    with open(cfg.MODEL_METADATA_FILE, "w") as f:
        json.dump(metadata, f, indent=2)
    log.info("✓ Model metadata exported → %s", cfg.MODEL_METADATA_FILE)

    # Re-verify class_names.json
    with open(cfg.CLASS_NAMES_FILE, "w") as f:
        json.dump(class_names, f, indent=2)
    log.info("✓ Class map exported → %s", cfg.CLASS_NAMES_FILE)

    log.info("")
    log.info("=" * 60)
    log.info("Phase 7 Model Export Complete.")
    log.info("Exported Artifacts:")
    log.info("  1. Model     : %s", cfg.EXPORTED_MODEL)
    log.info("  2. Metadata  : %s", cfg.MODEL_METADATA_FILE)
    log.info("  3. Class Map : %s", cfg.CLASS_NAMES_FILE)
    log.info("=" * 60)


if __name__ == "__main__":
    export_production_model()
