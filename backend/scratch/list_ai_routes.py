import re

with open("backend/app/api/v1/routes/ai_analyses.py") as f:
    text = f.read()

routes = re.findall(r'@router\.(get|post|put|delete|patch)\(["\'](.*?)["\']', text)
for method, path in routes:
    print(f"{method.upper():6} {path}")

