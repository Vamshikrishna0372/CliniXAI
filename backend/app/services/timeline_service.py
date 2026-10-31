"""Clinical Timeline backend service aggregating chronological patient history."""

from datetime import datetime, timezone
from typing import List
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database.collections import (
    COLLECTION_APPOINTMENTS, COLLECTION_CONSULTATIONS, COLLECTION_PRESCRIPTIONS,
    COLLECTION_AI_ANALYSES, COLLECTION_BILLING, COLLECTION_PAYMENTS,
    COLLECTION_FOLLOW_UPS, COLLECTION_DOCUMENTS, COLLECTION_PATIENTS
)
from app.schemas.timeline import TimelineEvent, TimelineResponse
from app.utils.datetime import utc_now


def _normalize_dt(val) -> datetime:
    if val is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    if isinstance(val, str):
        try:
            val = datetime.fromisoformat(val)
        except Exception:
            return datetime.min.replace(tzinfo=timezone.utc)
    if isinstance(val, datetime):
        if val.tzinfo is None:
            return val.replace(tzinfo=timezone.utc)
        return val.astimezone(timezone.utc)
    return datetime.min.replace(tzinfo=timezone.utc)


class TimelineService:
    """Service aggregating all patient interactions into a unified clinical timeline."""

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db

    async def get_patient_timeline(self, patient_id: str) -> TimelineResponse:
        """Aggregates all patient records chronologically across core collections."""
        # Resolve canonical patient_id and associated IDs
        pat_rec = await self.db[COLLECTION_PATIENTS].find_one({"$or": [{"patient_id": patient_id}, {"user_id": patient_id}]})
        query_ids = [patient_id]
        canonical_pat_id = patient_id
        if pat_rec:
            canonical_pat_id = pat_rec.get("patient_id", patient_id)
            query_ids.append(canonical_pat_id)
            if pat_rec.get("user_id"):
                query_ids.append(pat_rec["user_id"])
        clean_ids = list(set(query_ids))
        pid_filter = clean_ids[0] if len(clean_ids) == 1 else {"$in": clean_ids}

        events: List[TimelineEvent] = []

        # 1. Appointments
        apt_cursor = self.db[COLLECTION_APPOINTMENTS].find({"patient_id": pid_filter, "is_deleted": {"$ne": True}})
        async for doc in apt_cursor:
            events.append(
                TimelineEvent(
                    event_id=doc["appointment_id"],
                    event_type="appointment",
                    timestamp=doc.get("created_at") or utc_now(),
                    title=f"Appointment {doc.get('status', '').title()}",
                    description=f"Scheduled for {doc.get('appointment_date')} at {doc.get('start_time')}. Reason: {doc.get('reason', 'N/A')}",
                    doctor_id=doc.get("doctor_id"),
                    status=doc.get("status"),
                    metadata={"department_id": doc.get("department_id")},
                )
            )
            # Check-in sub-event
            check_in = doc.get("check_in", {})
            if isinstance(check_in, dict) and check_in.get("checked_in_at"):
                events.append(
                    TimelineEvent(
                        event_id=f"chk_{doc['appointment_id']}",
                        event_type="check_in",
                        timestamp=check_in["checked_in_at"],
                        title="Patient Checked-In",
                        description=f"Check-in method: {check_in.get('method', 'manual')}",
                        status="checked_in",
                    )
                )

        # 2. Consultations
        c_cursor = self.db[COLLECTION_CONSULTATIONS].find({"patient_id": pid_filter, "is_deleted": {"$ne": True}})
        async for doc in c_cursor:
            cc = doc.get("chief_complaint", {})
            complaint_text = cc.get("complaint") if isinstance(cc, dict) else "Consultation"
            events.append(
                TimelineEvent(
                    event_id=doc["consultation_id"],
                    event_type="consultation",
                    timestamp=doc.get("created_at") or utc_now(),
                    title="Clinical Consultation",
                    description=f"Chief Complaint: {complaint_text}",
                    doctor_id=doc.get("doctor_id"),
                    status=doc.get("status"),
                    metadata={"appointment_id": doc.get("appointment_id")},
                )
            )

        # 3. Prescriptions
        rx_cursor = self.db[COLLECTION_PRESCRIPTIONS].find({"patient_id": pid_filter, "is_deleted": {"$ne": True}})
        async for doc in rx_cursor:
            meds_count = len(doc.get("medications", []))
            events.append(
                TimelineEvent(
                    event_id=doc["prescription_id"],
                    event_type="prescription",
                    timestamp=doc.get("issued_at") or doc.get("created_at") or utc_now(),
                    title="Prescription Issued",
                    description=f"Prescription with {meds_count} medication(s).",
                    doctor_id=doc.get("doctor_id"),
                    status=doc.get("status"),
                )
            )

        # 4. AI Analyses & Doctor Reviews
        ai_cursor = self.db[COLLECTION_AI_ANALYSES].find({"patient_id": pid_filter, "is_deleted": {"$ne": True}})
        async for doc in ai_cursor:
            model_name = doc.get("model", {}).get("name", "AI Module") if isinstance(doc.get("model"), dict) else "AI Module"
            pred = doc.get("prediction", {})
            pred_class = pred.get("predicted_class", "N/A") if isinstance(pred, dict) else "N/A"

            events.append(
                TimelineEvent(
                    event_id=doc["analysis_id"],
                    event_type="ai_analysis",
                    timestamp=doc.get("created_at") or utc_now(),
                    title=f"AI Analysis: {model_name}",
                    description=f"Predicted Class: {pred_class}",
                    doctor_id=doc.get("doctor_id"),
                    status=doc.get("status"),
                )
            )

            doc_review = doc.get("doctor_review")
            if isinstance(doc_review, dict) and doc_review.get("reviewed_at"):
                events.append(
                    TimelineEvent(
                        event_id=f"rev_{doc['analysis_id']}",
                        event_type="ai_review",
                        timestamp=doc_review["reviewed_at"],
                        title="Doctor AI Review Completed",
                        description=f"Decision: {doc_review.get('decision')}. Interpretation: {doc_review.get('clinical_interpretation')}",
                        doctor_id=doc_review.get("reviewed_by"),
                        status="reviewed",
                    )
                )

        # 5. Billing & Payments
        b_cursor = self.db[COLLECTION_BILLING].find({"patient_id": pid_filter, "is_deleted": {"$ne": True}})
        async for doc in b_cursor:
            events.append(
                TimelineEvent(
                    event_id=doc["bill_id"],
                    event_type="billing",
                    timestamp=doc.get("created_at") or utc_now(),
                    title="Medical Invoice Issued",
                    description=f"Grand Total: ₹{doc.get('grand_total', 0.0)}. Balance Due: ₹{doc.get('balance_due', 0.0)}",
                    status=doc.get("status"),
                )
            )

        # 6. Follow-ups
        fu_cursor = self.db[COLLECTION_FOLLOW_UPS].find({"patient_id": pid_filter, "is_deleted": {"$ne": True}})
        async for doc in fu_cursor:
            events.append(
                TimelineEvent(
                    event_id=doc["follow_up_id"],
                    event_type="follow_up",
                    timestamp=doc.get("scheduled_date") or doc.get("created_at") or utc_now(),
                    title="Follow-up Appointment",
                    description=f"Reason: {doc.get('reason')}",
                    doctor_id=doc.get("doctor_id"),
                    status=doc.get("status"),
                )
            )

        # 7. Medical Documents
        doc_cursor = self.db[COLLECTION_DOCUMENTS].find({"patient_id": pid_filter, "is_deleted": {"$ne": True}})
        async for doc in doc_cursor:
            events.append(
                TimelineEvent(
                    event_id=doc["document_id"],
                    event_type="document",
                    timestamp=doc.get("created_at") or utc_now(),
                    title=f"Document Uploaded: {doc.get('title')}",
                    description=f"Category: {doc.get('category')}. File: {doc.get('original_file_name')}",
                    actor_id=doc.get("uploaded_by"),
                    status="active",
                )
            )

        # Sort all timeline events chronologically (most recent first)
        events.sort(key=lambda e: _normalize_dt(e.timestamp), reverse=True)

        return TimelineResponse(
            patient_id=canonical_pat_id,
            total_events=len(events),
            events=events,
        )
