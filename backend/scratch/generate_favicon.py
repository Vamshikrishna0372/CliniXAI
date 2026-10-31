import os
from PIL import Image, ImageDraw

# 1. Create SVG Favicon
svg_content = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">
  <defs>
    <linearGradient id="bgGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#0284c7" />
      <stop offset="100%" stop-color="#1d4ed8" />
    </linearGradient>
    <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="4" stdDeviation="6" flood-color="#0284c7" flood-opacity="0.4"/>
    </filter>
  </defs>
  <!-- Background squircle -->
  <rect x="8" y="8" width="112" height="112" rx="28" fill="url(#bgGrad)" filter="url(#glow)"/>
  <!-- Activity ECG pulse line -->
  <path d="M 24 64 L 44 64 L 54 40 L 66 88 L 78 52 L 86 64 L 104 64" 
        fill="none" 
        stroke="#ffffff" 
        stroke-width="9" 
        stroke-linecap="round" 
        stroke-linejoin="round"/>
</svg>"""

svg_path = os.path.join("clinixai-health-flow", "public", "favicon.svg")
with open(svg_path, "w", encoding="utf-8") as f:
    f.write(svg_content)
print("Saved favicon.svg successfully.")

# 2. Render multi-resolution ICO file (256, 128, 64, 48, 32, 16)
sizes = [256, 128, 64, 48, 32, 16]
images = []

for s in sizes:
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Scale factor
    f = s / 128.0
    r = int(28 * f)
    pad = int(8 * f)
    
    # Draw rounded rectangle background (cyan/blue)
    draw.rounded_rectangle(
        [pad, pad, s - pad, s - pad],
        radius=r,
        fill=(14, 165, 233, 255)  # Sky blue #0ea5e9
    )
    
    # Pulse path points
    pts = [
        (24 * f, 64 * f),
        (44 * f, 64 * f),
        (54 * f, 40 * f),
        (66 * f, 88 * f),
        (78 * f, 52 * f),
        (86 * f, 64 * f),
        (104 * f, 64 * f),
    ]
    
    line_w = max(2, int(9 * f))
    # Draw line segments
    for i in range(len(pts) - 1):
        draw.line([pts[i], pts[i+1]], fill=(255, 255, 255, 255), width=line_w)
    
    # Draw rounded caps at points
    r_cap = line_w // 2
    for p in pts:
        draw.ellipse([p[0]-r_cap, p[1]-r_cap, p[0]+r_cap, p[1]+r_cap], fill=(255, 255, 255, 255))
        
    images.append(img)

ico_path = os.path.join("clinixai-health-flow", "public", "favicon.ico")
images[0].save(
    ico_path,
    format="ICO",
    sizes=[(s, s) for s in sizes],
    append_images=images[1:]
)
print("Saved multi-resolution CliniXAI favicon.ico successfully.")

