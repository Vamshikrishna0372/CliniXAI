import json

with open(".data_persist/ai_analyses.json", "r") as f:
    analyses = json.load(f)

print(f"Total analyses: {len(analyses)}")
for a in analyses:
    aid = a.get("analysis_id")
    pid = a.get("patient_id")
    did = a.get("document_id")
    exp = a.get("explainability", {})
    gradcam_key = exp.get("artifact_storage_key") if exp else None
    print(f"AID: {aid} | PID: {pid} | DID: {did} | GradCAM: {gradcam_key} | Status: {a.get('status')}")

