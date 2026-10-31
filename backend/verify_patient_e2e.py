import urllib.request
import urllib.parse
import json

BASE = "http://127.0.0.1:8000/api/v1"

def run_test():
    print("=== STARTING PATIENT FULL WORKFLOW E2E VALIDATION ===")
    
    # 1. Login patient
    login_payload = json.dumps({"email": "patient.one@clinixai.com", "password": "Patient@123"}).encode("utf-8")
    req = urllib.request.Request(f"{BASE}/auth/login", data=login_payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        # Auth returns TokenResponse directly: {access_token, refresh_token, token_type, expires_in, user}
        token = res["access_token"]
        refresh_token = res["refresh_token"]
        user = res["user"]
        print("[PASS] 1. Patient Login:", user["email"], "| Role:", user["role"], "| Patient ID:", user.get("patient_id"))
        assert user["role"] == "patient", "Role mismatch"
        assert user.get("patient_id") is not None, "patient_id missing from login response"

    # 2. Get /auth/me
    req = urllib.request.Request(f"{BASE}/auth/me", headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        me = res
        print("[PASS] 2. /auth/me Identity:", me["user_id"], "| Attached Patient ID:", me.get("patient_id"))
        assert me.get("patient_id") == user["patient_id"], "patient_id mismatch in /auth/me"

    # 3. Get /patients/me
    req = urllib.request.Request(f"{BASE}/patients/me", headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        p_me = res["data"]
        patient_id = p_me["patient_id"]
        print("[PASS] 3. /patients/me Profile:", p_me.get("full_name", f"{p_me.get('first_name')} {p_me.get('last_name')}"), "| Patient ID:", patient_id)

    # 4. Update Profile (Patient Self-Update)
    update_payload = json.dumps({
        "phone": "+91 99999 88888",
        "address": {"street": "77 Health Park Lane, Tech City"},
        "allergies": ["Penicillin", "Peanuts", "Sulfa"]
    }).encode("utf-8")
    req = urllib.request.Request(f"{BASE}/patients/me", data=update_payload, headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"}, method="PATCH")
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        updated_p = res["data"]
        print("[PASS] 4. Update Patient Profile:", updated_p.get("phone"), "| Allergies:", updated_p.get("allergies"))
        assert "Peanuts" in updated_p.get("allergies", []), "Allergy update failed"

    # 5. List Doctors
    req = urllib.request.Request(f"{BASE}/doctors", headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        items = res["data"]["items"] if "items" in res["data"] else res["data"]
        first_doc = items[0]
        doctor_id = first_doc["doctor_id"]
        print("[PASS] 5. Doctor Discovery:", first_doc.get("full_name", first_doc.get("name")), "| ID:", doctor_id)

    # 6. Check Doctor Availability
    req = urllib.request.Request(f"{BASE}/doctors/{doctor_id}/availability?date=2026-09-22", headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        avail_data = res["data"]
        slots = avail_data.get("available_slots", [])
        available_slot = slots[0]["start_time"] if slots else "10:00 AM"
        print("[PASS] 6. Doctor Availability: Total slots:", len(slots), "| Selected Slot:", available_slot)

    # 7. Book Appointment
    slot_to_book = available_slot or "10:00"
    book_payload = json.dumps({
        "doctor_id": doctor_id,
        "department_id": "DEPT-CARD",
        "appointment_date": "2026-09-22",
        "start_time": slot_to_book,
        "appointment_type": "new_consultation",
        "reason": "Persistent headache and neurological evaluation",
    }).encode("utf-8")
    req = urllib.request.Request(f"{BASE}/appointments", data=book_payload, headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        appt = res["data"]
        appointment_id = appt["appointment_id"]
        print("[PASS] 7. Book Appointment Created:", appointment_id, "| Status:", appt.get("status"), "| Time:", appt.get("appointment_time"))

    # 8. List Patient Appointments & Verify Booking Appears
    req = urllib.request.Request(f"{BASE}/appointments?patient_id={patient_id}", headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        appts = res["data"] if isinstance(res.get("data"), list) else res.get("data", {}).get("items", [])
        found_appt = any(a["appointment_id"] == appointment_id for a in appts)
        print("[PASS] 8. Verify Booked Appointment in Patient List: Found?", found_appt, "| Total Appts:", len(appts))
        assert found_appt, "Booked appointment was not found in patient appointments list"

    # 9. Upload Medical Document
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="brain_scan_mri.jpg"\r\n'
        f"Content-Type: image/jpeg\r\n\r\n"
        f"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00" + ("\x00" * 200) + "\xff\xd9"
        f"\r\n--{boundary}\r\n"
        f'Content-Disposition: form-data; name="title"\r\n\r\nBrain MRI Scan T1\r\n'
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="category"\r\n\r\nMRI\r\n'
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="patient_id"\r\n\r\n{patient_id}\r\n'
        f"--{boundary}--\r\n"
    ).encode("latin-1")
    req = urllib.request.Request(f"{BASE}/documents", data=body, headers={
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Authorization": f"Bearer {token}"
    })
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        doc = res.get("data", res)
        document_id = doc["document_id"]
        print("[PASS] 9. Medical Document Uploaded:", document_id, "| Title:", doc.get("title"), "| File URL:", doc.get("file_url"))

    # 10. Verify Document Appears in Documents List
    req = urllib.request.Request(f"{BASE}/documents?patient_id={patient_id}", headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        docs = res.get("items", res.get("data", {}).get("items", []))
        found_doc = any(d["document_id"] == document_id for d in docs)
        print("[PASS] 10. Document in Patient Records List: Found?", found_doc, "| Total Documents:", len(docs))
        assert found_doc, "Uploaded document missing from patient records"

    # 11. Download Document File Content
    req = urllib.request.Request(f"{BASE}/documents/{document_id}/download", headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req) as resp:
        file_bytes = resp.read()
        print("[PASS] 11. Medical Document Download: Received bytes:", len(file_bytes))
        assert len(file_bytes) > 0, "Downloaded file was empty"

    # 12. Run Real AI Deep Learning Inference
    from PIL import Image
    import io
    img = Image.new("RGB", (224, 224), color=(100, 150, 200))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    img_bytes = buf.getvalue()

    ai_boundary = "----WebKitFormBoundaryAiTest001"
    ai_body = (
        f"--{ai_boundary}\r\n"
        f'Content-Disposition: form-data; name="image"; filename="patient_mri_test.jpg"\r\n'
        f"Content-Type: image/jpeg\r\n\r\n"
    ).encode("latin-1") + img_bytes + (
        f"\r\n--{ai_boundary}\r\n"
        f'Content-Disposition: form-data; name="analysis_type"\r\n\r\nBRAIN_MRI\r\n'
        f"--{ai_boundary}--\r\n"
    ).encode("latin-1")

    req = urllib.request.Request(f"{BASE}/ai/infer", data=ai_body, headers={
        "Content-Type": f"multipart/form-data; boundary={ai_boundary}",
        "Authorization": f"Bearer {token}"
    })
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        ai_res = res.get("data", res)
        print("[PASS] 12. AI Direct Inference:")
        print("      Prediction:", ai_res.get("predicted_class", ai_res.get("prediction")))
        print("      Confidence:", f"{ai_res.get('confidence', 0)*100:.2f}%")
        print("      Grad-CAM Heatmap Base64 Length:", len(ai_res.get("gradcam_b64", "") or ""))
        print("      All Class Probabilities:", ai_res.get("probabilities"))
        assert (ai_res.get("predicted_class") or ai_res.get("prediction")) is not None, "Missing prediction"
        assert ai_res.get("gradcam_b64") is not None, "Missing Grad-CAM heatmap"

    # 13. Token Refresh Session Persistence
    refresh_payload = json.dumps({"refresh_token": refresh_token}).encode("utf-8")
    req = urllib.request.Request(f"{BASE}/auth/refresh", data=refresh_payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        new_token = res["access_token"]
        new_user = res["user"]
        print("[PASS] 13. Token Refresh Session:")
        print("      New Access Token Generated | Retained Patient ID:", new_user.get("patient_id"))
        assert new_user.get("patient_id") == patient_id, "Patient ID lost after refresh"

    # 14. Access Protected Endpoint with New Token
    req = urllib.request.Request(f"{BASE}/patients/me", headers={"Authorization": f"Bearer {new_token}"})
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        print("[PASS] 14. Authenticated Request with Refreshed Token: Success! Profile:", res["data"].get("patient_id"))

    print("\n=======================================================")
    print(">>> ALL 14 PATIENT WORKFLOW E2E CHECKS COMPLETED WITH 100% PASS <<<")
    print("=======================================================")

if __name__ == "__main__":
    run_test()
