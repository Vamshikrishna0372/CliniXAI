"""
Common Model Artifact Exporter for CliniXAI Multi-Model Medical AI.

Exports:
- <module>_model.keras (or model.keras)
- <module>_metadata.json (or model_metadata.json)
- <module>_class_names.json (or class_names.json)
- training_history.json
"""

import json
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

log = logging.getLogger("artifact_utils")


def export_module_artifacts(
    mod_config: Any,
    class_names: List[str],
    test_metrics: Optional[Dict[str, Any]] = None,
    gradcam_layer: str = "conv5_block3_out",
    extra_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Path]:
    """
    Export metadata and class mapping artifacts for a trained module.

    Parameters
    ----------
    mod_config     : Module configuration object
    class_names    : List of class labels
    test_metrics   : Optional evaluation metrics
    gradcam_layer  : Target layer name for Grad-CAM

    Returns
    -------
    Dict mapping artifact name to saved file Path
    """
    outputs_dir = Path(getattr(mod_config, "OUTPUTS_DIR"))
    outputs_dir.mkdir(parents=True, exist_ok=True)

    module_slug = getattr(mod_config, "MODULE_SLUG", "module")
    module_id = getattr(mod_config, "MODULE_ID", "MODULE")

    meta_filename = getattr(mod_config, "METADATA_FILENAME", f"{module_slug}_metadata.json")
    cmap_filename = getattr(mod_config, "CLASS_MAP_FILENAME", f"{module_slug}_class_names.json")

    metadata = {
        "module_id":            module_id,
        "module_slug":          module_slug,
        "model_name":           getattr(mod_config, "DISPLAY_NAME", f"CliniXAI {module_slug.capitalize()} Analysis"),
        "modality":             getattr(mod_config, "MODALITY", ""),
        "architecture":         getattr(mod_config, "ARCHITECTURE", "ResNet50"),
        "model_version":        getattr(mod_config, "MODEL_VERSION", "1.0.0"),
        "input_size":           list(getattr(mod_config, "IMAGE_SIZE", (224, 224))),
        "num_channels":         getattr(mod_config, "NUM_CHANNELS", 3),
        "preprocessing_method": getattr(mod_config, "PREPROCESSING_FN", "resnet50"),
        "class_names":          class_names,
        "number_of_classes":    len(class_names),
        "classification_type":  getattr(mod_config, "CLASSIFICATION_MODE", "multiclass"),
        "export_timestamp":     datetime.now(timezone.utc).isoformat(),
        "gradcam_target_layer": gradcam_layer,
        "decision_threshold":   0.5,
        "test_metrics":         test_metrics or {},
        "clinical_safety_notice": (
            "CliniXAI AI analysis is intended for clinical decision support only. "
            "AI-generated results must be interpreted by a qualified healthcare professional "
            "and must not be used as an independent diagnosis."
        ),
    }

    if extra_metadata:
        metadata.update(extra_metadata)

    meta_path = outputs_dir / meta_filename
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    cmap_path = outputs_dir / cmap_filename
    with open(cmap_path, "w", encoding="utf-8") as f:
        json.dump(class_names, f, indent=2)

    # Also save standard model_metadata.json and class_names.json in module outputs for local backward compatibility
    with open(outputs_dir / "model_metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    with open(outputs_dir / "class_names.json", "w", encoding="utf-8") as f:
        json.dump(class_names, f, indent=2)

    log.info("✓ Exported metadata -> %s", meta_path)
    log.info("✓ Exported class map -> %s", cmap_path)

    return {
        "metadata": meta_path,
        "class_map": cmap_path,
    }
