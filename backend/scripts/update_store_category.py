with open("clinixai-health-flow/src/lib/store/clinix-store.tsx", "r", encoding="utf-8") as f:
    text = f.read()

target = """              if (rawCat.includes("image") || rawCat.includes("x-ray") || rawCat.includes("mri") || rawCat.includes("ct")) cat = "Medical Image";
              else if (rawCat.includes("lab") || rawCat.includes("diagnostic")) cat = "Diagnostic Report";
              else if (rawCat.includes("prescription")) cat = "Prescription";
              else if (rawCat.includes("consultation")) cat = "Consultation";
              else if (rawCat.includes("ai")) cat = "AI Report";"""

replacement = """              if (d.is_mri || rawCat.includes("brain") || rawCat.includes("mri") || (d.title || "").toLowerCase().includes("mri") || (d.original_file_name || "").toLowerCase().includes("mri")) cat = "Brain MRI";
              else if (rawCat.includes("x-ray") || rawCat.includes("xray") || (d.title || "").toLowerCase().includes("x-ray")) cat = "Chest X-Ray";
              else if (rawCat.includes("ct")) cat = "CT Scan";
              else if (rawCat.includes("image")) cat = "Medical Image";
              else if (rawCat.includes("lab") || rawCat.includes("diagnostic")) cat = "Lab Report";
              else if (rawCat.includes("prescription")) cat = "Prescription";
              else if (rawCat.includes("consultation")) cat = "Consultation";
              else if (rawCat.includes("ai")) cat = "AI Report";
              else cat = d.category || "Other";"""

if target in text:
    print("Found LF")
    text = text.replace(target, replacement)
elif target.replace("\n", "\r\n") in text:
    print("Found CRLF")
    text = text.replace(target.replace("\n", "\r\n"), replacement.replace("\n", "\r\n"))
else:
    print("Not found")

with open("clinixai-health-flow/src/lib/store/clinix-store.tsx", "w", encoding="utf-8", newline="") as f:
    f.write(text)
print("Done")

