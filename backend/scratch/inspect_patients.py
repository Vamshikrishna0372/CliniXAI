import json
from pathlib import Path

snap_dir = Path(".data_persist")
if not snap_dir.exists():
    snap_dir = Path("backend/.data_persist")

with open(snap_dir / "users.json", "r", encoding="utf-8") as f:
    users = json.load(f)

with open(snap_dir / "patients.json", "r", encoding="utf-8") as f:
    patients = json.load(f)

with open(snap_dir / "documents.json", "r", encoding="utf-8") as f:
    docs = json.load(f)

print("=== REAL PATIENT USERS ===")
for u in users:
    if u.get("role") == "patient" and not u.get("email", "").endswith(".test"):
        p = next((p for p in patients if p.get("user_id") == u.get("user_id")), None)
        p_by_email = next((p for p in patients if p.get("email") == u.get("email")), None)
        user_docs = [d for d in docs if d.get("patient_id") in [u.get("user_id"), p.get("patient_id") if p else None]]
        print(f"User: {u.get('user_id')} | Email: {u.get('email')} | u.patient_id: {u.get('patient_id')}")
        print(f"  Patient profile: {p.get('patient_id') if p else 'NONE'} (by email: {p_by_email.get('patient_id') if p_by_email else 'NONE'})")
        print(f"  Total docs: {len(user_docs)}")
        for d in user_docs:
            print(f"    Doc: {d.get('document_id')} | doc.patient_id: {d.get('patient_id')} | Cat: {d.get('category')} | File: {d.get('original_file_name') or d.get('file_name')} | Title: {d.get('title')}")
