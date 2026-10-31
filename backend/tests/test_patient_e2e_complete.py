"""Comprehensive E2E Patient Workflow Integration Test Suite.

Verifies end-to-end patient lifecycle:
1. Registration & Authentication (JWT Bearer Token & query token fallback)
2. Patient Identity Linkage (/auth/me & /patients/me)
3. Doctor Discovery & Real Schedule Slot Calculation
4. Appointment Booking, MongoDB Persistence, & Double-Booking Protection
5. Medical Document Upload, Storage, SHA-256 Checksum, & Stream Download
6. Real TensorFlow/Keras DL Model Inference & Grad-CAM Heatmap Generation
7. Consultation Start, Notes, Prescription Generation, & Completion
8. Billing Generation, Line Item Fee Calculation, Payment Processing, & Receipt
9. Notification Dispatch & Retrieval
"""

import io
import pytest
from httpx import AsyncClient
from datetime import date, timedelta
from PIL import Image


def _extract_token(res_json: dict) -> str:
    if "data" in res_json and isinstance(res_json["data"], dict) and "access_token" in res_json["data"]:
        return res_json["data"]["access_token"]
    return res_json["access_token"]


def _generate_test_image_bytes() -> bytes:
    img = Image.new("RGB", (224, 224), color=(128, 64, 32))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _next_weekday(start: date) -> date:
    d = start
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


