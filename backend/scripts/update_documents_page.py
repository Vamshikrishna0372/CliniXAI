with open("clinixai-health-flow/src/routes/app.documents.tsx", "r", encoding="utf-8") as f:
    text = f.read()

# 1. Update CATEGORIES and CATEGORY_LABEL
cat_old = """const CATEGORIES: MedDocument["category"][] = ["Consultation", "Diagnostic Report", "Medical Image", "Prescription", "Other"];
const CATEGORY_LABEL: Record<MedDocument["category"], string> = {
  Consultation: "Consultation", "Diagnostic Report": "Lab Report", "Medical Image": "Medical Image",
  Prescription: "Prescription", "AI Report": "AI Report", Other: "Other",
};"""

cat_new = """const CATEGORIES: MedDocument["category"][] = [
  "Brain MRI",
  "Chest X-Ray",
  "CT Scan",
  "Lab Report",
  "Prescription",
  "Consultation",
  "Other",
];
const CATEGORY_LABEL: Record<string, string> = {
  "Brain MRI": "Brain MRI",
  "Chest X-Ray": "Chest X-Ray",
  "CT Scan": "CT Scan",
  "Lab Report": "Lab Report",
  Prescription: "Prescription",
  Consultation: "Consultation",
  "Medical Image": "Medical Image",
  "Diagnostic Report": "Lab Report",
  "AI Report": "AI Report",
  Other: "Other",
};"""

text = text.replace(cat_old, cat_new)

# 2. Update patient ID resolution
pid_old = """  const patient = patients.find((p) => p.email === user?.email || p.id === user?.patientId || p.id === user?.id);
  const currentPatId = user?.patientId || (patient ? patient.id : (user?.id || ""));"""

pid_new = """  const patient = patients.find((p) => (p.email && p.email === user?.email) || p.id === user?.patientId || (p as any).userId === user?.id);
  const currentPatId = (user?.patientId && user.patientId.startsWith("PAT-"))
    ? user.patientId
    : (patient?.id && patient.id.startsWith("PAT-"))
      ? patient.id
      : "";"""

text = text.replace(pid_old, pid_new)

# 3. Update scoped documents filter (no user.id fallback)
scoped_old = """  const scoped = useMemo(
    () => (isStaffLike ? documents : documents.filter((d) => d.patientId === currentPatId || d.patientId === user?.id)),
    [documents, isStaffLike, currentPatId, user],
  );"""

scoped_new = """  const scoped = useMemo(
    () => (isStaffLike ? documents : documents.filter((d) => d.patientId === currentPatId)),
    [documents, isStaffLike, currentPatId],
  );"""

text = text.replace(scoped_old, scoped_new)

# 4. Update doUpload validation and category mapping
upload_old = """    if (isStaffLike && !uploadPatient) { toast.error("Select a patient first"); return; }
    const pid = isStaffLike ? uploadPatient : currentPatId;
    setUploading(true);
    let successCount = 0;

    for (const f of Array.from(files)) {
      try {
        const fd = new FormData();
        let backendCat: string = "Other";
        if (uploadCat === "Medical Image") backendCat = "X-Ray";
        else if (uploadCat === "Diagnostic Report") backendCat = "Lab Report";
        else if (uploadCat === "Consultation") backendCat = "Medical PDF";
        else if (uploadCat === "Prescription") backendCat = "Prescription";"""

upload_new = """    if (isStaffLike && !uploadPatient) { toast.error("Select a patient first"); return; }
    const pid = isStaffLike ? uploadPatient : currentPatId;
    if (!pid || !pid.startsWith("PAT-")) {
      toast.error("Canonical patient profile (PAT-...) required for document upload.");
      return;
    }
    setUploading(true);
    let successCount = 0;

    for (const f of Array.from(files)) {
      try {
        const fd = new FormData();
        let backendCat: string = "Other";
        if (uploadCat === "Brain MRI") backendCat = "MRI";
        else if (uploadCat === "Chest X-Ray") backendCat = "X-Ray";
        else if (uploadCat === "CT Scan") backendCat = "CT";
        else if (uploadCat === "Lab Report" || uploadCat === "Diagnostic Report") backendCat = "Lab Report";
        else if (uploadCat === "Consultation") backendCat = "Medical PDF";
        else if (uploadCat === "Prescription") backendCat = "Prescription";
        else if (uploadCat === "Medical Image") backendCat = "X-Ray";
        else backendCat = String(uploadCat);"""

text = text.replace(upload_old, upload_new)

with open("clinixai-health-flow/src/routes/app.documents.tsx", "w", encoding="utf-8", newline="") as f:
    f.write(text)

print("Updated app.documents.tsx successfully")

