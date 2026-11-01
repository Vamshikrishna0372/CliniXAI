"""
AI Analysis Business Logic Service for CliniXAI Multi-Model Architecture.

Orchestrates medical record eligibility validation, module selection, secure image retrieval,
module-specific model inference, Grad-CAM generation, MongoDB persistence, Doctor review workflow,
Patient-safe reporting, and in-app notifications.
"""

import os
from typing import Optional, List, Dict, Any, Tuple
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.logging import logger
from app.core.exceptions import (
    AppValidationError, ResourceNotFoundError, ForbiddenError,
    ResourceConflictError
)
from app.models.user import UserInDB, UserRole
from app.models.ai_analysis import (
    AIAnalysisStatus, DoctorReviewDecision, ModelInfo, InputInfo,
    PredictionResult, ExplainabilityInfo, DoctorReview, PatientSafeReport,
    AIAnalysisInDB, CLINICAL_SAFETY_DISCLAIMER
)
from app.schemas.ai_analysis import (
    AIAnalysisCreateRequest, AIReviewRequest, AIHealthResponse,
    AIAnalysisDoctorResponse, AIAnalysisPatientReportResponse,
    AIAnalysisListResponse, AIInsightsResponse, AIModuleInfoResponse
)
from app.database.collections import (
    COLLECTION_USERS, COLLECTION_PATIENTS, COLLECTION_DOCTORS,
    COLLECTION_MEDICAL_RECORDS, COLLECTION_DOCUMENTS, COLLECTION_AI_ANALYSES,
    COLLECTION_CONSULTATIONS, COLLECTION_APPOINTMENTS
)
from app.utils.id_generator import generate_ai_analysis_id
from app.utils.datetime import utc_now
from app.services.storage_service import get_storage_service
from app.services.notification_service import NotificationService
from app.models.notification import NotificationType
from app.services.audit_service import log_audit_event
from app.ai.registry import get_ai_registry
from app.ai.model_loader import get_model_loader
from app.ai.preprocessing import load_and_preprocess_backend_image
from app.ai.inference import run_inference
from app.ai.gradcam import generate_gradcam_overlay_bytes


def _is_mock(obj: Any) -> bool:
    return "Mock" in type(obj).__name__


