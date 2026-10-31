with open("clinixai-health-flow/src/routes/app.patients.$id.tsx", "r", encoding="utf-8") as f:
    text = f.read()

target = """  // Filtered documents
  const filteredDocuments = useMemo(() => {
    if (docCategoryFilter === "all") return documents;
    const target = docCategoryFilter.toLowerCase().replace(/[\s-_]/g, "");
    return documents.filter((d: any) => {
      const cat = (d.category || "").toLowerCase().replace(/[\s-_]/g, "");
      const title = (d.title || "").toLowerCase();
      const fname = (d.original_file_name || d.file_name || d.filename || "").toLowerCase();
      if (target === "mri") {
        return cat === "mri" || cat === "brainmri" || cat.includes("mri") || title.includes("mri") || fname.includes("mri");
      }
      if (target === "xray") {
        return cat === "xray" || cat === "chestxray" || cat.includes("xray") || cat.includes("cxr") || title.includes("xray") || title.includes("x-ray");
      }
      return cat === target;
    });
  }, [documents, docCategoryFilter]);"""

replacement = """  // Filtered documents
  const filteredDocuments = useMemo(() => {
    if (docCategoryFilter === "all") return documents;
    const target = docCategoryFilter.toLowerCase().replace(/[\s-_]/g, "");
    return documents.filter((d: any) => {
      const cat = (d.category || "").toLowerCase().replace(/[\s-_]/g, "");
      const title = (d.title || "").toLowerCase();
      const fname = (d.original_file_name || d.file_name || d.filename || "").toLowerCase();
      if (target === "mri") {
        return isBrainMri(d);
      }
      if (target === "xray") {
        return cat === "xray" || cat === "chestxray" || cat.includes("xray") || cat.includes("cxr") || title.includes("xray") || title.includes("x-ray") || fname.includes("xray") || fname.includes("x-ray");
      }
      return cat === target || (d.category || "").toLowerCase().includes(target);
    });
  }, [documents, docCategoryFilter]);"""

if target in text:
    print("Found LF")
    text = text.replace(target, replacement)
elif target.replace("\n", "\r\n") in text:
    print("Found CRLF")
    text = text.replace(target.replace("\n", "\r\n"), replacement.replace("\n", "\r\n"))
else:
    print("Not found")

with open("clinixai-health-flow/src/routes/app.patients.$id.tsx", "w", encoding="utf-8", newline="") as f:
    f.write(text)

print("Updated app.patients.$id.tsx successfully")

