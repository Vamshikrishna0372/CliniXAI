"""
AI Analysis & Explainable AI (XAI) API Routes for CliniXAI Multi-Model Architecture.

Clinical Decision Support (CDS) endpoints for multi-model inference (Chest X-Ray,
Brain MRI, Skin Dermoscopy, Retinal Fundus, Bone X-Ray), Grad-CAM heatmap overlays,
Doctor review workflows, Patient-safe reports, and Admin AI operational metrics.
"""

import io
import base64
from typing import Optional, List
from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.dependencies.database import get_database
from app.dependencies.auth import (
    get_current_active_user, get_current_active_user_strict_header, require_roles
)
from app.models.user import UserInDB, UserRole
from app.schemas.ai_analysis import (
    AIAnalysisCreateRequest, AIReviewRequest, AIHealthResponse,
    AIAnalysisDoctorResponse, AIAnalysisPatientReportResponse,
    AIAnalysisListResponse, AIInsightsResponse, AIModuleInfoResponse,
    AIDirectInferResponse,
)
from app.services.ai_service import AIService

router = APIRouter(tags=["AI Analyses"])


# ── AI Health Endpoint ──────────────────────────────────────────────────────
@router.get(
    "/ai/health",
    response_model=AIHealthResponse,
    summary="Get AI Subsystem Health Status",
)
async def get_ai_health():
    """Returns operational status, model availability, and architecture metadata for all registered AI modules."""
    return AIService.get_health()


