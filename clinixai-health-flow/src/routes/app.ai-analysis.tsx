import { useState, useEffect } from "react";
import { createFileRoute, Link, useNavigate, Outlet, useMatch } from "@tanstack/react-router";
import { Brain, Image as ImageIcon, Sparkles, Loader2, ArrowLeft, CheckCircle2, ShieldAlert } from "lucide-react";
import { PageHeader } from "@/components/app-shell/page-header";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { FileUpload } from "@/components/dashboard/file-upload";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useClinix } from "@/lib/store/clinix-store";
import { useAuth } from "@/lib/auth-context";
import { fmtDate, type MedDocument } from "@/lib/mock/domain";

import { apiClient, getApiBaseUrl } from "@/lib/api-client";
import { toast } from "sonner";

interface AIAnalysisSearchParams {
  document_id?: string;
  documentId?: string;
  patient_id?: string;
  patientId?: string;
  appointment_id?: string;
  appointmentId?: string;
  medical_record_id?: string;
  medicalRecordId?: string;
  recordId?: string;
  record_id?: string;
  modality?: string;
}

export const Route = createFileRoute("/app/ai-analysis")({
  head: () => ({ meta: [{ title: "AI Analysis — CliniXAI" }, { name: "robots", content: "noindex" }] }),
  validateSearch: (search: Record<string, unknown>): AIAnalysisSearchParams => ({
    document_id: typeof search.document_id === "string" ? search.document_id : typeof search.documentId === "string" ? search.documentId : undefined,
    patient_id: typeof search.patient_id === "string" ? search.patient_id : typeof search.patientId === "string" ? search.patientId : undefined,
    appointment_id: typeof search.appointment_id === "string" ? search.appointment_id : typeof search.appointmentId === "string" ? search.appointmentId : undefined,
    medical_record_id: typeof search.medical_record_id === "string" ? search.medical_record_id : typeof search.medicalRecordId === "string" ? search.medicalRecordId : undefined,
    recordId: typeof search.recordId === "string" ? search.recordId : undefined,
    record_id: typeof search.record_id === "string" ? search.record_id : undefined,
    modality: typeof search.modality === "string" ? search.modality : undefined,
  }),
  component: AIAnalysisPage,
});

const STAGES = [
  "Preparing medical image",
  "Running ResNet50 model inference",
  "Computing class probabilities",
  "Generating Grad-CAM explainability overlay",
  "Persisting AI record in database",
];

function AIAnalysisPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const isChild = useMatch({ from: "/app/ai-analysis/$id", shouldThrow: false });

  useEffect(() => {
    if (user?.role === "patient" && !isChild) {
      navigate({ to: "/app/ai-reports", replace: true });
    }
  }, [user?.role, isChild, navigate]);

  if (isChild) {
    return <Outlet />;
  }

  if (user?.role === "patient") {
    return null;
  }

  return <AIAnalysisForm />;
}

