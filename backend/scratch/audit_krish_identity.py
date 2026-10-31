import json

KRISH_PID = "PAT-2026-85014E"
KRISH_UID = "USR-2026-E66A3C"

def check_file(filename, key="patient_id"):
    try:
        with open(f".data_persist/{filename}", "r", encoding="utf-8") as f:
            items = json.load(f)
        matches = [x for x in items if x.get(key) in (KRISH_PID, KRISH_UID) or x.get("patient_id") in (KRISH_PID, KRISH_UID)]
        print(f"=== {filename} ({len(matches)} matches for Krish) ===")
        for m in matches:
            summary = {k: m[k] for k in ["appointment_id", "consultation_id", "document_id", "record_id", "analysis_id", "doctor_id", "status", "scheduled_start_time", "title", "category", "file_name", "original_file_name"] if k in m}
            print(" ", summary)
        return matches
    except Exception as e:
        print(f"Error checking {filename}: {e}")
        return []

check_file("appointments.json")
check_file("consultations.json")
docs = check_file("documents.json")
recs = check_file("medical_records.json")
analyses = check_file("ai_analyses.json")

print("\n=== AI ANALYSES FOR KRISH (PAT-2026-85014E) ===")
for a in analyses:
    print(json.dumps(a, indent=2))
