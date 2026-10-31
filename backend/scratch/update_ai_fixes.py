# 1. Update ai_analyses.py to allow stateless direct infer when patient_id is not provided
ai_path = r"backend/app/api/v1/routes/ai_analyses.py"
with open(ai_path, "r", encoding="utf-8") as f:
    ai_content = f.read()

old_check = """            if not target_pid:
                raise HTTPException(status_code=400, detail="patient_id is required for clinical decision support inference.")"""

new_check = """            if not target_pid:
                # Stateless / ad-hoc inference without patient context
                return AIDirectInferResponse(
                    analysis_id=None,
                    module_id=norm_id,
                    display_name=mod_cfg.display_name,
                    architecture=mod_cfg.architecture,
                    model_version=model_version,
                    predicted_class=prediction.predicted_class,
                    confidence=prediction.confidence,
                    probabilities=probs,
                    gradcam_available=gradcam_ok,
                    gradcam_b64=gradcam_b64,
                )"""

if old_check in ai_content:
    ai_content = ai_content.replace(old_check, new_check)
    with open(ai_path, "w", encoding="utf-8") as f:
        f.write(ai_content)
    print("Updated ai_analyses.py")
else:
    print("old_check not found in ai_analyses.py")

# 2. Update ai_service.py for eligibility check and backward compatible release filter
svc_path = r"backend/app/services/ai_service.py"
with open(svc_path, "r", encoding="utf-8") as f:
    svc_content = f.read()

# Add source_id check to is_brain_eligible
old_elig = """            is_brain_eligible = (
                is_mri_modality
                or any(k in file_category for k in ["mri", "brain"])
                or any(k in record_type for k in ["mri", "brain"])"""

new_elig = """            is_brain_eligible = (
                is_mri_modality
                or any(k in str(source_id).lower() for k in ["mri", "brain"])
                or any(k in file_category for k in ["mri", "brain"])
                or any(k in record_type for k in ["mri", "brain"])"""

if old_elig in svc_content:
    svc_content = svc_content.replace(old_elig, new_elig)
    print("Updated eligibility in ai_service.py")
else:
    print("old_elig not found in ai_service.py")

# Update query["is_released_to_patient"] in list_analyses
old_q = 'query["is_released_to_patient"] = True'
new_q = 'query["is_released_to_patient"] = {"$ne": False}'

if old_q in svc_content:
    svc_content = svc_content.replace(old_q, new_q)
    print("Updated release query in ai_service.py")
else:
    print("old_q not found in ai_service.py")

with open(svc_path, "w", encoding="utf-8") as f:
    f.write(svc_content)

