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

print("=== ALL DOCUMENTS WITH MISMATCHED OR USR- PATIENT_ID ===")
for d in docs:
    pid = d.get("patient_id")
    p_by_pid = next((p for p in patients if p.get("patient_id") == pid), None)
    p_by_uid = next((p for p in patients if p.get("user_id") == pid), None)
    if not p_by_pid:
        uploader = next((u for u in users if u.get("user_id") == d.get("uploaded_by")), None)
        print(f"Doc: {d.get('document_id')} | Title: {d.get('title')} | Cat: {d.get('category')} | File: {d.get('original_file_name') or d.get('file_name')}")
        print(f"  doc.patient_id: {pid} (is_uid: {bool(p_by_uid)})")
        print(f"  Uploaded by: {d.get('uploaded_by')} ({uploader.get('email') if uploader else 'unknown'})")
        if p_by_uid:
            print(f"  ACTUAL PATIENT PROFILE ID: {p_by_uid.get('patient_id')}")
        print("---")
