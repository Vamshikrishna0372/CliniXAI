import json

with open(".data_persist/ai_analyses.json", "r", encoding="utf-8") as f:
    analyses = json.load(f)

print(f"Total AI Analyses in database: {len(analyses)}")
for a in analyses[-15:]:
    print(f"  {a.get('analysis_id')}: patient_id={a.get('patient_id')}, doc_id={a.get('document_id')}, med_rec_id={a.get('medical_record_id')}, status={a.get('status')}, created_at={a.get('created_at')}")

