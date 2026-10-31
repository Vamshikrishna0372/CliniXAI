import json, os

snap_dir = ".data_persist" if os.path.exists(".data_persist") else "backend/.data_persist"

with open(f"{snap_dir}/documents.json", encoding="utf-8") as f:
    docs = json.load(f)
with open(f"{snap_dir}/patients.json", encoding="utf-8") as f:
    patients = json.load(f)
with open(f"{snap_dir}/users.json", encoding="utf-8") as f:
    users = json.load(f)
with open(f"{snap_dir}/appointments.json", encoding="utf-8") as f:
    apts = json.load(f)
with open(f"{snap_dir}/doctors.json", encoding="utf-8") as f:
    docs_list = json.load(f)

print("=== PATIENTS WHO HAVE DOCUMENTS ===")
pids_with_docs = set(d.get("patient_id") for d in docs if d.get("patient_id"))
for pid in pids_with_docs:
    p_rec = next((p for p in patients if p.get("patient_id") == pid or p.get("user_id") == pid), None)
    u_rec = next((u for u in users if u.get("user_id") == pid or (p_rec and u.get("user_id") == p_rec.get("user_id"))), None)
    p_docs = [d for d in docs if d.get("patient_id") == pid]
    p_apts = [a for a in apts if a.get("patient_id") == pid or (p_rec and a.get("patient_id") == p_rec.get("patient_id"))]
    print(f"\nID: {pid}")
    print(f"  Name: {p_rec.get('first_name', '')} {p_rec.get('last_name', '')} | Email: {p_rec.get('email') if p_rec else (u_rec.get('email') if u_rec else 'None')}")
    print(f"  Is real patient profile: {bool(p_rec)} (patient_id={p_rec.get('patient_id') if p_rec else 'N/A'}, user_id={p_rec.get('user_id') if p_rec else 'N/A'})")
    print(f"  Appointments ({len(p_apts)}): {[a.get('appointment_id') for a in p_apts]}")
    print(f"  Documents ({len(p_docs)}):")
    for d in p_docs:
        print(f"    - Doc ID: {d.get('document_id')}")
        print(f"      Title: {d.get('title')}")
        print(f"      Category: {d.get('category')}")
        print(f"      Mime: {d.get('mime_type')}")
        print(f"      Filename: {d.get('original_file_name') or d.get('file_name')}")
        print(f"      Uploaded by: {d.get('uploaded_by')}")
        print(f"      Storage: {d.get('storage_path')}")
        print(f"      Deleted: {d.get('is_deleted')}")

