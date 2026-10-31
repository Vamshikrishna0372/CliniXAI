p2 = r"clinixai-health-flow/src/routes/app.ai-analysis.$id.tsx"
with open(p2, "r", encoding="utf-8") as f:
    c2 = f.read()

target = """  const gradcamUrl = gradcamBlobUrl || activeReport?.gradcamUrl;
  const originalUrl = originalBlobUrl || activeReport?.imageUrl;

  if (loadingRemote) {"""

repl = """  const gradcamUrl = gradcamBlobUrl || activeReport?.gradcamUrl;
  const originalUrl = originalBlobUrl || activeReport?.imageUrl;

  if (user?.role === "patient") {
    return null;
  }

  if (loadingRemote) {"""

if target in c2:
    c2 = c2.replace(target, repl)
    with open(p2, "w", encoding="utf-8") as f:
        f.write(c2)
    print("Added patient early return in app.ai-analysis.$id.tsx")
else:
    print("Target not found")

