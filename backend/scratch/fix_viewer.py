import os

path = os.path.join("clinixai-health-flow", "src", "components", "domain", "medical-image-viewer.tsx")
with open(path, "r", encoding="utf-8") as f:
    text = f.read()

target = """          {src ? (
            <img src={src} alt={label} className="h-full w-full object-contain" />
          ) : isHeatmap ? (
            <div
              className="h-full w-full"
              style={{ background: "radial-gradient(closest-side at 55% 45%, rgba(239,68,68,0.85), rgba(234,179,8,0.6) 30%, rgba(59,130,246,0.35) 55%, transparent 75%)" }}
            />
          ) : (
            <div className="h-full w-full bg-gradient-to-br from-slate-700 via-slate-800 to-slate-950" />
          )}"""

replacement = """          {src ? (
            <img src={src} alt={label} className="h-full w-full object-contain" />
          ) : (
            <div className="flex flex-col items-center justify-center p-6 text-center text-xs text-muted-foreground/60 select-none">
              <ImageIcon className="h-8 w-8 mb-2 opacity-40" />
              <span>{isHeatmap ? "Grad-CAM heatmap unavailable" : "Original scan unavailable"}</span>
            </div>
          )}"""

if target in text:
    text = text.replace(target, replacement)
    print("Replaced LF")
elif target.replace("\n", "\r\n") in text:
    text = text.replace(target.replace("\n", "\r\n"), replacement.replace("\n", "\r\n"))
    print("Replaced CRLF")
else:
    print("Target not found directly")

with open(path, "w", encoding="utf-8") as f:
    f.write(text)
print("Saved medical-image-viewer.tsx successfully.")

