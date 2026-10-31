import urllib.request
import json

# Log in as Dr. Arjun Rao
login_req = urllib.request.Request(
    "http://localhost:8000/api/v1/auth/login",
    data=json.dumps({"email": "doctor.arjun@clinixai.com", "password": "Doctor@123"}).encode(),
    headers={"Content-Type": "application/json"}
)
res = urllib.request.urlopen(login_req)
token_data = json.loads(res.read().decode())
token = token_data["access_token"]
print("Doctor logged in successfully. Token obtained.")

# Fetch documents for PAT-2026-85014E
doc_req = urllib.request.Request(
    "http://localhost:8000/api/v1/documents?patient_id=PAT-2026-85014E",
    headers={"Authorization": f"Bearer {token}"}
)
try:
    doc_res = urllib.request.urlopen(doc_req)
    data = json.loads(doc_res.read().decode())
    print("API returned status 200!")
    print(f"Total documents returned: {data.get('total')}, items count: {len(data.get('items', []))}")
    for item in data.get("items", []):
        print("Item:", item.get("document_id"), item.get("title"), item.get("category"), item.get("mime_type"), item.get("patient_id"))
except urllib.error.HTTPError as e:
    print("HTTPError:", e.code, e.read().decode())
except Exception as e:
    print("Exception:", e)
