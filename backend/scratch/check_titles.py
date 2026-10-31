import os, re

titles = []
for root, dirs, files in os.walk(os.path.join("clinixai-health-flow", "src", "routes")):
    for f in files:
        if f.endswith(".tsx"):
            path = os.path.join(root, f)
            with open(path, "r", encoding="utf-8", errors="ignore") as fp:
                txt = fp.read()
                m = re.findall(r'title:\s*["\'`](.*?)["\'`]', txt)
                for t in m:
                    titles.append((f, t))
for f, t in sorted(titles):
    print(f"{f:30}: {t}")

