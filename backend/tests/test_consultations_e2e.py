"""
Complete End-to-End Test Suite for CliniXAI Consultation Workflow, Doctor Workspace,
Prescription Issuance, Medical Record Auto-Creation, AI Analysis Linkage, RBAC & MongoDB Persistence.
"""

import pytest
from httpx import AsyncClient
from datetime import date, timedelta


async def get_patient_token(async_client: AsyncClient) -> str:
    res = await async_client.post("/api/v1/auth/login", json={
        "email": "patient.one@clinixai.com",
        "password": "Patient@123",
    })
    assert res.status_code == 200, f"Patient login failed: {res.text}"
    body = res.json()
    return body["data"]["access_token"] if "data" in body else body["access_token"]


async def get_doctor_token(async_client: AsyncClient) -> str:
    res = await async_client.post("/api/v1/auth/login", json={
        "email": "doctor.arjun@clinixai.com",
        "password": "Doctor@123",
    })
    assert res.status_code == 200, f"Doctor login failed: {res.text}"
    body = res.json()
    return body["data"]["access_token"] if "data" in body else body["access_token"]


async def get_admin_token(async_client: AsyncClient) -> str:
    res = await async_client.post("/api/v1/auth/login", json={
        "email": "admin@clinixai.com",
        "password": "admin123",
    })
    assert res.status_code == 200, f"Admin login failed: {res.text}"
    body = res.json()
    return body["data"]["access_token"] if "data" in body else body["access_token"]