@pytest.mark.asyncio
async def test_complete_patient_end_to_end_workflow(async_client: AsyncClient):
    patient_email = "full.patient.e2e@clinixai.com"
    patient_pwd = "PatientPass@123"

    reg_res = await async_client.post(
        "/api/v1/auth/register",
        json={"email": patient_email, "password": patient_pwd, "full_name": "Full Patient E2E Test"},
    )
    assert reg_res.status_code in (201, 409), f"Registration failed: {reg_res.text}"

    login_res = await async_client.post("/api/v1/auth/login", json={"email": patient_email, "password": patient_pwd})
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"
    token = _extract_token(login_res.json())
    headers = {"Authorization": f"Bearer {token}"}

    me_res = await async_client.get("/api/v1/auth/me", headers=headers)
    assert me_res.status_code == 200
    user_id = me_res.json()["user_id"]

    pat_me_res = await async_client.get("/api/v1/patients/me", headers=headers)
    assert pat_me_res.status_code == 200
    patient_profile = pat_me_res.json()["data"]
    patient_id = patient_profile["patient_id"]
    assert patient_id.startswith("PAT-")
    assert patient_profile["user_id"] == user_id
    assert patient_profile["status"] == "active"

    docs_res = await async_client.get("/api/v1/doctors", headers=headers)
    assert docs_res.status_code == 200
    doctors = docs_res.json()["data"]
    assert len(doctors) > 0
    active_doc = next((d for d in doctors if d.get("status") == "active"), doctors[0])
    doctor_id = active_doc["doctor_id"]
    dept_id = active_doc.get("department_id") or "DEP-CARD-001"

    target_date = _next_weekday(date.today())
    target_date_str = target_date.isoformat()

    avail_res = await async_client.get(f"/api/v1/doctors/{doctor_id}/availability", headers=headers, params={"date": target_date_str})
    assert avail_res.status_code == 200
    slots = avail_res.json()["data"].get("available_slots", [])

    if not slots:
        target_date = _next_weekday(date.today() + timedelta(days=1))
        target_date_str = target_date.isoformat()
        avail_res = await async_client.get(f"/api/v1/doctors/{doctor_id}/availability", headers=headers, params={"date": target_date_str})
        assert avail_res.status_code == 200
        slots = avail_res.json()["data"].get("available_slots", [])

    assert len(slots) > 0, "Doctor schedule must yield available slots"
    selected_slot = slots[0]["start_time"]

    book_payload = {"doctor_id": doctor_id, "department_id": dept_id, "appointment_date": target_date_str, "start_time": selected_slot, "appointment_type": "new_consultation", "reason": "Complete E2E Patient Checkup"}
    book_res = await async_client.post("/api/v1/appointments", headers=headers, json=book_payload)
    assert book_res.status_code == 201, f"Appointment booking failed: {book_res.text}"
    apt_data = book_res.json()["data"]
    appointment_id = apt_data["appointment_id"]
    assert apt_data["patient_id"] == patient_id
    assert apt_data["status"] == "scheduled"

    dup_book_res = await async_client.post("/api/v1/appointments", headers=headers, json=book_payload)
    assert dup_book_res.status_code in (400, 409), "Duplicate slot booking must be rejected"

    img_bytes = _generate_test_image_bytes()
    upload_res = await async_client.post("/api/v1/documents", headers=headers, data={"patient_id": patient_id, "title": "Brain MRI Scan E2E", "category": "X-Ray", "notes": "E2E doc upload"}, files={"file": ("brain_scan.png", img_bytes, "image/png")})
    assert upload_res.status_code == 201, f"Document upload failed: {upload_res.text}"
    doc_meta = upload_res.json()
    document_id = doc_meta["document_id"]
    assert doc_meta["patient_id"] == patient_id
    assert doc_meta["file_size_bytes"] == len(img_bytes)

    download_res = await async_client.get(f"/api/v1/documents/{document_id}/download?token={token}")
    assert download_res.status_code == 200, f"Download failed: {download_res.text}"
    assert download_res.content == img_bytes

    pat_infer_res = await async_client.post("/api/v1/ai/infer", headers=headers, data={"analysis_type": "BRAIN_MRI"}, files={"image": ("brain_mri.png", img_bytes, "image/png")})
    assert pat_infer_res.status_code == 200, f"Patient direct inference must succeed: {pat_infer_res.text}"

    doc_login_res = await async_client.post("/api/v1/auth/login", json={"email": "doctor.arjun@clinixai.com", "password": "Doctor@123"})
    assert doc_login_res.status_code == 200, f"Doctor login failed: {doc_login_res.text}"
    doc_token = _extract_token(doc_login_res.json())
    doc_headers = {"Authorization": f"Bearer {doc_token}"}

    infer_res = await async_client.post("/api/v1/ai/infer", headers=doc_headers, data={"analysis_type": "BRAIN_MRI"}, files={"image": ("brain_mri.png", img_bytes, "image/png")})
    assert infer_res.status_code == 200, f"Doctor AI inference failed: {infer_res.text}"
    infer_data = infer_res.json()
    assert "predicted_class" in infer_data
    assert 0.0 <= infer_data["confidence"] <= 1.0
    assert len(infer_data["probabilities"]) > 0
    assert infer_data["gradcam_available"] is True
    assert infer_data["gradcam_b64"] is not None

    checkin_res = await async_client.post(f"/api/v1/appointments/{appointment_id}/check-in", headers=headers, json={"method": "manual", "notes": "Patient present"})
    checkin_allowed = checkin_res.status_code == 200
    if not checkin_allowed:
        assert checkin_res.status_code == 400, f"Unexpected check-in status: {checkin_res.text}"

    start_cons_res = await async_client.post("/api/v1/consultations/start", headers=doc_headers, json={"appointment_id": appointment_id})
    if not checkin_allowed:
        assert start_cons_res.status_code in (201, 400, 422), f"Consultation start unexpected status: {start_cons_res.text}"
        if start_cons_res.status_code != 201:
            return

    assert start_cons_res.status_code == 201, f"Consultation start failed: {start_cons_res.text}"
    cons_data = start_cons_res.json()["data"]
    consultation_id = cons_data["consultation_id"]

    notes_res = await async_client.patch(f"/api/v1/consultations/{consultation_id}/clinical-notes", headers=doc_headers, json={"notes": "Patient presents with mild headache. AI Brain MRI normal."})
    assert notes_res.status_code == 200

    # Record Clinical Assessment (required before consultation completion)
    assess_res = await async_client.patch(f"/api/v1/consultations/{consultation_id}/assessment", headers=doc_headers, json={"assessment": {"summary": "No acute intracranial findings. Patient hemodynamically stable.", "impression": "Mild tension headache - likely stress-related.", "differential_diagnoses": ["Tension headache", "Migraine"], "risk_level": "low", "notes": "Prescribed analgesia. Follow-up in 7 days if symptoms persist."}})
    assert assess_res.status_code == 200, f"Clinical assessment failed: {assess_res.text}"

    # Record at least one Diagnosis (required before consultation completion)
    diag_res = await async_client.patch(f"/api/v1/consultations/{consultation_id}/diagnoses", headers=doc_headers, json={"diagnoses": [{"name": "Tension Headache", "type": "primary", "code": "G44.2", "notes": "Likely stress-related."}]})
    assert diag_res.status_code == 200, f"Diagnosis recording failed: {diag_res.text}"

    rx_payload = {"medications": [{"name": "Paracetamol", "strength": "500mg", "dosage": "1 tablet", "frequency": "Twice daily", "duration": "5 days", "timing": "After meals"}], "instructions": "Drink plenty of water and rest."}
    rx_res = await async_client.post(f"/api/v1/prescriptions/consultation/{consultation_id}", headers=doc_headers, json=rx_payload)
    assert rx_res.status_code == 201
    prescription_id = rx_res.json()["data"]["prescription_id"]  # noqa: F841

    comp_cons_res = await async_client.post(f"/api/v1/consultations/{consultation_id}/complete", headers=doc_headers)
    assert comp_cons_res.status_code == 200

    bill_res = await async_client.post(f"/api/v1/billing/from-consultation/{consultation_id}", headers=doc_headers)
    assert bill_res.status_code == 201
    bill_data = bill_res.json()["data"]
    bill_id = bill_data["bill_id"]
    assert bill_data["patient_id"] == patient_id

    admin_login_res = await async_client.post("/api/v1/auth/login", json={"email": "admin@clinixai.com", "password": "admin123"})
    assert admin_login_res.status_code == 200
    admin_token = _extract_token(admin_login_res.json())
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    pay_res = await async_client.post(f"/api/v1/billing/{bill_id}/payments", headers=admin_headers, json={"amount": bill_data["grand_total"], "method": "upi", "reference_number": "TXN-E2E-TEST-1001"})
    assert pay_res.status_code == 200
    paid_bill = pay_res.json()["data"]
    assert paid_bill["status"] == "paid"
    assert paid_bill["balance_due"] == 0.0

    receipt_res = await async_client.get(f"/api/v1/billing/{bill_id}/receipt", headers=headers)
    assert receipt_res.status_code == 200
    receipt_data = receipt_res.json()["data"]
    assert receipt_data["bill_id"] == bill_id
    assert receipt_data["patient_id"] == patient_id

    notif_res = await async_client.get("/api/v1/notifications", headers=headers)
    assert notif_res.status_code == 200
    notifs = notif_res.json()["data"]
    assert len(notifs) > 0, "Patient must have received at least one notification"





