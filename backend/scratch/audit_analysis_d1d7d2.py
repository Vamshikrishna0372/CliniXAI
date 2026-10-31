import json

with open(".data_persist/ai_analyses.json", "r", encoding="utf-8") as f:
    analyses = json.load(f)

match = None
for a in analyses:
    if a.get("analysis_id") == "AI-2026-D1D7D2" or a.get("_id") == "AI-2026-D1D7D2":
        match = a
        break

if match:
    print("=== FOUND AI-2026-D1D7D2 ===")
    print(json.dumps(match, indent=2))
else:
    print("AI-2026-D1D7D2 NOT FOUND directly. Checking all analyses with D1D7D2 or recent...")
    for a in analyses:
        if "D1D7D2" in str(a):
            print("MATCH:", json.dumps(a, indent=2))

