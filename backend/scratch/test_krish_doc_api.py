import urllib.request
import json

# Login as Dr. Arjun
req = urllib.request.Request(
    "http://127.0.0.1:8000/api/v1/auth/login",
    data=json.dumps({"email": "doctor.arjun@clinixai.com", "password": "Doctor@123"}).encode("utf-8"),
    headers={"Content-Type": "application/json"}
)
with urllib.request.urlopen(req) as resp:
    token = json.loads(resp.read().decode())["access_token"]

# Check Krish document detail
req2 = urllib.request.Request(
    "http://127.0.0.1:8000/api/v1/documents/DOC-154CB274CCF5",
    headers={"Authorization": f"Bearer {token}"}
)
try:
    with urllib.request.urlopen(req2) as resp:
        print("Document detail status:", resp.status)
        doc = json.loads(resp.read().decode())
        print("Doc patient_id:", doc.get("patient_id"))
except urllib.error.HTTPError as e:
    print("Document detail HTTPError:", e.code, e.read().decode())

# Check what createAnalysis would do (WITHOUT creating if we don't want, but let's test a dry run or inspect code)

