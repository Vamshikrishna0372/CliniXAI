import asyncio
import json
from pathlib import Path
from motor.motor_asyncio import AsyncIOMotorClient

async def check():
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

    print("=== EXAMINING ALL DOCUMENTS WITH BRAIN / MRI ===")
    mri_docs = []
    for d in docs:
        text = (str(d.get("title")) + " " + str(d.get("filename") or d.get("file_name")) + " " + str(d.get("category"))).lower()
        if "brain" in text or "mri" in text:
            mri_docs.append(d)

    print(f"Total Brain/MRI docs: {len(mri_docs)}")
    for d in mri_docs:
        pid = d.get("patient_id")
        pat_by_pid = next((p for p in patients if p.get("patient_id") == pid), None)
        pat_by_uid = next((p for p in patients if p.get("user_id") == pid), None)
        user_by_uid = next((u for u in users if u.get("user_id") == pid), None)
        uploader = next((u for u in users if u.get("user_id") == d.get("uploaded_by")), None)
        
        print("\n------------------------------------------------------------")
        print(f"Doc ID: {d.get('document_id')}")
        print(f"  Title: {d.get('title')}")
        print(f"  Category: {d.get('category')}")
        print(f"  Filename: {d.get('file_name') or d.get('filename') or d.get('original_file_name')}")
        print(f"  doc.patient_id: {pid}")
        print(f"  doc.uploaded_by: {d.get('uploaded_by')} ({uploader.get('email') if uploader else 'unknown'}) (Role: {uploader.get('role') if uploader else 'unknown'})")
        print(f"  is_deleted: {d.get('is_deleted')}")
        print(f"  created_at: {d.get('created_at')}")
        if pat_by_pid:
            print(f"  Matches patient record by patient_id: {pat_by_pid.get('patient_id')} (user_id={pat_by_pid.get('user_id')}, email={pat_by_pid.get('email')})")
        if pat_by_uid:
            print(f"  Matches patient record by user_id: {pat_by_uid.get('patient_id')} (user_id={pat_by_uid.get('user_id')}, email={pat_by_uid.get('email')})")
        if not pat_by_pid and not pat_by_uid:
            print(f"  WARNING: doc.patient_id '{pid}' does NOT match any patient record!")

asyncio.run(check())
