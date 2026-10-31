import json
from pathlib import Path

def migrate_provenance():
    persist_paths = [
        Path('.data_persist'),
        Path('backend/.data_persist'),
    ]

    for pdir in persist_paths:
        doc_file = pdir / 'documents.json'
        if not doc_file.exists():
            continue

        users_file = pdir / 'users.json'
        doctors_file = pdir / 'doctors.json'
        patients_file = pdir / 'patients.json'
        analyses_file = pdir / 'ai_analyses.json'

        users = {}
        if users_file.exists():
            with open(users_file, 'r', encoding='utf-8') as f:
                users = {u.get('user_id'): u for u in json.load(f)}

        doctors = {}
        if doctors_file.exists():
            with open(doctors_file, 'r', encoding='utf-8') as f:
                d_list = json.load(f)
                doctors = {d.get('user_id'): d for d in d_list}
                doctors.update({d.get('doctor_id'): d for d in d_list})

        patients = {}
        if patients_file.exists():
            with open(patients_file, 'r', encoding='utf-8') as f:
                p_list = json.load(f)
                patients = {p.get('user_id'): p for p in p_list}
                patients.update({p.get('patient_id'): p for p in p_list})

        analyses = {}
        analyses_by_doc = {}
        if analyses_file.exists():
            with open(analyses_file, 'r', encoding='utf-8') as f:
                a_list = json.load(f)
                analyses = {a.get('analysis_id'): a for a in a_list}
                for a in a_list:
                    if a.get('document_id'):
                        analyses_by_doc[a['document_id']] = a

        with open(doc_file, 'r', encoding='utf-8') as f:
            docs = json.load(f)

        updated_count = 0
        for d in docs:
            ub = d.get('uploaded_by') or d.get('uploaded_by_user_id')
            d['uploaded_by'] = ub or 'unknown'
            d['uploaded_by_user_id'] = ub

            u_role = 'unknown'
            u_name = 'Unknown'
            if ub and ub != 'system' and ub != 'None':
                u = users.get(ub)
                if u:
                    u_role = str(u.get('role', 'unknown')).lower()
                    u_name = u.get('full_name') or u.get('name')
                if not u_name or u_role == 'unknown':
                    doc = doctors.get(ub)
                    if doc:
                        u_role = 'doctor'
                        u_name = doc.get('full_name') or doc.get('name') or 'Doctor'
                    else:
                        pat = patients.get(ub)
                        if pat:
                            u_role = 'patient'
                            u_name = pat.get('full_name') or f"{pat.get('first_name', '')} {pat.get('last_name', '')}".strip() or 'Patient'
            d['uploader_role'] = u_role
            d['uploader_name'] = u_name

            # Modality
            cat = str(d.get('category', '')).lower()
            title = str(d.get('title', '')).lower()
            fn = str(d.get('original_file_name', '')).lower()
            if 'mri' in cat or 'mri' in title or 'mri' in fn or 'brain' in title:
                d['modality'] = 'Brain MRI'
            elif 'xray' in cat or 'x-ray' in cat or 'xray' in title or 'x-ray' in title:
                d['modality'] = 'Chest X-Ray'
            elif 'ct' in cat or 'ct' in title:
                d['modality'] = 'CT Scan'
            elif 'derm' in cat or 'skin' in cat:
                d['modality'] = 'Skin Dermoscopy'
            elif 'fundus' in cat or 'retin' in cat:
                d['modality'] = 'Retinal Fundus'
            else:
                d['modality'] = d.get('category') or 'Other'

            # AI Analysis linkage
            ai_id = d.get('ai_analysis_id')
            if not ai_id and d.get('document_id') in analyses_by_doc:
                matching_an = analyses_by_doc[d['document_id']]
                d['ai_analysis_id'] = matching_an.get('analysis_id')
                d['ai_analysis_status'] = matching_an.get('status')
            elif ai_id and ai_id in analyses:
                d['ai_analysis_status'] = analyses[ai_id].get('status')

            updated_count += 1

        with open(doc_file, 'w', encoding='utf-8') as f:
            json.dump(docs, f, indent=2)

        print(f"Updated {updated_count} documents in {doc_file}")

if __name__ == '__main__':
    migrate_provenance()
