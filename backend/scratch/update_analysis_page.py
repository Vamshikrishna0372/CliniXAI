with open('clinixai-health-flow/src/routes/app.ai-analysis.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update imports
target_import = 'import { useAuth } from "@/lib/auth-context";'
replacement_import = 'import { useAuth } from "@/lib/auth-context";\nimport { fmtDate, type MedDocument } from "@/lib/mock/domain";'

# 2. Update useClinix destructuring
target_destruct = 'const { patients, aiReports, createAIAnalysis, completeAIAnalysis } = useClinix();'
replacement_destruct = 'const { patients, aiReports, documents, createAIAnalysis, completeAIAnalysis } = useClinix();'

# 3. Update directInfer call
target_direct = 'const inferResult = await apiClient.ai.directInfer(selectedFile, moduleType);'
replacement_direct = 'const inferResult = await apiClient.ai.directInfer(selectedFile, moduleType, patientId);'

# 4. Filter images for current patient and add renderImageProvenanceCard
target_existing = '  const patient = patients.find((p) => p.id === patientId);\n  const existing = aiReports.filter((r) => r.patientId === patientId);'

replacement_existing = """  const patient = patients.find((p) => p.id === patientId);

  // Filter medical imaging documents for the selected patient
  const patientImages = documents.filter((d) => {
    if (d.patientId !== patientId) return false;
    const cat = (d.category || "").toLowerCase();
    const name = (d.name || "").toLowerCase();
    const ft = (d.fileType || "").toLowerCase();
    return (
      cat.includes("mri") ||
      cat.includes("x-ray") ||
      cat.includes("xray") ||
      cat.includes("ct") ||
      cat.includes("image") ||
      name.includes("mri") ||
      name.includes("x-ray") ||
      name.includes("scan") ||
      ft === "png" ||
      ft === "jpg" ||
      ft === "dicom"
    );
  });

  const patientUploadedImages = patientImages.filter((d) => (d.uploaderRole || d.uploadedBy)?.toLowerCase() === "patient");
  const doctorUploadedImages = patientImages.filter((d) => (d.uploaderRole || d.uploadedBy)?.toLowerCase() === "doctor");
  const staffUploadedImages = patientImages.filter((d) => (d.uploaderRole || d.uploadedBy)?.toLowerCase() === "staff");

  const renderImageProvenanceCard = (doc: MedDocument) => {
    const roleCapitalized = doc.uploaderRole
      ? doc.uploaderRole.charAt(0).toUpperCase() + doc.uploaderRole.slice(1)
      : doc.uploadedBy
      ? doc.uploadedBy.charAt(0).toUpperCase() + doc.uploadedBy.slice(1)
      : "Unknown";

    const uploaderDisplayName = doc.uploaderName || (roleCapitalized === "Doctor" ? "Doctor" : roleCapitalized === "Patient" ? `${patient?.firstName} ${patient?.lastName}` : "Hospital Staff");
    const modalityDisplay = doc.modality || (doc.category.toLowerCase().includes("mri") ? "Brain MRI" : doc.category.toLowerCase().includes("x-ray") ? "Chest X-Ray" : doc.category);
    const hasAnalysis = Boolean(doc.aiAnalysisId);
    const isSelected = selectedDocId === doc.id;

    return (
      <div
        key={doc.id}
        data-testid={`image-card-${doc.id}`}
        className={`rounded-lg border p-3.5 space-y-2.5 transition-colors ${
          isSelected ? "border-primary bg-primary/5" : "border-border hover:bg-muted/40"
        }`}
      >
        <div className="flex items-start justify-between gap-2">
          <div>
            <h4 className="text-sm font-semibold text-foreground flex items-center gap-1.5">
              <Brain className="h-4 w-4 text-primary" />
              {modalityDisplay === "Brain MRI" ? "Brain MRI Tumor Classification" : modalityDisplay === "Chest X-Ray" ? "Chest X-Ray Pneumonia Evaluation" : doc.name}
            </h4>
            <p className="text-xs text-muted-foreground mt-0.5 truncate">{doc.name}</p>
          </div>
          <Badge variant={hasAnalysis ? "default" : "outline"} className={hasAnalysis ? "bg-emerald-600 hover:bg-emerald-700 text-white" : ""}>
            {hasAnalysis ? "Analysis completed" : "Not analyzed"}
          </Badge>
        </div>

        <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-muted-foreground pt-1 border-t border-border/40">
          <div>
            <span className="font-medium text-foreground">Patient: </span>
            <span>{patient?.firstName} {patient?.lastName}</span>
          </div>
          <div>
            <span className="font-medium text-foreground">Uploaded by: </span>
            <span>{uploaderDisplayName}</span>
          </div>
          <div>
            <span className="font-medium text-foreground">Uploader role: </span>
            <span>{roleCapitalized}</span>
          </div>
          <div>
            <span className="font-medium text-foreground">Uploaded: </span>
            <span>{fmtDate(doc.date)}</span>
          </div>
          <div>
            <span className="font-medium text-foreground">Modality: </span>
            <span>{modalityDisplay}</span>
          </div>
          <div>
            <span className="font-medium text-foreground">AI status: </span>
            <span>{hasAnalysis ? "Analysis completed" : "Pending analysis"}</span>
          </div>
        </div>

        <div className="flex items-center justify-end gap-2 pt-1">
          {hasAnalysis ? (
            <Button asChild size="sm" variant="default" className="text-xs h-7">
              <Link to="/app/ai-analysis/$id" params={{ id: doc.aiAnalysisId! }}>
                Open
              </Link>
            </Button>
          ) : (
            <Button
              size="sm"
              variant="outline"
              className="text-xs h-7 gap-1"
              onClick={() => {
                navigate({
                  to: "/app/ai-analysis",
                  search: {
                    document_id: doc.id,
                    patient_id: patientId,
                  },
                });
              }}
            >
              <Sparkles className="h-3.5 w-3.5 mr-1" />
              Analyze with AI
            </Button>
          )}
        </div>
      </div>
    );
  };"""

# 5. Replace the single hardcoded Patient-Uploaded Images Card
target_card = """          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2"><ImageIcon className="h-4 w-4" /> Patient-Uploaded Images</CardTitle>
              <CardDescription>{patient?.firstName} {patient?.lastName}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              {existing.length === 0 ? (
                <p className="text-sm text-muted-foreground">No images available for this patient.</p>
              ) : existing.map((r) => (
                <div key={r.id} className="flex min-w-0 flex-wrap items-center justify-between gap-2 rounded-lg border border-border p-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">{r.imageType}</p>
                    <div className="flex items-center gap-1 text-xs text-muted-foreground"><span>{r.date}</span>·<Badge variant="outline" className="ml-1">{r.status}</Badge></div>
                  </div>
                  <div className="flex gap-2">
                    <Button asChild size="sm" variant="outline"><Link to="/app/ai-analysis/$id" params={{ id: r.id }}>Open</Link></Button>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>"""

replacement_card = """          <div className="space-y-4">
            {patientUploadedImages.length === 0 && doctorUploadedImages.length === 0 && staffUploadedImages.length === 0 ? (
              <Card>
                <CardHeader>
                  <CardTitle className="text-base flex items-center gap-2"><ImageIcon className="h-4 w-4" /> Medical Images</CardTitle>
                  <CardDescription>{patient?.firstName} {patient?.lastName}</CardDescription>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground">No medical images available for this patient.</p>
                </CardContent>
              </Card>
            ) : (
              <>
                {/* Patient-Uploaded Images */}
                {patientUploadedImages.length > 0 && (
                  <Card data-testid="patient-uploaded-images-card">
                    <CardHeader>
                      <CardTitle className="text-base flex items-center gap-2">
                        <ImageIcon className="h-4 w-4 text-primary" /> Patient-Uploaded Images
                      </CardTitle>
                      <CardDescription>{patient?.firstName} {patient?.lastName} · Uploaded by Patient</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      {patientUploadedImages.map((doc) => renderImageProvenanceCard(doc))}
                    </CardContent>
                  </Card>
                )}

                {/* Doctor-Uploaded Images */}
                {doctorUploadedImages.length > 0 && (
                  <Card data-testid="doctor-uploaded-images-card">
                    <CardHeader>
                      <CardTitle className="text-base flex items-center gap-2">
                        <ImageIcon className="h-4 w-4 text-blue-600" /> Doctor-Uploaded Images
                      </CardTitle>
                      <CardDescription>{patient?.firstName} {patient?.lastName} · Uploaded by Clinician</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      {doctorUploadedImages.map((doc) => renderImageProvenanceCard(doc))}
                    </CardContent>
                  </Card>
                )}

                {/* Staff-Uploaded Images */}
                {staffUploadedImages.length > 0 && (
                  <Card data-testid="staff-uploaded-images-card">
                    <CardHeader>
                      <CardTitle className="text-base flex items-center gap-2">
                        <ImageIcon className="h-4 w-4 text-emerald-600" /> Staff-Uploaded Images
                      </CardTitle>
                      <CardDescription>{patient?.firstName} {patient?.lastName} · Uploaded by Hospital Staff</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      {staffUploadedImages.map((doc) => renderImageProvenanceCard(doc))}
                    </CardContent>
                  </Card>
                )}
              </>
            )}
          </div>"""

content_norm = content.replace("\r\n", "\n")

for name, t, r in [
    ("import", target_import, replacement_import),
    ("destruct", target_destruct, replacement_destruct),
    ("direct", target_direct, replacement_direct),
    ("existing", target_existing, replacement_existing),
    ("card", target_card, replacement_card),
]:
    t_norm = t.replace("\r\n", "\n")
    r_norm = r.replace("\r\n", "\n")
    if t_norm in content_norm:
        content_norm = content_norm.replace(t_norm, r_norm)
        print(f"Replaced {name} successfully")
    else:
        print(f"Failed to find {name}")

if "\r\n" in content:
    content_norm = content_norm.replace("\n", "\r\n")

with open('clinixai-health-flow/src/routes/app.ai-analysis.tsx', 'w', encoding='utf-8') as f:
    f.write(content_norm)
