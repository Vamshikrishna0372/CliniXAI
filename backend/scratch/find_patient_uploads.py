import json
from pathlib import Path

snap_dir = Path(".data_persist")
if not snap_dir.exists():
    snap_dir = Path("backend/.data_persist")

with open(snap_dir / "documents.json", "r", encoding="utf-8") as f:
    docs = json.load(f)
with open(snap_dir / "patients.json", "r", encoding="utf-8") as f:
    patients = json.load(f)
with open(snap_dir / "users.json", "r", encoding="utf-8") as f:
    users = json.load(f)
with open(snap_dir / "appointments.json", "r", encoding="utf-8") as f:
    appointments = json.load(f)
with open(snap_dir / "doctors.json", "r", encoding="utf-8") as f:
    doctors = json.load(f)

# Find all patients who uploaded a document from Patient -> Documents
for d in docs:
    uploader = next((u for u in users if u.get("user_id") == d.get("uploaded_by")), None)
    if uploader and uploader.get("role") == "patient":
        pid = d.get("patient_id")
        pat = next((p for p in patients if p.get("patient_id") == pid or p.get("user_id") == pid or p.get("email") == uploader.get("email")), None)
        print("=================================================================")
        print(f"Doc ID: {d.get('document_id')}")
        print(f"  Title: {d.get('title')}")
        print(f"  Filename: {d.get('original_file_name') or d.get('file_name')}")
        print(f"  Category: {d.get('category')}")
        print(f"  doc.patient_id: {pid}")
        print(f"  Uploader user_id: {uploader.get('user_id')} ({uploader.get('email')})")
        print(f"  Matched patient: {pat.get('patient_id') if pat else 'NONE'}")
        if pat:
            print(f"    pat.patient_id: {pat.get('patient_id')}")
            print(f"    pat.user_id: {pat.get('user_id')}")
            print(f"    pat.email: {pat.get('email')}")
            # Find appointments for this patient
            p_apts = [a for a in appointments if a.get("patient_id") in [pat.get("patient_id"), pat.get("user_id"), uploader.get("user_id")]]
            print(f"    Appointments count: {len(p_apts)}")
            for a in p_apts:
                doc = next((doc for doc in doctors if doc.get("doctor_id") == a.get("doctor_id")), None)
                print(f"      Apt {a.get('appointment_id')}: Doctor {a.get('doctor_id')} ({doc.get('full_name') if doc else 'unknown'}) - Status: {a.get('status')}")