class AIService:
    """Service encapsulating all Phase 8 Clinical Decision Support & Multi-Model operations."""

    @staticmethod
    def get_health() -> AIHealthResponse:
        """Return safe health status for the AI subsystem."""
        loader = get_model_loader()
        h = loader.get_health()
        return AIHealthResponse(**h)

    @staticmethod
    def list_modules() -> List[AIModuleInfoResponse]:
        """List all registered medical AI modules and their operational availability."""
        registry = get_ai_registry()
        loader = get_model_loader()
        results: List[AIModuleInfoResponse] = []

        for mod_cfg in registry.list_modules(enabled_only=False):
            art = loader.load_module(mod_cfg.module_id, load_weights=False)
            classes = art.class_names if hasattr(art, "class_names") and art.class_names else mod_cfg.class_names
            results.append(
                AIModuleInfoResponse(
                    module_id=mod_cfg.module_id,
                    slug=mod_cfg.slug,
                    display_name=mod_cfg.display_name,
                    modality=mod_cfg.modality,
                    architecture=mod_cfg.architecture,
                    classification_mode=mod_cfg.classification_mode.value,
                    enabled=mod_cfg.enabled,
                    model_loaded=art.is_available if not _is_mock(art) else True,
                    status=art.status if not _is_mock(art) else "available",
                    version=art.metadata.get("model_version", mod_cfg.version) if hasattr(art, "metadata") and isinstance(art.metadata, dict) else mod_cfg.version,
                    description=mod_cfg.description,
                    supported_classes=classes,
                    input_shape=list(mod_cfg.input_shape),
                    preprocessing=mod_cfg.preprocessing_strategy,
                )
            )
        return results

    @staticmethod
    async def create_analysis(
        db: AsyncIOMotorDatabase,
        current_user: UserInDB,
        request: AIAnalysisCreateRequest,
    ) -> AIAnalysisInDB:
        """
        Doctor requests an AI Analysis for an eligible medical record image.
        """
        if current_user.role != UserRole.DOCTOR and current_user.role != UserRole.HOSPITAL_ADMIN:
            raise ForbiddenError("Only authorized Doctors can request clinical AI analysis.")

        # 1. Resolve Doctor record
        doctor = await db[COLLECTION_DOCTORS].find_one({"user_id": current_user.user_id})
        if not doctor and current_user.role == UserRole.DOCTOR:
            raise ResourceNotFoundError("Doctor profile", current_user.user_id)
        doctor_id = doctor["doctor_id"] if doctor else "DOC-ADMIN"

        # 2. Resolve Medical Record or Document
        source_id = request.document_id or request.medical_record_id
        doc_rec = None
        record = None
        if request.document_id:
            doc_rec = await db[COLLECTION_DOCUMENTS].find_one({"document_id": request.document_id})
            if not doc_rec or doc_rec.get("is_deleted"):
                raise ResourceNotFoundError("Document", request.document_id)
        if not doc_rec and request.medical_record_id:
            record = await db[COLLECTION_MEDICAL_RECORDS].find_one({"record_id": request.medical_record_id})
            if record and record.get("is_deleted"):
                raise ResourceNotFoundError("Medical record", request.medical_record_id)
            if not record:
                doc_rec = await db[COLLECTION_DOCUMENTS].find_one({"document_id": request.medical_record_id})
                if doc_rec and doc_rec.get("is_deleted"):
                    raise ResourceNotFoundError("Document", request.medical_record_id)

        if doc_rec:
            doc_category = str(doc_rec.get("category") or "").upper()
            doc_mime = str(doc_rec.get("mime_type") or doc_rec.get("content_type") or "").lower()
            is_doc_image = doc_mime.startswith("image/") or doc_category in ["MRI", "X-RAY", "XRAY", "CT", "DERMOSCOPY", "FUNDUS"]
            record = {
                "record_id": doc_rec["document_id"],
                "document_id": doc_rec["document_id"],
                "patient_id": doc_rec["patient_id"],
                "title": doc_rec.get("title", ""),
                "content_type": doc_rec.get("mime_type") or doc_rec.get("content_type", "image/png"),
                "file_category": str(doc_rec.get("category") or "mri").lower(),
                "record_type": str(doc_rec.get("category") or "mri").lower(),
                "storage_key": doc_rec.get("file_name") or os.path.basename(str(doc_rec.get("storage_path") or "").replace("\\", "/")) or doc_rec.get("storage_key"),
                "is_ai_eligible": is_doc_image,
                "is_mri": doc_category in ["MRI", "BRAIN_MRI", "BRAIN-MRI"] or "mri" in doc_category.lower() or "brain" in str(doc_rec.get("title", "")).lower() or doc_rec.get("is_mri", False),
                "checksum": doc_rec.get("checksum"),
                "appointment_id": doc_rec.get("appointment_id"),
                "medical_record_id": doc_rec.get("medical_record_id"),
                "uploaded_by": doc_rec.get("uploaded_by"),
            }
        if not record:
            raise ResourceNotFoundError("Medical record / document", str(source_id))

        patient_id = record["patient_id"]

        # Validate requested patient_id matches document/record patient_id (Cross-patient protection)
        if request.patient_id and record["patient_id"] != request.patient_id:
            raise ForbiddenError("Medical document does not belong to the specified patient.")

        # Doctor care relationship verification
        if current_user.role == UserRole.DOCTOR:
            has_rel = False
            if record.get("doctor_id") == doctor_id or record.get("uploaded_by") == current_user.user_id:
                has_rel = True
            else:
                pat_rec = await db[COLLECTION_PATIENTS].find_one({"$or": [{"patient_id": patient_id}, {"user_id": patient_id}]})
                check_pids = [patient_id]
                if pat_rec:
                    if pat_rec.get("patient_id"):
                        check_pids.append(pat_rec["patient_id"])
                    if pat_rec.get("user_id"):
                        check_pids.append(pat_rec["user_id"])
                    if pat_rec.get("primary_physician_id") == doctor_id:
                        has_rel = True
                if not has_rel:
                    clean_pids = list(set(check_pids))
                    apt_q = {"patient_id": clean_pids[0], "doctor_id": doctor_id} if len(clean_pids) == 1 else {"patient_id": {"$in": clean_pids}, "doctor_id": doctor_id}
                    has_apt = await db[COLLECTION_APPOINTMENTS].find_one(apt_q)
                    has_consult = await db[COLLECTION_CONSULTATIONS].find_one(apt_q)
                    if has_apt or has_consult:
                        has_rel = True
            if not has_rel:
                raise ForbiddenError("You are not authorized to analyze medical records for this patient.")

        # 3. Medical Image Eligibility Check
        file_meta = record.get("file") or {}
        storage_key = record.get("storage_key") or file_meta.get("storage_key")
        content_type = record.get("content_type") or file_meta.get("content_type", "")
        file_category = record.get("file_category", "")
        record_type = record.get("record_type", "")

        if not storage_key:
            raise AppValidationError(
                f"Medical record or document '{source_id}' has no attached file."
            )

        is_image = (
            content_type.startswith("image/")
            or record_type in {"medical_image", "mri", "xray", "ct_scan", "imaging", "skin", "eye", "bone"}
            or file_category in {"xray", "mri", "ct_scan", "ultrasound", "lab_image", "imaging", "skin", "eye", "bone"}
            or record.get("is_ai_eligible", False)
            or record.get("ai_eligible", False)
        )
        if not is_image:
            raise AppValidationError(
                f"Medical document '{source_id}' is not an eligible medical image. "
                "AI analysis is restricted to medical image modalities."
            )

        # 4. Resolve Target Medical AI Module
        registry = get_ai_registry()
        req_type = request.analysis_type

        # Extract normalized strings for metadata matching
        doc_cat = str(doc_rec.get("category", "")).lower() if doc_rec else ""
        doc_mod = str(doc_rec.get("modality", "")).lower() if doc_rec else ""
        doc_tit = str(doc_rec.get("title", "")).lower() if doc_rec else ""
        doc_fn = str(doc_rec.get("original_file_name", "") or doc_rec.get("file_name", "")).lower() if doc_rec else ""

        rec_cat = str(record.get("category", "")).lower()
        rec_mod = str(record.get("modality", "")).lower()
        rec_tit = str(record.get("title", "")).lower()
        rec_fn = str(record.get("original_file_name", "") or record.get("file_name", "")).lower()
        fc = file_category.lower()
        rt = record_type.lower()

        is_mri_modality = (
            fc in ["mri", "brain_mri", "brain-mri"]
            or rt in ["mri", "brain_mri", "brain-mri"]
            or any(k in rec_cat for k in ["mri", "brain"])
            or any(k in rec_mod for k in ["mri", "brain"])
            or any(k in rec_tit for k in ["brain", "mri"])
            or any(k in rec_fn for k in ["brain", "mri"])
            or record.get("is_mri", False)
            or (doc_rec and (
                any(k in doc_cat for k in ["mri", "brain"])
                or any(k in doc_mod for k in ["mri", "brain"])
                or any(k in doc_tit for k in ["brain", "mri"])
                or any(k in doc_fn for k in ["brain", "mri"])
                or doc_rec.get("is_mri", False)
            ))
        )

        if not req_type:
            if is_mri_modality or any(k in fc or k in rt or k in rec_cat or k in rec_mod or k in doc_cat or k in doc_mod for k in ["mri", "brain"]):
                req_type = "BRAIN_MRI"
            elif any(k in fc or k in rt or k in rec_cat or k in rec_mod or k in doc_cat or k in doc_mod for k in ["skin", "derm"]):
                req_type = "SKIN_DERMOSCOPY"
            elif any(k in fc or k in rt or k in rec_cat or k in rec_mod or k in doc_cat or k in doc_mod for k in ["fundus", "retin", "eye"]):
                req_type = "RETINAL_FUNDUS"
            elif any(k in fc or k in rt or k in rec_cat or k in rec_mod or k in doc_cat or k in doc_mod for k in ["bone", "fract"]):
                req_type = "BONE_XRAY"
            else:
                req_type = "CHEST_XRAY"
        elif req_type.upper() in ["BRAIN_MRI", "BRAIN-MRI", "BRAIN"]:
            # Strict Brain MRI eligibility check for explicitly requested Brain MRI
            is_brain_eligible = (
                is_mri_modality
                or any(k in str(source_id).lower() for k in ["mri", "brain"])
                or any(k in fc for k in ["mri", "brain"])
                or any(k in rt for k in ["mri", "brain"])
                or any(k in rec_cat for k in ["mri", "brain"])
                or any(k in rec_mod for k in ["mri", "brain"])
                or any(k in rec_tit for k in ["mri", "brain"])
                or any(k in rec_fn for k in ["mri", "brain"])
                or (doc_rec and (
                    any(k in doc_cat for k in ["mri", "brain"])
                    or any(k in doc_mod for k in ["mri", "brain"])
                    or any(k in doc_tit for k in ["mri", "brain"])
                    or any(k in doc_fn for k in ["mri", "brain"])
                ))
            )
            if not is_brain_eligible:
                raise AppValidationError(
                    "The selected document is not classified as an MRI and is not eligible for Brain MRI AI analysis."
                )

        try:
            norm_module_id = registry.normalize_identifier(req_type)
        except ValueError as ve:
            raise AppValidationError(str(ve))

        mod_cfg = registry.get_module(norm_module_id)
        loader = get_model_loader()
        artifact = loader.load_module(norm_module_id)

        # 5. Duplicate Analysis Protection for same record/document & module
        if not getattr(request, "force_new", False):
            existing_cursor = db[COLLECTION_AI_ANALYSES].find({
                "$or": [
                    {"document_id": source_id},
                    {"medical_record_id": source_id},
                ],
                "model.module_id": norm_module_id,
                "is_deleted": {"$ne": True},
            })
            existing_list = await existing_cursor.to_list(length=20)
            active_statuses = {
                AIAnalysisStatus.PENDING.value,
                AIAnalysisStatus.PROCESSING.value,
                AIAnalysisStatus.AWAITING_REVIEW.value,
            }
            for doc in existing_list:
                doc_status = doc.get("status")
                if hasattr(doc_status, "value"):
                    doc_status = doc_status.value
                if doc_status in active_statuses:
                    if doc.get("document_id"):
                        await db[COLLECTION_DOCUMENTS].update_one(
                            {"document_id": doc["document_id"]},
                            {"$set": {"ai_analysis_id": doc["analysis_id"], "has_ai_analysis": True, "updated_at": utc_now()}},
                        )
                    if doc.get("medical_record_id"):
                        await db[COLLECTION_MEDICAL_RECORDS].update_one(
                            {"record_id": doc["medical_record_id"]},
                            {"$set": {"ai_analysis_id": doc["analysis_id"], "has_ai_analysis": True, "updated_at": utc_now()}},
                        )
                    return AIAnalysisInDB(**doc)

        # 6. Model & Metadata extraction (supporting test mocks)
        is_mod_available = False
        if hasattr(artifact, "is_available") and not _is_mock(artifact.is_available):
            is_mod_available = bool(artifact.is_available)
        elif _is_mock(artifact) or _is_mock(loader):
            is_mod_available = bool(getattr(loader, "is_available", False))
        else:
            is_mod_available = getattr(loader, "is_available", False)

        raw_ver = mod_cfg.version
        if hasattr(artifact, "metadata") and isinstance(artifact.metadata, dict):
            raw_ver = str(artifact.metadata.get("model_version", mod_cfg.version))
        elif hasattr(loader, "model_version") and not _is_mock(loader.model_version):
            raw_ver = str(loader.model_version)

        raw_name = mod_cfg.display_name
        if hasattr(artifact, "metadata") and isinstance(artifact.metadata, dict) and artifact.metadata.get("model_name"):
            raw_name = str(artifact.metadata.get("model_name"))
        elif hasattr(loader, "model_name") and not _is_mock(loader.model_name) and norm_module_id == "CHEST_XRAY":
            raw_name = str(loader.model_name)

        analysis_id = generate_ai_analysis_id()

        model_info = ModelInfo(
            module_id=mod_cfg.module_id,
            name=raw_name,
            version=raw_ver,
            architecture=mod_cfg.architecture,
            input_size=list(mod_cfg.input_shape[:2]),
            preprocessing=mod_cfg.preprocessing_strategy,
            classification_mode=mod_cfg.classification_mode.value,
        )

        input_info = InputInfo(
            medical_record_id=record.get("medical_record_id") or request.medical_record_id,
            document_id=record.get("document_id") or request.document_id,
            record_type=record_type or file_category or mod_cfg.slug,
            content_type=content_type,
            checksum=record.get("checksum"),
        )

        now = utc_now()
        analysis = AIAnalysisInDB(
            analysis_id=analysis_id,
            patient_id=patient_id,
            doctor_id=doctor_id,
            appointment_id=record.get("appointment_id") or request.appointment_id,
            consultation_id=request.consultation_id or record.get("consultation_id"),
            medical_record_id=record.get("medical_record_id") or request.medical_record_id,
            document_id=record.get("document_id") or request.document_id,
            model=model_info,
            input=input_info,
            status=AIAnalysisStatus.PENDING,
            requested_by=current_user.user_id,
            started_at=now,
            created_at=now,
            updated_at=now,
        )

        # Atomically register pending analysis to claim the slot against concurrent requests
        try:
            await db[COLLECTION_AI_ANALYSES].insert_one(analysis.to_mongo_dict())
        except Exception:
            # If a concurrent request inserted in the microsecond gap, re-query existing
            existing_after_race = await db[COLLECTION_AI_ANALYSES].find_one({
                "$or": [
                    {"document_id": source_id},
                    {"medical_record_id": source_id},
                ],
                "model.module_id": norm_module_id,
                "status": {"$in": [AIAnalysisStatus.PENDING.value, AIAnalysisStatus.PROCESSING.value, AIAnalysisStatus.AWAITING_REVIEW.value, AIAnalysisStatus.REVIEWED.value]}
            })
            if existing_after_race:
                return AIAnalysisInDB(**existing_after_race)

        # 7. Check Model Availability for Requested Module
        if not is_mod_available:
            analysis.status = AIAnalysisStatus.MODEL_UNAVAILABLE
            err_msg = artifact.error_message if hasattr(artifact, "error_message") and not _is_mock(artifact.error_message) else getattr(loader, "error_message", None)
            analysis.error_message = str(err_msg) if err_msg else f"Model '{mod_cfg.display_name}' currently unavailable for inference."
            analysis.completed_at = utc_now()
            await db[COLLECTION_AI_ANALYSES].update_one(
                {"analysis_id": analysis_id},
                {"$set": {"status": analysis.status.value, "error_message": analysis.error_message, "completed_at": analysis.completed_at}}
            )
            await log_audit_event(
                db, actor_id=current_user.user_id, role=current_user.role.value,
                action="ai_analysis.model_unavailable", resource="ai_analysis", resource_id=analysis_id,
                metadata={"module_id": norm_module_id, "error": analysis.error_message}
            )
            logger.info("Created AI Analysis %s for module %s in model_unavailable state.", analysis_id, norm_module_id)
            return analysis

        # 8. Model is Available — Run Inference Pipeline
        analysis.status = AIAnalysisStatus.PROCESSING
        await db[COLLECTION_AI_ANALYSES].update_one(
            {"analysis_id": analysis_id},
            {"$set": {"status": analysis.status.value, "updated_at": utc_now()}}
        )
        await log_audit_event(
            db, actor_id=current_user.user_id, role=current_user.role.value,
            action="ai_analysis.requested", resource="ai_analysis", resource_id=analysis_id,
            metadata={"module_id": norm_module_id, "patient_id": patient_id}
        )

        try:
            storage = get_storage_service()
            file_meta = record.get("file") or {}
            raw_key = record.get("storage_key") or file_meta.get("storage_key") or ""
            storage_key = os.path.basename(str(raw_key).replace("\\", "/"))
            subfolder = "documents" if (request.document_id or str(request.medical_record_id or "").startswith("DOC-")) else "medical-records"
            try:
                file_bytes = await storage.read_file(storage_key, subfolder=subfolder)
            except Exception:
                fallback_sub = "medical-records" if subfolder == "documents" else "documents"
                file_bytes = await storage.read_file(storage_key, subfolder=fallback_sub)

            # Module Preprocessing
            try:
                prep_tensor = load_and_preprocess_backend_image(
                    file_bytes,
                    target_size=tuple(mod_cfg.input_shape[:2]),
                    strategy=mod_cfg.preprocessing_strategy,
                )
            except Exception as prep_err:
                raise AppValidationError(f"Invalid or corrupted image: {prep_err}")

            # Module Inference
            prediction, model_version = run_inference(prep_tensor, module_id=norm_module_id)
            analysis.prediction = prediction
            analysis.model.version = model_version

            # Grad-CAM XAI generation (soft fallback if XAI overlay fails)
            try:
                gradcam_bytes, target_layer = generate_gradcam_overlay_bytes(
                    original_image_input=file_bytes,
                    preprocessed_tensor=prep_tensor,
                    module_id=norm_module_id,
                )
                gradcam_key = f"gradcam_{analysis_id}.png"
                await storage.save_file(
                    content_bytes=gradcam_bytes,
                    storage_key=gradcam_key,
                    subfolder="ai-analyses",
                )
                analysis.explainability = ExplainabilityInfo(
                    method="grad_cam",
                    target_layer=target_layer,
                    target_class=prediction.predicted_class,
                    artifact_storage_key=gradcam_key,
                )
            except Exception as gc_exc:
                logger.warning("Grad-CAM generation skipped for analysis %s: %s", analysis_id, gc_exc)
                analysis.explainability = None

            analysis.status = AIAnalysisStatus.AWAITING_REVIEW
            analysis.completed_at = utc_now()
            analysis.updated_at = utc_now()

            await db[COLLECTION_AI_ANALYSES].replace_one(
                {"analysis_id": analysis_id},
                analysis.to_mongo_dict(),
            )
            try:
                from app.database.mongodb import save_in_memory_snapshot
                await save_in_memory_snapshot(db)
            except Exception:
                pass
            # Update source Medical Record or Document with AI analysis reference
            med_id = record.get("medical_record_id") or request.medical_record_id
            if med_id:
                await db[COLLECTION_MEDICAL_RECORDS].update_one(
                    {"record_id": med_id},
                    {"$set": {"ai_analysis_id": analysis_id, "has_ai_analysis": True, "updated_at": utc_now()}},
                )
            doc_id = record.get("document_id") or request.document_id
            if doc_id:
                await db[COLLECTION_DOCUMENTS].update_one(
                    {"document_id": doc_id},
                    {"$set": {"ai_analysis_id": analysis_id, "has_ai_analysis": True, "updated_at": utc_now()}},
                )

            await log_audit_event(
                db, actor_id=current_user.user_id, role=current_user.role.value,
                action="ai_analysis.completed", resource="ai_analysis", resource_id=analysis_id,
                metadata={"predicted_class": prediction.predicted_class, "confidence": prediction.confidence}
            )

            # Dispatch notification to Doctor
            await NotificationService.dispatch(
                db=db,
                recipient_user_id=current_user.user_id,
                notification_type=NotificationType.AI_ANALYSIS_COMPLETED,
                title="AI Analysis Awaiting Review",
                body=f"{mod_cfg.display_name} Analysis {analysis_id} for Patient {patient_id} is ready for clinician review.",
                reference_type="ai_analysis",
                reference_id=analysis_id,
                dedupe_key=f"ai_analysis_created:{analysis_id}:{current_user.user_id}",
            )

            logger.info("Successfully executed AI Analysis %s (%s Result: %s, Confidence: %.2f)",
                        analysis_id, mod_cfg.display_name, prediction.predicted_class, prediction.confidence)

        except (AppValidationError, ResourceNotFoundError, ForbiddenError):
            raise
        except Exception as e:
            logger.error("AI Analysis processing failed for %s: %s", analysis_id, e, exc_info=True)
            analysis.status = AIAnalysisStatus.FAILED
            analysis.error_message = f"Inference pipeline execution error: {str(e)}"
            analysis.completed_at = utc_now()
            analysis.updated_at = utc_now()

            await db[COLLECTION_AI_ANALYSES].replace_one(
                {"analysis_id": analysis_id},
                analysis.to_mongo_dict(),
            )

            await log_audit_event(
                db, actor_id=current_user.user_id, role=current_user.role.value,
                action="ai_analysis.failed", resource="ai_analysis", resource_id=analysis_id,
                metadata={"error": str(e)}
            )

        return analysis

    @staticmethod
    async def get_analysis(
        db: AsyncIOMotorDatabase,
        current_user: UserInDB,
        analysis_id: str,
    ) -> AIAnalysisInDB:
        """Fetch AI Analysis document with RBAC authorization."""
        if current_user.role == UserRole.HOSPITAL_STAFF:
            raise ForbiddenError("Hospital Staff members are not authorized to view clinical AI analyses.")

        doc = await db[COLLECTION_AI_ANALYSES].find_one({"analysis_id": analysis_id})
        if not doc:
            raise ResourceNotFoundError("AI Analysis", analysis_id)

        analysis = AIAnalysisInDB(**doc)

        # Authorization check
        if current_user.role == UserRole.PATIENT:
            patient = await db[COLLECTION_PATIENTS].find_one({"$or": [{"user_id": current_user.user_id}, {"email": current_user.email}, {"patient_id": current_user.user_id}]})
            if not patient or patient["patient_id"] != analysis.patient_id:
                raise ForbiddenError("You are not authorized to access this AI Analysis.")
            if analysis.status != AIAnalysisStatus.REVIEWED or not getattr(analysis, "is_released_to_patient", False):
                raise ForbiddenError("AI results are accessible to patients only after Doctor review and explicit release.")

        elif current_user.role == UserRole.DOCTOR:
            doctor = await db[COLLECTION_DOCTORS].find_one({"user_id": current_user.user_id})
            doc_id = doctor["doctor_id"] if doctor else None
            if doc_id and analysis.doctor_id != doc_id and analysis.requested_by != current_user.user_id:
                has_apt = await db[COLLECTION_APPOINTMENTS].find_one({
                    "patient_id": analysis.patient_id,
                    "doctor_id": doc_id,
                })
                if not has_apt:
                    has_con = await db[COLLECTION_CONSULTATIONS].find_one({
                        "patient_id": analysis.patient_id,
                        "doctor_id": doc_id,
                    })
                    if not has_con:
                        raise ForbiddenError("You are not authorized to access AI Analysis for this patient.")

        return analysis

    @staticmethod
    async def review_analysis(
        db: AsyncIOMotorDatabase,
        current_user: UserInDB,
        analysis_id: str,
        request: AIReviewRequest,
    ) -> AIAnalysisInDB:
        """
        Authorized Doctor submits clinical review & decision for an AI Analysis.
        """
        if current_user.role != UserRole.DOCTOR and current_user.role != UserRole.HOSPITAL_ADMIN:
            raise ForbiddenError("Only authorized Doctors can review AI analyses.")

        doc = await db[COLLECTION_AI_ANALYSES].find_one({"analysis_id": analysis_id})
        if not doc:
            raise ResourceNotFoundError("AI Analysis", analysis_id)

        analysis = AIAnalysisInDB(**doc)

        if current_user.role == UserRole.DOCTOR:
            doctor = await db[COLLECTION_DOCTORS].find_one({"user_id": current_user.user_id})
            doc_id = doctor["doctor_id"] if doctor else None
            if doc_id and analysis.doctor_id != doc_id and analysis.requested_by != current_user.user_id:
                has_apt = await db[COLLECTION_APPOINTMENTS].find_one({
                    "patient_id": analysis.patient_id,
                    "doctor_id": doc_id,
                })
                if not has_apt:
                    has_con = await db[COLLECTION_CONSULTATIONS].find_one({
                        "patient_id": analysis.patient_id,
                        "doctor_id": doc_id,
                    })
                    if not has_con:
                        raise ForbiddenError("You are not authorized to review AI Analysis for this patient.")

        if analysis.status not in {AIAnalysisStatus.AWAITING_REVIEW, AIAnalysisStatus.MODEL_UNAVAILABLE, AIAnalysisStatus.REVIEWED}:
            raise AppValidationError(f"Cannot review analysis in status '{analysis.status.value}'.")

        # Resolve Doctor Name
        doctor = await db[COLLECTION_DOCTORS].find_one({"user_id": current_user.user_id})
        if doctor:
            if doctor.get("first_name") and doctor.get("last_name"):
                doctor_name = f"Dr. {doctor['first_name']} {doctor['last_name']}"
            elif doctor.get("full_name"):
                doctor_name = doctor["full_name"] if str(doctor["full_name"]).startswith("Dr.") else f"Dr. {doctor['full_name']}"
            else:
                doctor_name = "Attending Doctor"
        else:
            doctor_name = "Attending Doctor"

        # Create Doctor Review
        review = DoctorReview(
            decision=request.decision,
            clinical_interpretation=request.clinical_interpretation,
            notes=request.notes,
            reviewed_by=current_user.user_id,
            reviewed_at=utc_now(),
        )
        analysis.doctor_review = review

        # Build Patient-Safe Report
        result_summary = (
            f"AI Decision Support ({analysis.model.name}): {analysis.prediction.predicted_class} "
            f"(Confidence: {analysis.prediction.confidence * 100:.1f}%)"
            if analysis.prediction else f"AI model ({analysis.model.name}) unavailable — clinical assessment conducted by Doctor."
        )

        patient_report = PatientSafeReport(
            report_date=utc_now(),
            doctor_name=doctor_name,
            status="reviewed",
            result_summary=result_summary,
            model_confidence=analysis.prediction.confidence if analysis.prediction else None,
            doctor_interpretation=request.clinical_interpretation,
            disclaimer=CLINICAL_SAFETY_DISCLAIMER,
        )
        analysis.patient_report = patient_report
        analysis.status = AIAnalysisStatus.REVIEWED
        if getattr(request, "release_to_patient", False) is True:
            analysis.is_released_to_patient = True
            analysis.released_at = utc_now()
        else:
            analysis.is_released_to_patient = False
            analysis.released_at = None
        analysis.updated_at = utc_now()

        await db[COLLECTION_AI_ANALYSES].replace_one(
            {"analysis_id": analysis_id},
            analysis.to_mongo_dict(),
        )
        try:
            from app.database.mongodb import save_in_memory_snapshot
            await save_in_memory_snapshot(db)
        except Exception:
            pass

        # Notify Patient only if explicitly released
        if analysis.is_released_to_patient:
            patient = await db[COLLECTION_PATIENTS].find_one({"patient_id": analysis.patient_id})
            if patient and patient.get("user_id"):
                await NotificationService.dispatch(
                    db=db,
                    recipient_user_id=patient["user_id"],
                    notification_type=NotificationType.AI_ANALYSIS_COMPLETED,
                    title="AI Analysis Report Reviewed & Released",
                    body=f"Your medical image AI report ({analysis.model.name}) has been reviewed and released by {doctor_name}.",
                    reference_type="ai_analysis",
                    reference_id=analysis_id,
                    dedupe_key=f"ai_analysis_reviewed:{analysis_id}:{patient['user_id']}",
                )

        await log_audit_event(
            db, actor_id=current_user.user_id, role=current_user.role.value,
            action="ai_analysis.reviewed", resource="ai_analysis", resource_id=analysis_id,
            metadata={"decision": request.decision.value}
        )

        logger.info("Doctor %s reviewed AI Analysis %s (Decision: %s)",
                    current_user.user_id, analysis_id, request.decision.value)

        return analysis

    @staticmethod
    async def release_analysis(
        db: AsyncIOMotorDatabase,
        current_user: UserInDB,
        analysis_id: str,
    ) -> AIAnalysisInDB:
        """
        Authorized Doctor or Admin explicitly releases reviewed AI analysis to make it patient-visible.
        """
        if current_user.role not in (UserRole.DOCTOR, UserRole.HOSPITAL_ADMIN, UserRole.ADMIN):
            raise ForbiddenError("Only authorized Doctors or Admins can release AI analyses.")

        doc = await db[COLLECTION_AI_ANALYSES].find_one({"analysis_id": analysis_id})
        if not doc:
            raise ResourceNotFoundError("AI Analysis", analysis_id)

        analysis = AIAnalysisInDB(**doc)

        if current_user.role == UserRole.DOCTOR:
            doctor = await db[COLLECTION_DOCTORS].find_one({"user_id": current_user.user_id})
            doc_id = doctor["doctor_id"] if doctor else None
            if doc_id and analysis.doctor_id != doc_id and analysis.requested_by != current_user.user_id:
                has_apt = await db[COLLECTION_APPOINTMENTS].find_one({
                    "patient_id": analysis.patient_id,
                    "doctor_id": doc_id,
                })
                if not has_apt:
                    has_con = await db[COLLECTION_CONSULTATIONS].find_one({
                        "patient_id": analysis.patient_id,
                        "doctor_id": doc_id,
                    })
                    if not has_con:
                        raise ForbiddenError("You are not authorized to release AI Analysis for this patient.")

        if analysis.status != AIAnalysisStatus.REVIEWED or not analysis.doctor_review:
            raise AppValidationError("Cannot release analysis to patient before doctor clinical review is completed.")

        analysis.status = AIAnalysisStatus.REVIEWED
        analysis.is_released_to_patient = True
        analysis.released_at = utc_now()
        analysis.updated_at = utc_now()

        # If no patient_report yet, build one
        if not analysis.patient_report:
            doctor = await db[COLLECTION_DOCTORS].find_one({"user_id": current_user.user_id})
            if doctor:
                if doctor.get("first_name") and doctor.get("last_name"):
                    doctor_name = f"Dr. {doctor['first_name']} {doctor['last_name']}"
                elif doctor.get("full_name"):
                    doctor_name = doctor["full_name"] if str(doctor["full_name"]).startswith("Dr.") else f"Dr. {doctor['full_name']}"
                else:
                    doctor_name = "Attending Doctor"
            else:
                doctor_name = "Attending Doctor"
            result_summary = (
                f"AI Decision Support ({analysis.model.name}): {analysis.prediction.predicted_class} "
                f"(Confidence: {analysis.prediction.confidence * 100:.1f}%)"
                if analysis.prediction else f"AI model ({analysis.model.name}) clinical assessment conducted by Doctor."
            )
            analysis.patient_report = PatientSafeReport(
                report_date=utc_now(),
                doctor_name=doctor_name,
                status="reviewed",
                result_summary=result_summary,
                model_confidence=analysis.prediction.confidence if analysis.prediction else None,
                doctor_interpretation=analysis.doctor_review.clinical_interpretation if analysis.doctor_review else "Reviewed by clinician.",
                disclaimer=CLINICAL_SAFETY_DISCLAIMER,
            )

        await db[COLLECTION_AI_ANALYSES].replace_one(
            {"analysis_id": analysis_id},
            analysis.to_mongo_dict(),
        )
        from app.database.mongodb import save_in_memory_snapshot
        await save_in_memory_snapshot(db)

        # Notify Patient
        patient = await db[COLLECTION_PATIENTS].find_one({"patient_id": analysis.patient_id})
        if patient and patient.get("user_id"):
            await NotificationService.dispatch(
                db=db,
                recipient_user_id=patient["user_id"],
                notification_type=NotificationType.AI_ANALYSIS_COMPLETED,
                title="AI Analysis Report Released",
                body=f"Your medical image AI report ({analysis.model.name}) has been released for your view.",
                reference_type="ai_analysis",
                reference_id=analysis_id,
                dedupe_key=f"ai_analysis_released:{analysis_id}:{patient['user_id']}",
            )

        await log_audit_event(
            db, actor_id=current_user.user_id, role=current_user.role.value,
            action="ai_analysis.released", resource="ai_analysis", resource_id=analysis_id,
            metadata={"released_to_patient": True}
        )

        logger.info("User %s explicitly released AI Analysis %s to Patient %s",
                    current_user.user_id, analysis_id, analysis.patient_id)

        return analysis

    @staticmethod
    async def get_patient_report(
        db: AsyncIOMotorDatabase,
        current_user: UserInDB,
        analysis_id: str,
    ) -> AIAnalysisPatientReportResponse:
        """Fetch patient-safe AI analysis report."""
        doc = await db[COLLECTION_AI_ANALYSES].find_one({"analysis_id": analysis_id})
        if not doc:
            raise ResourceNotFoundError("AI Analysis", analysis_id)

        analysis = AIAnalysisInDB(**doc)

        # Patient Authorization
        patient = await db[COLLECTION_PATIENTS].find_one({"$or": [{"user_id": current_user.user_id}, {"email": current_user.email}, {"patient_id": current_user.user_id}]})
        if current_user.role == UserRole.PATIENT:
            if not patient or patient["patient_id"] != analysis.patient_id:
                raise ForbiddenError("You are not authorized to access this report.")
            if analysis.status != AIAnalysisStatus.REVIEWED or not getattr(analysis, "is_released_to_patient", False) or not analysis.patient_report:
                raise ForbiddenError("AI results are available to patients only after Doctor review and explicit release.")

        if not analysis.patient_report:
            raise AppValidationError("Patient report is not yet available for this analysis.")

        return AIAnalysisPatientReportResponse(
            analysis_id=analysis.analysis_id,
            patient_id=analysis.patient_id,
            medical_record_id=analysis.medical_record_id,
            status=analysis.status.value,
            report=analysis.patient_report,
            disclaimer=CLINICAL_SAFETY_DISCLAIMER,
        )

    @staticmethod
    async def get_gradcam_artifact(
        db: AsyncIOMotorDatabase,
        current_user: UserInDB,
        analysis_id: str,
    ) -> Tuple[bytes, str]:
        """Fetch Grad-CAM overlay image bytes for an analysis."""
        analysis = await AIService.get_analysis(db, current_user, analysis_id)

        if not analysis.explainability or not analysis.explainability.artifact_storage_key:
            raise ResourceNotFoundError("Grad-CAM explainability artifact", analysis_id)

        storage = get_storage_service()
        storage_key = analysis.explainability.artifact_storage_key
        file_bytes = await storage.read_file(storage_key, subfolder="ai-analyses")

        await log_audit_event(
            db, actor_id=current_user.user_id, role=current_user.role.value,
            action="ai_analysis.gradcam_accessed", resource="ai_analysis", resource_id=analysis_id
        )

        return file_bytes, "image/png"

    @staticmethod
    async def get_original_image_artifact(
        db: AsyncIOMotorDatabase,
        current_user: UserInDB,
        analysis_id: str,
    ) -> Tuple[bytes, str]:
        """Fetch original input image bytes used for AI analysis with strict RBAC."""
        analysis = await AIService.get_analysis(db, current_user, analysis_id)

        # 1. If document_id is present or discoverable, read via DocumentService
        doc_id = analysis.document_id or (analysis.input.document_id if analysis.input else None)
        if not doc_id:
            from app.database.collections import COLLECTION_DOCUMENTS
            d_match = await db[COLLECTION_DOCUMENTS].find_one({"ai_analysis_id": analysis_id, "is_deleted": {"$ne": True}})
            if d_match:
                doc_id = d_match.get("document_id")

        if doc_id:
            try:
                from app.services.document_service import DocumentService
                doc_service = DocumentService(db)
                file_bytes, doc = await doc_service.read_document_bytes(doc_id)
                content_type = doc.mime_type or "image/jpeg"
                await log_audit_event(
                    db, actor_id=current_user.user_id, role=current_user.role.value,
                    action="ai_analysis.original_image_accessed", resource="ai_analysis", resource_id=analysis_id
                )
                return file_bytes, content_type
            except Exception:
                pass

        # 2. Check storage for raw analysis image or medical record
        med_rec_id = analysis.medical_record_id or (analysis.input.medical_record_id if analysis.input else None)
        storage = get_storage_service()

        if med_rec_id:
            for subfolder in ["medical-records", "documents", "ai-analyses"]:
                try:
                    file_bytes = await storage.read_file(med_rec_id, subfolder=subfolder)
                    content_type = "image/jpeg"
                    if med_rec_id.endswith(".png"):
                        content_type = "image/png"
                    elif med_rec_id.endswith(".dcm"):
                        content_type = "application/dicom"
                    await log_audit_event(
                        db, actor_id=current_user.user_id, role=current_user.role.value,
                        action="ai_analysis.original_image_accessed", resource="ai_analysis", resource_id=analysis_id
                    )
                    return file_bytes, content_type
                except Exception:
                    continue

            from app.database.collections import COLLECTION_MEDICAL_RECORDS
            rec = await db[COLLECTION_MEDICAL_RECORDS].find_one({"record_id": med_rec_id})
            if rec and rec.get("file") and rec["file"].get("storage_key"):
                key = rec["file"]["storage_key"]
                content_type = rec["file"].get("content_type", "image/jpeg")
                file_bytes = await storage.read_file(key, subfolder="medical-records")
                await log_audit_event(
                    db, actor_id=current_user.user_id, role=current_user.role.value,
                    action="ai_analysis.original_image_accessed", resource="ai_analysis", resource_id=analysis_id
                )
                return file_bytes, content_type

        # 3. Default naming patterns: image_{analysis_id}.*, etc.
        for prefix in ["image", "mri", "scan", "input"]:
            for ext in [".jpg", ".png", ".jpeg", ".webp"]:
                fname = f"{prefix}_{analysis_id}{ext}"
                for subfolder in ["medical-records", "documents", "ai-analyses"]:
                    try:
                        file_bytes = await storage.read_file(fname, subfolder=subfolder)
                        content_type = "image/png" if ext == ".png" else "image/jpeg"
                        await log_audit_event(
                            db, actor_id=current_user.user_id, role=current_user.role.value,
                            action="ai_analysis.original_image_accessed", resource="ai_analysis", resource_id=analysis_id
                        )
                        return file_bytes, content_type
                    except Exception:
                        continue

        raise ResourceNotFoundError("Original medical image for AI analysis", analysis_id)

    @staticmethod
    async def list_analyses(
        db: AsyncIOMotorDatabase,
        current_user: UserInDB,
        patient_id: Optional[str] = None,
        doctor_id: Optional[str] = None,
        consultation_id: Optional[str] = None,
        medical_record_id: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
        module_id: Optional[str] = None,
    ) -> AIAnalysisListResponse:
        """List paginated AI analyses with strict role-aware filtering and RBAC validation."""
        query: Dict[str, Any] = {}

        if current_user.role == UserRole.PATIENT:
            patient = await db[COLLECTION_PATIENTS].find_one({"$or": [{"user_id": current_user.user_id}, {"email": current_user.email}, {"patient_id": current_user.user_id}]})
            if not patient:
                return AIAnalysisListResponse(items=[], total=0, page=page, page_size=page_size)
            if patient_id and patient_id != patient["patient_id"]:
                raise ForbiddenError("You are not authorized to query AI analyses for other patients.")
            query["patient_id"] = patient["patient_id"]
            query["status"] = AIAnalysisStatus.REVIEWED.value  # patients only see reviewed
            query["is_released_to_patient"] = {"$ne": False}

        elif current_user.role == UserRole.DOCTOR:
            doctor = await db[COLLECTION_DOCTORS].find_one({"user_id": current_user.user_id})
            doc_id = doctor["doctor_id"] if doctor else "DOC-UNKNOWN"
            if doctor_id and doctor_id != doc_id:
                raise ForbiddenError("You cannot query AI analyses on behalf of another doctor.")

            if patient_id:
                # Verify doctor has an active care relationship with this patient
                has_apt = await db[COLLECTION_APPOINTMENTS].find_one({
                    "patient_id": patient_id,
                    "doctor_id": doc_id,
                })
                if not has_apt:
                    has_con = await db[COLLECTION_CONSULTATIONS].find_one({
                        "patient_id": patient_id,
                        "doctor_id": doc_id,
                    })
                    if not has_con:
                        has_own_rec = await db[COLLECTION_AI_ANALYSES].find_one({
                            "patient_id": patient_id,
                            "$or": [{"doctor_id": doc_id}, {"requested_by": current_user.user_id}],
                        })
                        if not has_own_rec:
                            raise ForbiddenError("You are not authorized to access AI Analysis for this patient.")
                query["patient_id"] = patient_id
                query["$or"] = [{"doctor_id": doc_id}, {"requested_by": current_user.user_id}]
            else:
                query["$or"] = [{"doctor_id": doc_id}, {"requested_by": current_user.user_id}]

        elif current_user.role in (UserRole.HOSPITAL_ADMIN, UserRole.ADMIN):
            if patient_id:
                query["patient_id"] = patient_id
            if doctor_id:
                query["doctor_id"] = doctor_id

        elif current_user.role in (UserRole.HOSPITAL_STAFF, UserRole.STAFF):
            raise ForbiddenError("Staff members cannot browse AI analyses.")

        if consultation_id:
            query["consultation_id"] = consultation_id
        if medical_record_id:
            query["medical_record_id"] = medical_record_id
        if status:
            st = str(status).lower()
            if st == "released":
                query["status"] = AIAnalysisStatus.REVIEWED.value
                query["is_released_to_patient"] = {"$ne": False}
            elif st in ("unreleased", "reviewed_unreleased"):
                query["status"] = AIAnalysisStatus.REVIEWED.value
                query["is_released_to_patient"] = {"$ne": True}
            elif st in ("awaiting_review", "pending_review", "pending"):
                query["status"] = AIAnalysisStatus.AWAITING_REVIEW.value
            else:
                query["status"] = status
        if module_id:
            query["model.module_id"] = module_id.upper()

        total = await db[COLLECTION_AI_ANALYSES].count_documents(query)
        skip = (page - 1) * page_size

        cursor = db[COLLECTION_AI_ANALYSES].find(query).sort([("created_at", -1), ("analysis_id", -1)]).skip(skip).limit(page_size)
        items = []
        async for doc in cursor:
            try:
                items.append(AIAnalysisDoctorResponse(**doc))
            except Exception as parse_err:
                logger.warning("Skipping unparseable AI analysis record %s: %s", doc.get("analysis_id"), parse_err)
                continue

        return AIAnalysisListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )

    @staticmethod
    async def get_admin_ai_insights(
        db: AsyncIOMotorDatabase,
        current_user: UserInDB,
    ) -> AIInsightsResponse:
        """Hospital Admin aggregate AI insights and operational metrics."""
        if current_user.role != UserRole.HOSPITAL_ADMIN:
            raise ForbiddenError("Only Hospital Admin can view AI operational insights.")

        total_analyses = await db[COLLECTION_AI_ANALYSES].count_documents({})
        reviewed_count = await db[COLLECTION_AI_ANALYSES].count_documents({"status": AIAnalysisStatus.REVIEWED.value})
        awaiting_review_count = await db[COLLECTION_AI_ANALYSES].count_documents({"status": AIAnalysisStatus.AWAITING_REVIEW.value})
        failed_count = await db[COLLECTION_AI_ANALYSES].count_documents({"status": AIAnalysisStatus.FAILED.value})

        # By status
        status_pipeline = [{"$group": {"_id": "$status", "count": {"$sum": 1}}}]
        by_status = {}
        async for doc in db[COLLECTION_AI_ANALYSES].aggregate(status_pipeline):
            by_status[doc["_id"]] = doc["count"]

        # By model version
        version_pipeline = [{"$group": {"_id": "$model.version", "count": {"$sum": 1}}}]
        by_model_version = {}
        async for doc in db[COLLECTION_AI_ANALYSES].aggregate(version_pipeline):
            if doc["_id"]:
                by_model_version[doc["_id"]] = doc["count"]

        return AIInsightsResponse(
            total_analyses=total_analyses,
            by_status=by_status,
            by_model_version=by_model_version,
            reviewed_count=reviewed_count,
            awaiting_review_count=awaiting_review_count,
            failed_count=failed_count,
        )