# ── Direct Upload Inference Endpoint ─────────────────────────────────────────
@router.post(
    "/ai/infer",
    response_model=AIDirectInferResponse,
    summary="Run AI Inference on a Directly Uploaded Image",
)
async def direct_infer(
    image: UploadFile = File(..., description="Medical image file (JPEG, PNG, DICOM)"),
    analysis_type: str = Form("BRAIN_MRI", description="AI module identifier: BRAIN_MRI, CHEST_XRAY, SKIN_DERMOSCOPY, RETINAL_FUNDUS, BONE_XRAY"),
    patient_id: Optional[str] = Form(None, description="Canonical Patient ID for clinical context"),
    document_id: Optional[str] = Form(None, description="Optional existing document ID to associate with analysis"),
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """
    Stateless inference endpoint — accepts a raw image upload and returns AI results
    with Grad-CAM heatmap immediately. Does not require an existing medical record.
    Intended for the clinical decision support upload-and-analyze flow.
    """
    from app.ai.registry import get_ai_registry
    from app.ai.model_loader import get_model_loader
    from app.ai.preprocessing import load_and_preprocess_backend_image
    from app.ai.inference import run_inference
    from app.ai.gradcam import generate_gradcam_overlay_bytes
    from app.utils.file_validation import validate_file_content
    from app.services.audit_service import log_audit_event

    # Validate role - Doctors, Admins, and Patients (for their own clinical decision support upload)
    if current_user.role not in (UserRole.DOCTOR, UserRole.HOSPITAL_ADMIN, UserRole.ADMIN, UserRole.PATIENT):
        raise HTTPException(status_code=403, detail="Unauthorized to run AI inference.")

    # Read uploaded bytes
    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Uploaded image file is empty.")

    # Secure file validation (dangerous extensions block, magic bytes, max size limit)
    try:
        val_res = validate_file_content(image.filename or "uploaded_image.jpg", image.content_type or "image/jpeg", image_bytes)
        if not val_res.is_image:
            raise HTTPException(status_code=400, detail="Uploaded file is not a valid medical image.")
    except Exception as val_err:
        if isinstance(val_err, HTTPException):
            raise val_err
        raise HTTPException(status_code=400, detail=str(val_err))

    registry = get_ai_registry()
    loader = get_model_loader()

    try:
        norm_id = registry.normalize_identifier(analysis_type)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    mod_cfg = registry.get_module(norm_id)
    artifact = loader.load_module(norm_id)

    if not artifact.is_available:
        raise HTTPException(
            status_code=503,
            detail=f"AI module '{mod_cfg.display_name}' is not currently available: {artifact.error_message}"
        )

    # Preprocess
    prep_tensor = load_and_preprocess_backend_image(
        image_bytes,
        target_size=tuple(mod_cfg.input_shape[:2]),
        strategy=mod_cfg.preprocessing_strategy,
    )

    # Inference
    prediction, model_version = run_inference(prep_tensor, module_id=norm_id)

    # Grad-CAM
    gradcam_b64: Optional[str] = None
    gradcam_bytes: Optional[bytes] = None
    gradcam_ok = False
    try:
        gradcam_bytes, _ = generate_gradcam_overlay_bytes(
            original_image_input=image_bytes,
            preprocessed_tensor=prep_tensor,
            module_id=norm_id,
        )
        gradcam_b64 = "data:image/png;base64," + base64.b64encode(gradcam_bytes).decode("utf-8")
        gradcam_ok = True
    except Exception as gc_err:
        import logging
        logging.getLogger(__name__).warning("Grad-CAM skipped for direct infer: %s", gc_err)

    # Build probabilities list from prediction
    probs = []
    class_probs = getattr(prediction, "class_probabilities", None) or getattr(prediction, "probabilities", None)
    if class_probs:
        probs = [{"label": k, "probability": v} for k, v in class_probs.items()]
    elif hasattr(prediction, "confidence"):
        probs = [{"label": prediction.predicted_class, "probability": prediction.confidence}]

    # Persist genuine AI Analysis record into authoritative MongoDB
    analysis_id: Optional[str] = None
    try:
        from app.utils.id_generator import generate_ai_analysis_id
        from app.utils.datetime import utc_now
        from app.services.storage_service import get_storage_service
        from app.models.ai_analysis import AIAnalysisInDB, AIAnalysisStatus, ModelInfo, InputInfo, ExplainabilityInfo
        from app.database.collections import COLLECTION_AI_ANALYSES, COLLECTION_DOCTORS, COLLECTION_PATIENTS
        from app.database.mongodb import save_in_memory_snapshot

        analysis_id = generate_ai_analysis_id()
        storage = get_storage_service()

        img_key = f"image_{analysis_id}.jpg"
        await storage.save_file(content_bytes=image_bytes, storage_key=img_key, subfolder="medical-records")

        explainability = None
        if gradcam_ok and gradcam_bytes:
            gradcam_key = f"gradcam_{analysis_id}.png"
            await storage.save_file(content_bytes=gradcam_bytes, storage_key=gradcam_key, subfolder="ai-analyses")
            explainability = ExplainabilityInfo(
                method="grad_cam",
                target_layer="conv5_block3_out" if norm_id == "BRAIN_MRI" else "conv2d_3",
                target_class=prediction.predicted_class,
                artifact_storage_key=gradcam_key,
            )

        doctor_id = None
        target_pid = patient_id

        if current_user.role in (UserRole.DOCTOR, UserRole.HOSPITAL_ADMIN, UserRole.ADMIN):
            doc = await db[COLLECTION_DOCTORS].find_one({"user_id": current_user.user_id})
            if doc:
                doctor_id = doc.get("doctor_id")
            if not doctor_id and current_user.role == UserRole.DOCTOR:
                doctor_id = "DOC-RAO-001"

            if not target_pid and document_id:
                from app.database.collections import COLLECTION_DOCUMENTS
                d_rec = await db[COLLECTION_DOCUMENTS].find_one({"document_id": document_id})
                if d_rec and d_rec.get("patient_id"):
                    target_pid = d_rec["patient_id"]

            if not target_pid:
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
                )

            pat = await db[COLLECTION_PATIENTS].find_one({"$or": [{"patient_id": target_pid}, {"user_id": target_pid}]})
            if not pat:
                raise HTTPException(status_code=404, detail=f"Patient '{target_pid}' not found.")
            canonical_patient_id = pat["patient_id"]

            if current_user.role == UserRole.DOCTOR and doctor_id:
                from app.database.collections import COLLECTION_APPOINTMENTS, COLLECTION_CONSULTATIONS
                check_pids = [canonical_patient_id]
                if pat.get("user_id"):
                    check_pids.append(pat["user_id"])
                clean_pids = list(set(check_pids))
                apt_q = {"patient_id": clean_pids[0], "doctor_id": doctor_id} if len(clean_pids) == 1 else {"patient_id": {"$in": clean_pids}, "doctor_id": doctor_id}
                has_rel = (
                    pat.get("primary_physician_id") == doctor_id
                    or await db[COLLECTION_APPOINTMENTS].find_one(apt_q)
                    or await db[COLLECTION_CONSULTATIONS].find_one(apt_q)
                )
                if not has_rel:
                    raise HTTPException(status_code=403, detail="You are not authorized to run AI analysis for this patient.")

        elif current_user.role == UserRole.PATIENT:
            pat = await db[COLLECTION_PATIENTS].find_one({"user_id": current_user.user_id})
            if not pat:
                raise HTTPException(status_code=404, detail="Patient profile not found.")
            canonical_patient_id = pat["patient_id"]
            doctor_id = pat.get("primary_physician_id") or "DOC-RAO-001"
        else:
            canonical_patient_id = target_pid or "PAT-ONE-001"
            doctor_id = "DOC-RAO-001"

        # Document Linkage / Creation with authoritative uploader provenance
        from app.database.collections import COLLECTION_DOCUMENTS
        from app.models.document import DocumentCategory
        final_doc_id = document_id
        if final_doc_id:
            existing_doc = await db[COLLECTION_DOCUMENTS].find_one({"document_id": final_doc_id})
            if existing_doc:
                await db[COLLECTION_DOCUMENTS].update_one(
                    {"document_id": final_doc_id},
                    {"$set": {"ai_analysis_id": analysis_id, "has_ai_analysis": True, "updated_at": utc_now()}}
                )
        else:
            import uuid
            final_doc_id = f"DOC-{uuid.uuid4().hex[:12].upper()}"
            r_val = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
            r_str = str(r_val).strip().lower().replace("userrole.", "")
            if "patient" in r_str:
                uploader_role = "patient"
            elif "doctor" in r_str:
                uploader_role = "doctor"
            elif "admin" in r_str:
                uploader_role = "hospital_admin"
            else:
                uploader_role = "staff"

            uploader_name = getattr(current_user, "full_name", None) or ("Doctor" if uploader_role == "doctor" else "Patient" if uploader_role == "patient" else "Hospital Staff")
            if uploader_role == "doctor" and "doc" in locals() and doc:
                uploader_name = doc.get("full_name") or doc.get("name") or uploader_name
            elif uploader_role == "patient" and "pat" in locals() and pat:
                uploader_name = pat.get("full_name") or f"{pat.get('first_name', '')} {pat.get('last_name', '')}".strip() or uploader_name

            category_enum = DocumentCategory.MRI if norm_id == "BRAIN_MRI" else DocumentCategory.XRAY if norm_id == "CHEST_XRAY" else DocumentCategory.OTHER
            modality_label = "Brain MRI" if norm_id == "BRAIN_MRI" else "Chest X-Ray" if norm_id == "CHEST_XRAY" else mod_cfg.display_name

            new_doc = {
                "document_id": final_doc_id,
                "patient_id": canonical_patient_id,
                "uploaded_by": current_user.user_id,
                "uploaded_by_user_id": current_user.user_id,
                "uploaded_by_role": uploader_role,
                "uploader_role": uploader_role,
                "uploader_name": uploader_name,
                "title": f"{mod_cfg.display_name} Scan",
                "category": category_enum.value,
                "modality": modality_label,
                "file_name": img_key,
                "original_file_name": image.filename or "medical_image.jpg",
                "mime_type": image.content_type or "image/jpeg",
                "file_size_bytes": len(image_bytes),
                "storage_path": img_key,
                "ai_analysis_id": analysis_id,
                "is_deleted": False,
                "created_at": utc_now(),
                "updated_at": utc_now(),
            }
            await db[COLLECTION_DOCUMENTS].insert_one(new_doc)

        now = utc_now()
        model_info = ModelInfo(
            module_id=norm_id,
            name=mod_cfg.display_name,
            version=model_version,
            architecture=mod_cfg.architecture,
            input_size=list(mod_cfg.input_shape[:2]),
            preprocessing=mod_cfg.preprocessing_strategy,
            classification_mode=mod_cfg.classification_mode.value,
        )
        input_info = InputInfo(
            medical_record_id=img_key,
            document_id=final_doc_id,
            record_type=mod_cfg.slug,
            content_type=image.content_type or "image/jpeg",
            checksum=getattr(val_res, "checksum", None),
        )

        analysis_in_db = AIAnalysisInDB(
            analysis_id=analysis_id,
            patient_id=canonical_patient_id,
            doctor_id=doctor_id or "DOC-RAO-001",
            medical_record_id=img_key,
            document_id=final_doc_id,
            model=model_info,
            input=input_info,
            prediction=prediction,
            explainability=explainability,
            status=AIAnalysisStatus.AWAITING_REVIEW,
            requested_by=current_user.user_id,
            started_at=now,
            completed_at=now,
            created_at=now,
            updated_at=now,
        )
        await db[COLLECTION_AI_ANALYSES].insert_one(analysis_in_db.to_mongo_dict())
        await save_in_memory_snapshot(db)
        await log_audit_event(
            db, actor_id=current_user.user_id, role=current_user.role.value,
            action="ai_analysis.completed", resource="ai_analysis", resource_id=analysis_id,
            metadata={"predicted_class": prediction.predicted_class, "confidence": prediction.confidence, "module_id": norm_id}
        )
    except HTTPException:
        raise
    except Exception as persist_err:
        import logging
        logging.getLogger(__name__).warning("Direct infer persistence warning: %s", persist_err)

    return AIDirectInferResponse(
        analysis_id=analysis_id,
        module_id=norm_id,
        display_name=mod_cfg.display_name,
        architecture=mod_cfg.architecture,
        model_version=model_version,
        predicted_class=prediction.predicted_class,
        confidence=prediction.confidence,
        probabilities=probs,
        gradcam_available=gradcam_ok,
        gradcam_b64=gradcam_b64,
    )




