import json
from pathlib import Path

snap_dir = Path(".data_persist")
if not snap_dir.exists():
    snap_dir = Path("backend/.data_persist")

with open(snap_dir / "documents.json", "r", encoding="utf-8") as f:
    docs = json.load(f)

print(f"Total documents: {len(docs)}")
for d in docs:
    text = (str(d.get("title")) + " " + str(d.get("filename")) + " " + str(d.get("category")) + " " + str(d.get("description"))).lower()
    if any(k in text for k in ["brain", "mri", "image", "scan", "neuro", "xray", "x-ray"]):
        print("\n--- MATCHING DOC ---")
        for k, v in d.items():
            print(f"  {k}: {v}")

with open(snap_dir / "patients.json", "r", encoding="utf-8") as f:
    patients = json.load(f)

pat_map = {p.get("patient_id"): p for p in patients}
user_pat_map = {p.get("user_id"): p for p in patients}

print("\n--- PATIENT SUMMARY FOR MATCHING DOCS ---")
for d in docs:
    text = (str(d.get("title")) + " " + str(d.get("filename")) + " " + str(d.get("category")) + " " + str(d.get("description"))).lower()
    if any(k in text for k in ["brain", "mri", "image", "scan", "neuro", "xray", "x-ray"]):
        pid = d.get("patient_id")
        p_by_pid = pat_map.get(pid)
        p_by_uid = user_pat_map.get(pid)
        print(f"Doc {d.get('document_id')} | doc.patient_id={pid} | found_by_patient_id={bool(p_by_pid)} | found_by_user_id={bool(p_by_uid)}")
        if p_by_pid:
            print(f"   -> Patient record: id={p_by_pid.get('patient_id')}, user_id={p_by_pid.get('user_id')}, name={p_by_pid.get('full_name') or p_by_pid.get('first_name')}")
        if p_by_uid:
            print(f"   -> Found as User ID! Actual patient_id={p_by_uid.get('patient_id')}, user_id={p_by_uid.get('user_id')}, name={p_by_uid.get('full_name') or p_by_uid.get('first_name')}")
