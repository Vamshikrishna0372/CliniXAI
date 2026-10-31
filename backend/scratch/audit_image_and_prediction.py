import hashlib
import json
import os
import sys
from PIL import Image
import numpy as np

ORIG_IMG_PATH = "backend/uploads/medical-records/image_AI-2026-466F63.jpg"
GRADCAM_PATH = "backend/uploads/ai-analyses/gradcam_AI-2026-466F63.png"

report = {}

# 1. Inspect original image
if os.path.exists(ORIG_IMG_PATH):
    with open(ORIG_IMG_PATH, "rb") as f:
        orig_bytes = f.read()
    orig_sha256 = hashlib.sha256(orig_bytes).hexdigest()
    img_pil = Image.open(ORIG_IMG_PATH)
    report["original_image"] = {
        "exists": True,
        "path": os.path.abspath(ORIG_IMG_PATH),
        "size_bytes": len(orig_bytes),
        "sha256": orig_sha256,
        "dimensions": img_pil.size,
        "mode": img_pil.mode,
        "format": img_pil.format,
    }
else:
    report["original_image"] = {"exists": False}

# 2. Inspect Grad-CAM image
if os.path.exists(GRADCAM_PATH):
    with open(GRADCAM_PATH, "rb") as f:
        gc_bytes = f.read()
    gc_sha256 = hashlib.sha256(gc_bytes).hexdigest()
    gc_pil = Image.open(GRADCAM_PATH)
    report["gradcam_artifact"] = {
        "exists": True,
        "path": os.path.abspath(GRADCAM_PATH),
        "size_bytes": len(gc_bytes),
        "sha256": gc_sha256,
        "dimensions": gc_pil.size,
        "mode": gc_pil.mode,
        "format": gc_pil.format,
    }
else:
    report["gradcam_artifact"] = {"exists": False}

# 3. Check MongoDB record input checksum
with open(".data_persist/ai_analyses.json", "r", encoding="utf-8") as f:
    analyses = json.load(f)

for a in analyses:
    if a.get("analysis_id") == "AI-2026-466F63":
        report["mongodb_record"] = {
            "analysis_id": a.get("analysis_id"),
            "patient_id": a.get("patient_id"),
            "doctor_id": a.get("doctor_id"),
            "document_id": a.get("document_id"),
            "medical_record_id": a.get("medical_record_id"),
            "input_checksum": a.get("input", {}).get("checksum"),
            "prediction": a.get("prediction"),
            "explainability": a.get("explainability"),
            "doctor_review": a.get("doctor_review"),
        }
        break

# 4. Run real model inference on orig_bytes to compare with stored prediction
sys.path.insert(0, os.path.abspath("backend"))
try:
    from app.ai.registry import get_ai_registry
    from app.ai.model_loader import get_model_loader
    from app.ai.preprocessing import load_and_preprocess_backend_image
    from app.ai.inference import run_inference
    from app.ai.gradcam import generate_gradcam_overlay_bytes

    registry = get_ai_registry()
    mod_cfg = registry.get_module("BRAIN_MRI")
    loader = get_model_loader()
    artifact = loader.load_module("BRAIN_MRI")

    prep_tensor = load_and_preprocess_backend_image(
        orig_bytes,
        target_size=tuple(mod_cfg.input_shape[:2]),
        strategy=mod_cfg.preprocessing_strategy,
    )

    pred, model_ver = run_inference(prep_tensor, module_id="BRAIN_MRI")
    report["fresh_inference_on_stored_image"] = {
        "model_version": model_ver,
        "predicted_class": pred.predicted_class,
        "confidence": pred.confidence,
        "class_probabilities": pred.class_probabilities,
        "probabilities": pred.probabilities,
        "low_confidence": pred.low_confidence,
    }

    # Verify Grad-CAM generation
    gc_new_bytes, _ = generate_gradcam_overlay_bytes(
        original_image_input=orig_bytes,
        preprocessed_tensor=prep_tensor,
        module_id="BRAIN_MRI",
    )
    report["fresh_gradcam"] = {
        "generated": True,
        "size_bytes": len(gc_new_bytes),
        "sha256": hashlib.sha256(gc_new_bytes).hexdigest(),
    }
except Exception as ex:
    report["inference_error"] = str(ex)
    import traceback
    report["inference_traceback"] = traceback.format_exc()

with open("backend/scratch/image_and_prediction_audit.json", "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2)

print("IMAGE_AND_PREDICTION_AUDIT_DONE")