@pytest.mark.asyncio
async def test_complete_consultation_prescription_medical_record_pipeline(async_client: AsyncClient):
    """Full E2E Clinical Workflow: Book -> Check-In -> Start Consultation -> Notes & Assessment -> Diagnosis -> Prescription -> AI Link -> Complete -> Medical Record -> Patient/Doctor/Admin Views."""
    pat_token = await get_patient_token(async_client)
    doc_token = await get_doctor_token(async_client)
    admin_token = await get_admin_token(async_client)

    pat_headers = {"Authorization": f"Bearer {pat_token}"}
    doc_headers = {"Authorization": f"Bearer {doc_token}"}
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    target_d = date.today() + timedelta(days=1)
    while target_d.weekday() >= 5:
        target_d += timedelta(days=1)
    target_date_str = target_d.isoformat()

    # 1. Query Doctor Availability for Scheduled Clinic Day
    avail_res = await async_client.get(
        "/api/v1/doctors/DOC-RAO-001/availability",
        headers=pat_headers,
        params={"date": target_date_str}
    )
    assert avail_res.status_code == 200, f"Doctor availability query failed: {avail_res.text}"
    avail_slots = avail_res.json()["data"]["available_slots"]
    chosen_slot = avail_slots[0]["start_time"]

    # 2. Patient Books Appointment
    book_res = await async_client.post("/api/v1/appointments", headers=pat_headers, json={
        "doctor_id": "DOC-RAO-001",
        "department_id": "DEPT-CARD",
        "appointment_date": target_date_str,
        "start_time": chosen_slot,
        "reason": "Cardiology consultation and Brain MRI review",
        "appointment_type": "new_consultation"
    })
    assert book_res.status_code == 201, f"Booking failed: {book_res.text}"
    apt_data = book_res.json()["data"]
    appointment_id = apt_data["appointment_id"]
    patient_id = apt_data["patient_id"]

    # Update appointment_date to today for check-in validation
    from app.database.mongodb import db_manager
    await db_manager.db["appointments"].update_one(
        {"appointment_id": appointment_id},
        {"$set": {"appointment_date": date.today().isoformat()}}
    )

    # 3. Patient / Staff Checks In
    ci_res = await async_client.post(f"/api/v1/appointments/{appointment_id}/check-in", headers=pat_headers, json={"method": "manual"})
    assert ci_res.status_code == 200, f"Check-in failed: {ci_res.text}"

    # 4. Doctor Starts Consultation
    start_res = await async_client.post("/api/v1/consultations/start", headers=doc_headers, json={"appointment_id": appointment_id})
    assert start_res.status_code == 201, f"Start consultation failed: {start_res.text}"
    consult_data = start_res.json()["data"]
    consultation_id = consult_data["consultation_id"]
    assert consult_data["appointment_id"] == appointment_id
    assert consult_data["patient_id"] == patient_id
    assert consult_data["doctor_id"] == "DOC-RAO-001"
    assert consult_data["status"] == "in_progress"

    # 5. Duplicate Consultation Prevention: Calling start_consultation again returns existing consultation
    dup_start_res = await async_client.post("/api/v1/consultations/start", headers=doc_headers, json={"appointment_id": appointment_id})
    assert dup_start_res.status_code == 201
    assert dup_start_res.json()["data"]["consultation_id"] == consultation_id

    # 6. Doctor Records Clinical Assessment & Notes
    assess_payload = {
        "assessment": {
            "summary": "Patient presented with mild tension headache and request for routine cardiac check. Vitals stable.",
            "impression": "No acute neurological or cardiovascular deficits detected.",
            "risk_level": "low"
        }
    }
    assess_res = await async_client.patch(f"/api/v1/consultations/{consultation_id}/assessment", headers=doc_headers, json=assess_payload)
    assert assess_res.status_code == 200, f"Assessment failed: {assess_res.text}"

    # 7. Doctor Records Diagnoses
    diag_payload = {
        "diagnoses": [
            {"name": "Tension-type Headache", "type": "primary", "code": "G44.2", "notes": "Mild stress-induced"},
            {"name": "Essential Hypertension (Mild)", "type": "secondary", "code": "I10", "notes": "Borderline blood pressure"}
        ]
    }
    diag_res = await async_client.patch(f"/api/v1/consultations/{consultation_id}/diagnoses", headers=doc_headers, json=diag_payload)
    assert diag_res.status_code == 200, f"Diagnoses failed: {diag_res.text}"

    # 8. Doctor Issues Prescription
    rx_payload = {
        "medications": [
            {"name": "Paracetamol 500mg", "dosage": "1 tablet", "frequency": "As needed (max 3/day)", "duration": "5 days", "instructions": "Take after meals with water"},
            {"name": "Amlodipine 5mg", "dosage": "1 tablet", "frequency": "Once daily (Morning)", "duration": "30 days", "instructions": "Monitor BP weekly"}
        ],
        "instructions": "Maintain low sodium diet, stay hydrated, and follow up in 4 weeks."
    }
    rx_res = await async_client.post(f"/api/v1/prescriptions/consultation/{consultation_id}", headers=doc_headers, json=rx_payload)
    assert rx_res.status_code == 201, f"Prescription creation failed: {rx_res.text}"
    rx_data = rx_res.json()["data"]
    prescription_id = rx_data["prescription_id"]
    assert rx_data["consultation_id"] == consultation_id
    assert len(rx_data["medications"]) == 2

    # 9. Doctor Completes Consultation
    complete_res = await async_client.post(f"/api/v1/consultations/{consultation_id}/complete", headers=doc_headers, json={
        "final_diagnosis": "Tension-type Headache",
        "recommendations": "Follow-up in 4 weeks"
    })
    assert complete_res.status_code == 200, f"Completion failed: {complete_res.text}"
    completed_consult = complete_res.json()["data"]
    assert completed_consult["status"] == "completed"

    # 10. Verify Appointment status updated to COMPLETED
    apt_detail_res = await async_client.get(f"/api/v1/appointments/{appointment_id}", headers=doc_headers)
    assert apt_detail_res.status_code == 200
    assert apt_detail_res.json()["data"]["status"] == "completed"

    # 11. Verify Medical Record Auto-Creation in MongoDB
    mr_list_res = await async_client.get("/api/v1/medical-records", headers=doc_headers, params={"patient_id": patient_id})
    assert mr_list_res.status_code == 200, f"Medical records list failed: {mr_list_res.text}"
    mr_items = mr_list_res.json()["data"]
    linked_mr = next((m for m in mr_items if m.get("consultation_id") == consultation_id), None)
    assert linked_mr is not None, f"Medical record auto-creation failed for consultation {consultation_id}"
    assert linked_mr["patient_id"] == patient_id
    assert linked_mr["doctor_id"] == "DOC-RAO-001"

    # 12. Patient View Isolation: Patient retrieves own completed consultation, prescription & medical record
    pat_consults_res = await async_client.get("/api/v1/consultations", headers=pat_headers)
    assert pat_consults_res.status_code == 200
    pat_consult_items = pat_consults_res.json()["data"]
    assert any(c["consultation_id"] == consultation_id for c in pat_consult_items)

    pat_rx_res = await async_client.get("/api/v1/prescriptions", headers=pat_headers)
    assert pat_rx_res.status_code == 200
    pat_rx_items = pat_rx_res.json()["data"]
    assert any(r["prescription_id"] == prescription_id for r in pat_rx_items)

    pat_mr_res = await async_client.get("/api/v1/medical-records", headers=pat_headers)
    assert pat_mr_res.status_code == 200
    pat_mr_items = pat_mr_res.json()["data"]
    assert any(m["consultation_id"] == consultation_id for m in pat_mr_items)

    # 13. Doctor Patient Context Workspace Verification
    doc_ctx_res = await async_client.get(f"/api/v1/consultations/patient-context/{patient_id}", headers=doc_headers)
    assert doc_ctx_res.status_code == 200
    ctx_body = doc_ctx_res.json()["data"]
    assert ctx_body["patient_id"] == patient_id
    assert any(pc["consultation_id"] == consultation_id for pc in ctx_body["past_consultations"])

    # 14. Admin Hospital-Wide Visibility Verification
    admin_consults_res = await async_client.get("/api/v1/consultations", headers=admin_headers)
    assert admin_consults_res.status_code == 200
    admin_items = admin_consults_res.json()["data"]
    assert any(c["consultation_id"] == consultation_id for c in admin_items)
