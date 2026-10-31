import urllib.request
import json

req = urllib.request.Request(
    "http://127.0.0.1:8000/api/v1/auth/login",
    data=json.dumps({"email": "doctor.arjun@clinixai.com", "password": "Doctor@123"}).encode("utf-8"),
    headers={"Content-Type": "application/json"}
)
with urllib.request.urlopen(req) as resp:
    token = json.loads(resp.read().decode())["access_token"]

req2 = urllib.request.Request(
    "http://127.0.0.1:8000/api/v1/patients?page_size=100",
    headers={"Authorization": f"Bearer {token}"}
)
with urllib.request.urlopen(req2) as resp:
    data = json.loads(resp.read().decode())

print("API Response structure:")
if isinstance(data, dict):
    print("Keys:", list(data.keys()))
    items = data.get("items") or data.get("data")
    if isinstance(items, dict):
        items = items.get("items")
    print(f"Total items: {len(items) if isinstance(items, list) else type(items)}")
    if isinstance(items, list):
        for p in items:
            name = f"{p.get('first_name', '')} {p.get('last_name', '')}"
            print(f"  {p.get('patient_id')}: {name} ({p.get('email')})")
