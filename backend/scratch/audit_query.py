import json, os

snap_dir = ".data_persist" if os.path.exists(".data_persist") else "backend/.data_persist"

with open(f"{snap_dir}/documents.json", encoding="utf-8") as f:
    docs = json.load(f)

with open(f"{snap_dir}/patients.json", encoding="utf-8") as f:
    patients = json.load(f)

with open(f"{snap_dir}/users.json", encoding="utf-8") as f:
    users = json.load(f)

with open(f"{snap_dir}/appointments.json", encoding="utf-8") as f:
    appointments = json.load(f)

with open(f"{snap_dir}/doctors.json", encoding="utf-8") as f:
    doctors = json.load(f)

print(f"Total documents: {len(docs)}")
print(f"Total patients: {len(patients)}")
print(f"Total users: {len(users)}")
print(f"Total appointments: {len(appointments)}")

print("\n--- ALL DOCUMENTS ---")
for i, d in enumerate(docs):
    uploader = next((u for u in users if u.get("user_id") == d.get("uploaded_by")), None)
    pat_by_pid = next((p for p in patients if p.get("patient_id") == d.get("patient_id")), None)
    pat_by_uid = next((p for p in patients if p.get("user_id") == d.get("patient_id")), None)
    print(f"[{i+1}] Doc ID: {d.get('document_id')}")
    print(f"    title: {d.get('title')}")
    print(f"    category: {d.get('category')}")
    print(f"    mime_type: {d.get('mime_type')}")
    print(f"    file_name: {d.get('file_name')}")
    print(f"    original_file_name: {d.get('original_file_name')}")
    print(f"    storage_path: {d.get('storage_path')}")
    print(f"    patient_id: {d.get('patient_id')}")
    print(f"    uploaded_by: {d.get('uploaded_by')} ({uploader.get('email') if uploader else 'unknown'})")
    print(f"    is_deleted: {d.get('is_deleted')}")
    print(f"    appointment_id: {d.get('appointment_id')}")
    print(f"    medical_record_id: {d.get('medical_record_id')}")
    print(f"    ai_analysis_id: {d.get('ai_analysis_id')}")
    print(f"    has_ai_analysis: {d.get('has_ai_analysis')}")
    print(f"    pat_by_pid match: {pat_by_pid.get('patient_id') if pat_by_pid else 'NO'}")
    print(f"    pat_by_uid match: {pat_by_uid.get('patient_id') if pat_by_uid else 'NO'}")