function AIAnalysisForm() {
  const { user } = useAuth();
  const { patients, aiReports, documents, createAIAnalysis, completeAIAnalysis } = useClinix();
  const navigate = useNavigate();
  let routeSearch: AIAnalysisSearchParams = {};
  try {
    routeSearch = Route.useSearch();
  } catch {
    // fallback if outside router context
  }
  const searchParams = typeof window !== "undefined" ? new URLSearchParams(window.location.search) : new URLSearchParams();
  const selectedDocId = routeSearch.document_id || routeSearch.documentId || searchParams.get("document_id") || searchParams.get("documentId") || undefined;
  const targetPatientId = routeSearch.patient_id || routeSearch.patientId || searchParams.get("patient_id") || searchParams.get("patientId") || undefined;

  const isStaffLike = user?.role === "staff" || user?.role === "admin" || user?.role === "doctor";
  const patientRec = patients.find((p) => p.email === user?.email || p.id === user?.id || p.id?.startsWith("PAT-"));
  const currentPatId = targetPatientId || (patientRec ? patientRec.id : (user?.id || ""));
  
  const [patientId, setPatientId] = useState<string>(currentPatId || (isStaffLike ? (patients[0]?.id ?? "") : ""));
  const [imageType, setImageType] = useState("Brain MRI (T1-weighted contrast)");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [stage, setStage] = useState<number>(-1);

  // Existing document state when initiated from Clinical Workspace
  const [existingDoc, setExistingDoc] = useState<any>(null);
  const [docBlobUrl, setDocBlobUrl] = useState<string | null>(null);
  const [loadingDoc, setLoadingDoc] = useState<boolean>(false);
  const [docError, setDocError] = useState<string | null>(null);
  const [selectedModule, setSelectedModule] = useState<"BRAIN_MRI" | "CHEST_XRAY">("BRAIN_MRI");

  useEffect(() => {
    let cancelled = false;
    let url: string | null = null;
    if (selectedDocId) {
      setLoadingDoc(true);
      setDocError(null);
      setExistingDoc(null);
      setDocBlobUrl(null);

      apiClient.documents.getDetail(selectedDocId)
        .then(async (docData: any) => {
          if (cancelled || !docData) return;

          // Cross-patient validation: reject mismatched patient context
          if (targetPatientId && docData.patient_id && docData.patient_id !== targetPatientId) {
            setDocError(`Access Denied: Document ${selectedDocId} belongs to patient ${docData.patient_id}, not ${targetPatientId}.`);
            toast.error("Cross-patient access violation: Document mismatch.");
            return;
          }

          setExistingDoc(docData);
          if (docData.patient_id) {
            setPatientId(docData.patient_id);
          }

          const cat = String(docData.category || "").toLowerCase();
          const title = String(docData.title || "").toLowerCase();
          const mod = String(docData.modality || "").toLowerCase();
          if (
            routeSearch.modality?.toUpperCase() === "CHEST_XRAY" ||
            cat.includes("chest") ||
            cat.includes("xray") ||
            cat.includes("x-ray") ||
            title.includes("chest") ||
            title.includes("xray") ||
            mod.includes("chest") ||
            mod.includes("xray")
          ) {
            setSelectedModule("CHEST_XRAY");
          } else {
            setSelectedModule("BRAIN_MRI");
          }

          try {
            const blob = await apiClient.documents.getFileBlob(selectedDocId);
            if (!cancelled && blob) {
              url = URL.createObjectURL(blob);
              setDocBlobUrl(url);
            }
          } catch (blobErr: any) {
            console.warn("Could not load image blob preview:", blobErr);
            if (!cancelled) {
              setDocError(blobErr?.message || "Unable to load selected medical image bytes.");
            }
          }
        })
        .catch((err: any) => {
          console.error("Failed to load document:", err);
          if (!cancelled) {
            const status = err?.status || (err?.message?.includes("403") ? 403 : err?.message?.includes("404") ? 404 : 500);
            if (status === 403) {
              setDocError("You are not authorized to access this medical image.");
            } else if (status === 404) {
              setDocError("Selected medical image document not found.");
            } else {
              setDocError(err?.message || "Unable to load selected medical image.");
            }
            toast.error(err?.message || "Could not load selected medical image.");
          }
        })
        .finally(() => {
          if (!cancelled) setLoadingDoc(false);
        });
    }
    return () => {
      cancelled = true;
      if (url) URL.revokeObjectURL(url);
    };
  }, [selectedDocId, targetPatientId]);

  useEffect(() => {
    if (!patientId && patients.length > 0) {
      setPatientId(isStaffLike ? patients[0].id : currentPatId);
    }
  }, [patients, patientId, isStaffLike, currentPatId]);

  const patient = patients.find((p) => p.id === patientId);

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
  };

  // 1-Click analysis using existing patient image
  const runExistingImageAnalysis = async () => {
    if (!existingDoc?.document_id) return;
    setStage(0);

    try {
      setStage(1);
      const targetModule = selectedModule || "BRAIN_MRI";
      const isBrainModule = targetModule === "BRAIN_MRI";
      const isChestModule = targetModule === "CHEST_XRAY";

      const cat = String(existingDoc.category || "").toLowerCase();
      const mod = String(existingDoc.modality || "").toLowerCase();
      const title = String(existingDoc.title || "").toLowerCase();

      // Ensure document metadata in DB is correctly aligned with clinical module choice
      const needsClassification =
        cat === "other" ||
        mod === "other" ||
        (isBrainModule && !cat.includes("mri") && !mod.includes("mri") && !title.includes("mri") && !title.includes("brain")) ||
        (isChestModule && !cat.includes("xray") && !cat.includes("x-ray") && !mod.includes("chest") && !mod.includes("xray") && !title.includes("chest") && !title.includes("xray"));

      if (needsClassification) {
        const newCategory = isBrainModule ? "MRI" : "X-Ray";
        const newModality = isBrainModule ? "Brain MRI" : "Chest X-Ray";
        try {
          const updatedDoc = await apiClient.documents.updateMetadata(existingDoc.document_id, {
            category: newCategory,
            modality: newModality,
          });
          if (updatedDoc) {
            setExistingDoc((prev: any) => ({ ...prev, ...updatedDoc, category: newCategory, modality: newModality }));
          }
        } catch (updateErr) {
          console.warn("Could not synchronize document metadata before analysis:", updateErr);
        }
      }

      setStage(2);
      const inferResult = await apiClient.ai.createAnalysis({
        document_id: existingDoc.document_id,
        patient_id: existingDoc.patient_id,
        appointment_id: existingDoc.appointment_id || undefined,
        medical_record_id: existingDoc.medical_record_id || undefined,
        analysis_type: targetModule,
        consultation_id: existingDoc.consultation_id || undefined,
      });
      setStage(3);

      setStage(4);
      setStage(-1);
      toast.success("AI model inference completed successfully!");
      const targetId = inferResult?.data?.analysis_id || inferResult?.analysis_id;
      if (targetId) {
        navigate({ to: "/app/ai-analysis/$id", params: { id: targetId } });
      } else {
        toast.error("Could not resolve created AI analysis ID.");
      }
    } catch (err: any) {
      setStage(-1);
      toast.error(`AI analysis failed: ${err?.message || "Internal model error"}`);
    }
  };

  // Direct upload flow
  const runDirectUpload = async () => {
    if (!patientId) {
      toast.error("Please select a patient first.");
      return;
    }
    if (!selectedFile) {
      toast.error("Please upload a medical image file to run AI analysis.");
      return;
    }

    const report = createAIAnalysis({ patientId, imageType });
    setStage(0);

    try {
      setStage(1);
      const normType = imageType.toLowerCase();
      let moduleType = "BRAIN_MRI";
      if (normType.includes("chest") || normType.includes("xray")) moduleType = "CHEST_XRAY";
      else if (normType.includes("skin") || normType.includes("dermo")) moduleType = "SKIN_DERMOSCOPY";
      else if (normType.includes("retina") || normType.includes("fundus")) moduleType = "RETINAL_FUNDUS";
      else if (normType.includes("bone")) moduleType = "BONE_XRAY";

      setStage(2);
      const inferResult = await apiClient.ai.directInfer(selectedFile, moduleType, patientId);
      setStage(3);

      const targetId = inferResult.analysis_id || report.id;

      completeAIAnalysis(
        targetId,
        {
          prediction: inferResult.predicted_class,
          confidence: Number(inferResult.confidence.toFixed(2)),
          explanation: `Model: ${inferResult.display_name} (v${inferResult.model_version}, ${inferResult.architecture}). Top prediction: ${inferResult.predicted_class} with ${Math.round(inferResult.confidence * 100)}% confidence.`,
          gradcam: inferResult.gradcam_available ? "available" : "unavailable",
          gradcamUrl: inferResult.gradcam_b64 || undefined,
          imageUrl: URL.createObjectURL(selectedFile),
          probabilities: inferResult.probabilities,
        },
        report.id
      );

      setStage(-1);
      toast.success("AI analysis completed successfully!");
      navigate({ to: "/app/ai-analysis/$id", params: { id: targetId } });
    } catch (err: any) {
      setStage(-1);
      toast.error(`AI analysis failed: ${err?.message || "Internal model error"}`);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="AI Clinical Decision Support"
        description="Deep learning medical imaging evaluation with ResNet50 transfer learning and Grad-CAM explainability."
        status={{ label: "Decision Support", tone: "info" }}
      />

      <Card className="border-warning/30 bg-warning/5">
        <CardContent className="p-4 text-sm flex items-start gap-2">
          <ShieldAlert className="h-4 w-4 mt-0.5 text-warning shrink-0" />
          <p className="text-muted-foreground">
            <span className="font-medium text-warning-foreground">Clinical Safety Notice: </span>
            CliniXAI AI results are clinical decision-support information and do not replace professional medical diagnosis. The attending clinician must interpret findings in conjunction with clinical examination and patient history.
          </p>
        </CardContent>
      </Card>

      {/* Controlled Error Display if document resolution fails */}
      {docError ? (
        <Card className="border-destructive/40 bg-destructive/5 shadow-sm">
          <CardHeader>
            <CardTitle className="text-base text-destructive flex items-center gap-2">
              <ShieldAlert className="h-5 w-5 text-destructive" />
              Document Access & Clinical Validation Error
            </CardTitle>
            <CardDescription className="text-xs">
              The requested medical scan could not be loaded into AI Clinical Decision Support.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="rounded-lg border border-destructive/20 bg-background/80 p-4 text-xs font-medium text-destructive space-y-1">
              <p>{docError}</p>
              <p className="text-[11px] text-muted-foreground mt-1">
                Please verify that the document ID belongs to this patient and that you have an established clinical care relationship.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Button asChild size="sm" variant="outline" className="text-xs">
                <Link to="/app/patients/$id" params={{ id: targetPatientId || "PAT-ONE-001" }}>
                  <ArrowLeft className="mr-1.5 h-3.5 w-3.5" /> Return to Patient Workspace
                </Link>
              </Button>
              <Button size="sm" variant="ghost" className="text-xs" onClick={() => navigate({ to: "/app/ai-analysis" })}>
                Reset AI Analysis
              </Button>
            </div>
          </CardContent>
        </Card>
      ) : selectedDocId && existingDoc ? (
        <Card data-testid="selected-doc-mri-card" className="border-primary/40 shadow-sm">
          <CardHeader>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <CardTitle className="text-base flex items-center gap-2">
                  <Brain className="h-5 w-5 text-primary" />
                  Selected Patient Medical Image for AI Analysis
                </CardTitle>
                <CardDescription className="text-xs mt-1">
                  Reusing securely stored clinical image from patient workspace. No re-upload required.
                </CardDescription>
              </div>
              <Badge variant="outline" className="font-mono text-xs">
                {existingDoc.document_id}
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-3">
                <div className="rounded-lg border border-border bg-muted/30 p-3 text-xs space-y-1.5">
                  <p>
                    <span className="text-muted-foreground font-medium">Patient: </span>
                    <span className="font-semibold text-foreground">{patient?.firstName || "Patient"} {patient?.lastName || ""} ({patientId})</span>
                  </p>
                  <p>
                    <span className="text-muted-foreground font-medium">Selected Medical Image: </span>
                    <span className="font-semibold text-foreground">{existingDoc.title || existingDoc.original_file_name}</span>
                  </p>
                  <p>
                    <span className="text-muted-foreground font-medium">Document ID: </span>
                    <span className="font-mono text-foreground font-semibold">{existingDoc.document_id}</span>
                  </p>
                  <p>
                    <span className="text-muted-foreground font-medium">File: </span>
                    <span className="font-mono text-muted-foreground">{existingDoc.original_file_name || existingDoc.file_name}</span>
                  </p>
                  <div className="flex items-center gap-1.5 pt-0.5">
                    <span className="text-muted-foreground font-medium">Modality / Category: </span>
                    <Badge variant={String(existingDoc.category || "").toLowerCase() === "other" ? "outline" : "secondary"} className="text-[10px] uppercase font-semibold">
                      {existingDoc.modality || existingDoc.category || "MRI"}
                    </Badge>
                  </div>
                  <div className="space-y-1.5 pt-1 border-t border-border/50">
                    <Label className="text-xs font-semibold text-foreground">Target AI Module / Modality</Label>
                    <Select value={selectedModule} onValueChange={(val: "BRAIN_MRI" | "CHEST_XRAY") => setSelectedModule(val)}>
                      <SelectTrigger className="h-8 text-xs font-medium">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="BRAIN_MRI">Brain MRI Tumor Classification (ResNet50)</SelectItem>
                        <SelectItem value="CHEST_XRAY">Chest X-Ray Pneumonia Classification (ResNet50)</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  {String(existingDoc.category || "").toLowerCase() === "other" && (
                    <div className="rounded-md border border-amber-500/25 bg-amber-500/10 p-2 text-xs text-amber-800 dark:text-amber-300">
                      <span className="font-semibold">Notice: </span>
                      Document was uploaded with category OTHER. Running analysis will automatically confirm and classify this image as {selectedModule === "BRAIN_MRI" ? "Brain MRI" : "Chest X-Ray"}.
                    </div>
                  )}
                  <p>
                    <span className="text-muted-foreground font-medium">Model: </span>
                    <span className="font-medium text-foreground">ResNet50 (v1.0.0)</span>
                  </p>
                  {existingDoc.created_at && (
                    <p>
                      <span className="text-muted-foreground">Uploaded: </span>
                      <span>{String(existingDoc.created_at).slice(0, 10)}</span>
                    </p>
                  )}
                </div>

                <Button id="btn-run-existing-analysis" data-testid="btn-run-existing-analysis" className="w-full font-semibold" onClick={runExistingImageAnalysis} disabled={stage >= 0}>
                  {stage >= 0 ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" /> {STAGES[stage]}…
                    </>
                  ) : (
                    <>
                      <Sparkles className="mr-2 h-4 w-4" /> Run AI Analysis on Selected Image
                    </>
                  )}
                </Button>

                {stage >= 0 && (
                  <div className="space-y-1">
                    <div className="h-2 w-full overflow-hidden rounded-full bg-muted" role="progressbar">
                      <div className="h-full bg-primary transition-all duration-300" style={{ width: `${((stage + 1) / STAGES.length) * 100}%` }} />
                    </div>
                    <p className="text-[11px] text-muted-foreground text-center">{STAGES[stage]}</p>
                  </div>
                )}
              </div>

              <div className="rounded-xl border border-border bg-black/5 dark:bg-black/30 p-2 flex items-center justify-center min-h-[200px]">
                {loadingDoc ? (
                  <div className="flex flex-col items-center justify-center p-6 text-center text-xs text-muted-foreground">
                    <Loader2 className="h-6 w-6 animate-spin mb-2" />
                    <span>Loading selected MRI...</span>
                  </div>
                ) : docBlobUrl ? (
                  <img
                    src={docBlobUrl}
                    data-testid="selected-mri-image"
                    alt={existingDoc.title || "Patient medical scan"}
                    className="max-h-56 w-auto object-contain rounded-lg shadow-sm"
                  />
                ) : (
                  <div className="flex flex-col items-center justify-center p-6 text-center text-xs text-muted-foreground">
                    <ShieldAlert className="h-6 w-6 text-muted-foreground mb-1" />
                    <span>Medical scan preview unavailable</span>
                  </div>
                )}
              </div>
            </div>

            <div className="pt-2 flex items-center justify-between border-t border-border/40 text-xs text-muted-foreground">
              <span>Need to upload a different image?</span>
              <Button variant="ghost" size="sm" className="text-xs h-7" onClick={() => navigate({ to: "/app/ai-analysis" })}>
                Upload New Image
              </Button>
            </div>
          </CardContent>
        </Card>
      ) : (
        /* Manual selection & upload flow */
        <div className="grid gap-6 lg:grid-cols-[1fr_1fr]">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Select Input Image</CardTitle>
              <CardDescription>Select patient and upload medical scan for stateless decision support.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label htmlFor="ai-patient">Patient</Label>
                <select id="ai-patient" className="mt-1 h-10 w-full rounded-md border border-input bg-background px-2 text-sm" value={patientId} onChange={(e) => setPatientId(e.target.value)}>
                  {patients.map((p) => <option key={p.id} value={p.id}>{p.firstName} {p.lastName} — {p.id}</option>)}
                </select>
              </div>
              <div>
                <Label htmlFor="ai-type">Modality / Image Type</Label>
                <Input id="ai-type" value={imageType} onChange={(e) => setImageType(e.target.value)} />
              </div>
              <div>
                <Label>Upload Image File</Label>
                <FileUpload accept="image/*,.dcm" onFileSelect={(file) => setSelectedFile(file)} />
              </div>
              <Button className="w-full" onClick={runDirectUpload} disabled={stage >= 0 || !patientId}>
                {stage >= 0 ? <><Loader2 className="h-4 w-4 animate-spin mr-2" /> {STAGES[stage]}…</> : <><Sparkles className="h-4 w-4 mr-2" /> Run AI Analysis</>}
              </Button>
              {stage >= 0 && (
                <div className="h-2 w-full overflow-hidden rounded-full bg-muted" role="progressbar" aria-valuenow={Math.round(((stage + 1) / STAGES.length) * 100)} aria-valuemin={0} aria-valuemax={100}>
                  <div className="h-full bg-primary transition-all" style={{ width: `${((stage + 1) / STAGES.length) * 100}%` }} />
                </div>
              )}
            </CardContent>
          </Card>

          <div className="space-y-4">
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
          </div>
        </div>
      )}

      <Card>
        <CardHeader><CardTitle className="text-base flex items-center gap-2"><Brain className="h-4 w-4" /> Recent AI Analyses</CardTitle></CardHeader>
        <CardContent className="grid gap-2">
          {aiReports.length === 0 && <p className="text-sm text-muted-foreground">No AI analyses yet.</p>}
          {aiReports.slice(0, 12).map((r) => {
            const p = patients.find((x) => x.id === r.patientId);
            return (
              <Link key={r.id} to="/app/ai-analysis/$id" params={{ id: r.id }} className="flex min-w-0 flex-wrap items-center justify-between gap-2 rounded-lg border border-border p-3 hover:bg-muted/50">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">{r.imageType} — {p?.firstName} {p?.lastName}</p>
                  <p className="text-xs text-muted-foreground">{r.prediction ?? "Processing"} · {r.confidence ? `${Math.round(r.confidence * 100)}%` : "—"} · {r.date}</p>
                </div>
                <Badge variant="outline">{r.status}</Badge>
              </Link>
            );
          })}
        </CardContent>
      </Card>
    </div>
  );
}