# ── Registered AI Modules List Endpoint ──────────────────────────────────────
@router.get(
    "/ai/modules",
    response_model=List[AIModuleInfoResponse],
    summary="List Registered Medical AI Modules",
)
@router.get(
    "/ai/models",
    response_model=List[AIModuleInfoResponse],
    summary="List Registered Medical AI Models",
)
async def list_ai_modules():
    """Returns metadata, modality, status, and availability of all registered medical AI modules."""
    return AIService.list_modules()


# ── Admin AI Operational Insights / Analytics ─────────────────────────────
@router.get(
    "/admin/ai-insights",
    response_model=AIInsightsResponse,
    summary="Hospital Admin AI Operational Insights",
)
@router.get(
    "/ai/analytics",
    response_model=AIInsightsResponse,
    summary="AI Subsystem Operational Analytics",
)
async def get_admin_ai_insights(
    current_user: UserInDB = Depends(require_roles(UserRole.HOSPITAL_ADMIN, UserRole.ADMIN, UserRole.DOCTOR, UserRole.HOSPITAL_STAFF, UserRole.STAFF)),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Fetches aggregated AI system utilization and status metrics calculated from database records."""
    return await AIService.get_admin_ai_insights(db, current_user)



# ── Trigger AI Analysis ────────────────────────────────────────────────────
@router.post(
    "/ai-analyses",
    response_model=AIAnalysisDoctorResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Trigger AI Analysis on a Medical Image Record",
)
async def create_ai_analysis(
    request: AIAnalysisCreateRequest,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """
    Authorized Doctor triggers model inference and Grad-CAM generation for a specified
    medical image module (Chest X-Ray, Brain MRI, Skin Dermoscopy, Retinal Fundus, Bone X-Ray).
    """
    analysis = await AIService.create_analysis(db, current_user, request)
    return AIAnalysisDoctorResponse(**analysis.model_dump())


# ── List AI Analyses ────────────────────────────────────────────────────────
@router.get(
    "/ai-analyses",
    response_model=AIAnalysisListResponse,
    summary="List Paginated AI Analyses",
)
async def list_ai_analyses(
    patient_id: Optional[str] = Query(None, description="Filter by Patient ID"),
    doctor_id: Optional[str] = Query(None, description="Filter by Doctor ID"),
    consultation_id: Optional[str] = Query(None, description="Filter by Consultation ID"),
    medical_record_id: Optional[str] = Query(None, description="Filter by Medical Record ID"),
    status: Optional[str] = Query(None, description="Filter by Status"),
    module_id: Optional[str] = Query(None, description="Filter by Model Module ID (e.g. BRAIN_MRI, CHEST_XRAY)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """List paginated AI analyses filtered by role and permissions."""
    return await AIService.list_analyses(
        db, current_user, patient_id, doctor_id,
        consultation_id, medical_record_id, status, page, page_size,
        module_id=module_id,
    )


# ── Get Single AI Analysis Detail ───────────────────────────────────────────
@router.get(
    "/ai-analyses/{analysis_id}",
    response_model=AIAnalysisDoctorResponse,
    summary="Get AI Analysis Detail",
)
async def get_ai_analysis_detail(
    analysis_id: str,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Retrieve complete AI Analysis details (Doctor/Admin access, or Patient after review)."""
    analysis = await AIService.get_analysis(db, current_user, analysis_id)
    resp_data = analysis.model_dump()
    if current_user.role == UserRole.PATIENT and resp_data.get("doctor_review"):
        # Protect doctor-only internal notes from patient view
        resp_data["doctor_review"]["notes"] = None
    return AIAnalysisDoctorResponse(**resp_data)


# ── Doctor Submit Review ───────────────────────────────────────────────────
@router.post(
    "/ai-analyses/{analysis_id}/review",
    response_model=AIAnalysisDoctorResponse,
    summary="Doctor Submit Review & Clinical Interpretation",
)
async def review_ai_analysis(
    analysis_id: str,
    request: AIReviewRequest,
    current_user: UserInDB = Depends(require_roles(UserRole.DOCTOR, UserRole.HOSPITAL_ADMIN)),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Authorized Doctor reviews AI prediction, adds clinical interpretation, and updates status to REVIEWED."""
    analysis = await AIService.review_analysis(db, current_user, analysis_id, request)
    return AIAnalysisDoctorResponse(**analysis.model_dump())


# ── Doctor Explicit Release ────────────────────────────────────────────────
@router.post(
    "/ai-analyses/{analysis_id}/release",
    response_model=AIAnalysisDoctorResponse,
    summary="Doctor Explicitly Release Reviewed AI Analysis to Patient",
)
async def release_ai_analysis(
    analysis_id: str,
    current_user: UserInDB = Depends(require_roles(UserRole.DOCTOR, UserRole.HOSPITAL_ADMIN, UserRole.ADMIN)),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Authorized Doctor or Admin explicitly releases reviewed AI analysis to make it patient-visible."""
    analysis = await AIService.release_analysis(db, current_user, analysis_id)
    return AIAnalysisDoctorResponse(**analysis.model_dump())


# ── Get Patient-Safe Report ────────────────────────────────────────────────
@router.get(
    "/ai-analyses/{analysis_id}/report",
    response_model=AIAnalysisPatientReportResponse,
    summary="Get Patient-Safe AI Report",
)
async def get_patient_safe_report(
    analysis_id: str,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Patient retrieves own reviewed patient-safe AI analysis report."""
    return await AIService.get_patient_report(db, current_user, analysis_id)


# ── Get Grad-CAM Overlay Image ─────────────────────────────────────────────
@router.get(
    "/ai-analyses/{analysis_id}/gradcam",
    summary="Retrieve Grad-CAM Explainability Overlay Image",
)
async def get_gradcam_image(
    analysis_id: str,
    current_user: UserInDB = Depends(get_current_active_user_strict_header),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Authorized clinician retrieves Grad-CAM PNG heatmap overlay image.
    
    STRICT SECURITY REQUIREMENT: Only accepts Bearer token via Authorization header.
    URL query parameter '?token=' is explicitly rejected.
    """
    file_bytes, content_type = await AIService.get_gradcam_artifact(db, current_user, analysis_id)
    return Response(content=file_bytes, media_type=content_type)


# ── Get Original Input Image ───────────────────────────────────────────────
@router.get(
    "/ai-analyses/{analysis_id}/image",
    summary="Retrieve Original Medical Input Image Used for AI Analysis",
)
async def get_original_image(
    analysis_id: str,
    current_user: UserInDB = Depends(get_current_active_user_strict_header),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Authorized clinician or patient retrieves original medical input image used for inference.
    
    STRICT SECURITY REQUIREMENT: Only accepts Bearer token via Authorization header.
    URL query parameter '?token=' is explicitly rejected.
    """
    file_bytes, content_type = await AIService.get_original_image_artifact(db, current_user, analysis_id)
    return Response(content=file_bytes, media_type=content_type)


# ── Admin AI Operational Insights ──────────────────────────────────────────
@router.get(
    "/admin/ai-insights",
    response_model=AIInsightsResponse,
    summary="Hospital Admin AI Operational Insights",
)
async def get_admin_ai_insights(
    current_user: UserInDB = Depends(require_roles(UserRole.HOSPITAL_ADMIN)),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Hospital Admin fetches aggregated AI system utilization and status metrics."""
    return await AIService.get_admin_ai_insights(db, current_user)
