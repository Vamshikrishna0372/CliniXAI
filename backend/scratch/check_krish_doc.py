import json

with open(".data_persist/documents.json", "r", encoding="utf-8") as f:
    docs = json.load(f)

for d in docs:
    if d.get("document_id") == "DOC-154CB274CCF5":
        print(json.dumps(d, indent=2))
        break

