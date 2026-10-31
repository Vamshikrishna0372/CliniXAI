import json

with open(".data_persist/audit_logs.json", "r", encoding="utf-8") as f:
    logs = json.load(f)

print("=== AUDIT LOGS FOR D1D7D2 ===")
for l in logs:
    if "D1D7D2" in str(l):
        print(json.dumps(l, indent=2))

