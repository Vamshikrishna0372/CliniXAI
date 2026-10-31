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

print("=== CHECKING APPOINTMENT LINKAGES FOR ALL PATIENTS WITH BRAIN MRI ===")
for d in docs:
    text = (str(d.get("title")) + " " + str(d.get("filename") or d.get("file_name")) + " " + str(d.get("category"))).lower()
    if "brain" in text or "mri" in text:
        pid = d.get("patient_id")
        pat = next((p for p in patients if p.get("patient_id") == pid or p.get("user_id") == pid), None)
        uploader = next((u for u in users if u.get("user_id") == d.get("uploaded_by")), None)
        if pat:
            check_pids = list(set([pat.get("patient_id"), pat.get("user_id"), pid]))
            apts = [a for a in appointments if a.get("patient_id") in check_pids]
            docs_in_apts = list(set([a.get("doctor_id") for a in apts]))
            print(f"Doc: {d.get('document_id')} | Title: {d.get('title')} | Cat: {d.get('category')}")
            print(f"  Patient: {pat.get('patient_id')} (user={pat.get('user_id')}, email={pat.get('email')})")
            print(f"  doc.patient_id in doc: {pid}")
            print(f"  Uploaded by: {d.get('uploaded_by')} (role: {uploader.get('role') if uploader else 'unknown'})")
            print(f"  Linked Doctors in appointments: {docs_in_apts}")
            print(f"  Appointments count: {len(apts)}")
            print("---")
