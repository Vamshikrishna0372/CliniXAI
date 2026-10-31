import json

with open('.data_persist/users.json', 'r', encoding='utf-8') as f:
    users = {u.get('user_id'): u for u in json.load(f)}
with open('.data_persist/doctors.json', 'r', encoding='utf-8') as f:
    doc_list = json.load(f)
    doctors = {d.get('user_id'): d for d in doc_list}
    doctors.update({d.get('doctor_id'): d for d in doc_list})
with open('.data_persist/patients.json', 'r', encoding='utf-8') as f:
    pat_list = json.load(f)
    patients = {p.get('user_id'): p for p in pat_list}
    patients.update({p.get('patient_id'): p for p in pat_list})

with open('.data_persist/documents.json', 'r', encoding='utf-8') as f:
    docs = json.load(f)

for d in docs:
    ub = d.get('uploaded_by')
    u = users.get(ub)
    role = 'unknown'
    name = 'Unknown'
    if u:
        role = u.get('role', 'unknown')
        name = u.get('full_name') or u.get('name')
    if role == 'unknown' or not name:
        doc = doctors.get(ub)
        if doc:
            role = 'doctor'
            name = doc.get('full_name') or doc.get('name') or 'Doctor'
        else:
            pat = patients.get(ub)
            if pat:
                role = 'patient'
                name = pat.get('full_name') or f"{pat.get('first_name', '')} {pat.get('last_name', '')}".strip()
    
    title = str(d.get('title') or d.get('original_file_name') or '')
    cat = str(d.get('category') or '')
    if 'mri' in title.lower() or 'mri' in cat.lower() or 'brain' in title.lower():
        print(f"{d.get('document_id')} | Patient: {d.get('patient_id')} | Uploader: {name} ({role}) | Title: {title}")
