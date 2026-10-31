import { useState, useEffect } from "react";
import { createFileRoute, Link, useParams, useNavigate } from "@tanstack/react-router";
import { ArrowLeft, Brain, ShieldAlert, CheckCircle2, XCircle, HelpCircle, Cpu, Send, Loader2 } from "lucide-react";
import { PageHeader } from "@/components/app-shell/page-header";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { toast } from "sonner";
import { fmtDate, todayIso } from "@/lib/mock/domain";
import { useClinix } from "@/lib/store/clinix-store";
import { useAuth } from "@/lib/auth-context";
import { getAIModel, modelForImageType } from "@/lib/mock/ai-models";
import { MedicalImageViewer } from "@/components/domain/medical-image-viewer";
import { ConfidenceBreakdown } from "@/components/domain/confidence-breakdown";
import { apiClient } from "@/lib/api-client";

export const Route = createFileRoute("/app/ai-analysis/$id")({
  head: () => ({ meta: [{ title: "AI Analysis — CliniXAI" }, { name: "robots", content: "noindex" }] }),
  component: AIResultPage,
});

const DECISIONS = [
  { value: "accepted" as const, label: "Accepted", icon: CheckCircle2 },
  { value: "rejected" as const, label: "Rejected", icon: XCircle },
  { value: "not-relevant" as const, label: "Not clinically relevant", icon: HelpCircle },
];

function mapBackendToReport(r: any) {
  const modId = String(r.model?.module_id || r.model?.name || "").toLowerCase();
  const modelId = modId.includes("brain") ? "brain-mri" : modId.includes("chest") ? "chest-xray" : undefined;
  const isRev = String(r.status || "").toLowerCase() === "reviewed";
  const isReleased = Boolean(r.is_released_to_patient);
  return {
    id: r.analysis_id,
    patientId: r.patient_id,
    doctorId: r.doctor_id || "",
    date: r.created_at ? String(r.created_at).split("T")[0] : todayIso(),
    modelId: modelId,
    modelName: r.model?.name,
    modelArchitecture: r.model?.architecture || "ResNet50",
    modelVersion: r.model?.version || "1.0.0",
    imageType: modId.includes("chest") ? "Chest X-Ray" : modId.includes("brain") ? "Brain MRI" : (r.model?.name || "Medical Image"),
    backendStatus: r.status,
    isReleasedToPatient: isReleased,
    status: isRev ? (isReleased ? "Reviewed & Released" : "Reviewed (Unreleased)") : "Awaiting Doctor Review",
    prediction: r.prediction?.predicted_class || "Normal",
    confidence: typeof r.prediction?.confidence === "number" ? (r.prediction.confidence <= 1 ? r.prediction.confidence : r.prediction.confidence / 100) : 0.95,
    lowConfidence: Boolean(r.prediction?.low_confidence),
    explanation: r.prediction?.clinical_summary || "Real AI analysis completed.",
    gradcam: r.explainability?.artifact_storage_key || r.gradcam_path ? "available" : "unavailable",
    probabilities: r.prediction?.probabilities || (r.prediction?.class_probabilities ? Object.entries(r.prediction.class_probabilities).map(([label, probability]) => ({ label, probability: Number(probability) })) : []),
    doctorDecision: r.doctor_review?.decision,
    doctorNote: r.doctor_review?.clinical_interpretation,
    reviewedOn: r.doctor_review?.reviewed_at || r.released_at,
    medicalRecordId: r.medical_record_id,
    documentId: r.document_id || (r.medical_record_id?.startsWith("DOC-") ? r.medical_record_id : undefined),
    imageUrl: r.input?.image_url || r.image_url || undefined,
  };
}

function AIResultPage() {
  const { id } = useParams({ from: "/app/ai-analysis/$id" });
  const { getAIReport, getPatient, reviewAIReport } = useClinix();
  const storeReport = getAIReport(id);
  const storePatient = storeReport ? getPatient(storeReport.patientId) : undefined;
  const [remoteReport, setRemoteReport] = useState<any>(null);
  const [remotePatient, setRemotePatient] = useState<any>(null);
  const [loadingRemote, setLoadingRemote] = useState(false);
  const [showReleaseModal, setShowReleaseModal] = useState(false);
  const [isSavingReview, setIsSavingReview] = useState(false);
  const [isReleasing, setIsReleasing] = useState(false);

  useEffect(() => {
    if (id) {
      setLoadingRemote(true);
      apiClient.ai.getDetail(id)
        .then(async (res) => {
          const r = res?.data || res;
          if (r) {
            setRemoteReport(mapBackendToReport(r));
            if (r.patient_id) {
              const pRes = await apiClient.patients.getDetail(r.patient_id).catch(() => null);
              const p = pRes?.data || pRes;
              if (p) {
                setRemotePatient({
                  id: p.patient_id,
                  firstName: p.first_name || "Patient",
                  lastName: p.last_name || "",
                });
              } else {
                setRemotePatient({ id: r.patient_id, firstName: "Patient", lastName: r.patient_id });
              }
            }
          }
        })
        .catch((err) => console.error("Failed to load remote AI report:", err))
        .finally(() => setLoadingRemote(false));
    }
  }, [id]);

  const { user } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (user?.role === "patient") {
      navigate({ to: "/app/ai-reports/$id", params: { id }, replace: true });
    }
  }, [user?.role, id, navigate]);

  const activeReport = remoteReport || storeReport;
  const activePatient = remotePatient || storePatient;
  const [notes, setNotes] = useState(activeReport?.doctorNote ?? "");
  const [decision, setDecision] = useState<"accepted" | "rejected" | "not-relevant" | "">(activeReport?.reviewDecision ?? "");
  const [gradcamBlobUrl, setGradcamBlobUrl] = useState<string | undefined>(undefined);
  const [originalBlobUrl, setOriginalBlobUrl] = useState<string | undefined>(undefined);

  useEffect(() => {
    if (activeReport?.doctorNote && !notes) {
      setNotes(activeReport.doctorNote);
    }
    if (activeReport?.doctorDecision && !decision) {
      const d = String(activeReport.doctorDecision).toLowerCase();
      if (d.includes("accepted")) setDecision("accepted");
      else if (d.includes("rejected")) setDecision("rejected");
      else setDecision("not-relevant");
    }
  }, [activeReport?.doctorNote, activeReport?.doctorDecision]);

  const model = getAIModel(activeReport?.modelId) ?? modelForImageType(activeReport?.imageType);
  const heatmapAvailable = activeReport?.gradcam ? activeReport.gradcam === "available" : model?.gradcam === "enabled";

  // Authenticated binary Grad-CAM and Original Image retrieval (Bearer header, NO JWT in URL query parameters)
  useEffect(() => {
    let currentGradcamUrl: string | undefined;
    let currentOriginalUrl: string | undefined;
    let isCancelled = false;

    if (heatmapAvailable && activeReport?.id && (activeReport.id.startsWith("AI-") || activeReport.id.startsWith("ANA-"))) {
      apiClient.ai.getGradcamBlob(activeReport.id)
        .then((blob) => {
          if (!isCancelled && blob) {
            currentGradcamUrl = URL.createObjectURL(blob);
            setGradcamBlobUrl(currentGradcamUrl);
          }
        })
        .catch((err) => {
          console.error("Authenticated Grad-CAM fetch error:", err);
          if (!isCancelled) {
            setGradcamBlobUrl(undefined);
          }
        });
    }

    const recId = activeReport?.medicalRecordId;
    const docId = (activeReport as any)?.documentId || (activeReport as any)?.document_id || (recId?.startsWith("DOC-") ? recId : undefined);

    // Stream original image via authenticated endpoint with fallback to document/record blob
    if (activeReport?.id) {
      apiClient.ai.getOriginalImageBlob(activeReport.id)
        .then((blob) => {
          if (!isCancelled && blob) {
            currentOriginalUrl = URL.createObjectURL(blob);
            setOriginalBlobUrl(currentOriginalUrl);
          }
        })
        .catch(() => {
          if (docId) {
            apiClient.documents.getFileBlob(docId)
              .then((blob) => {
                if (!isCancelled && blob) {
                  currentOriginalUrl = URL.createObjectURL(blob);
                  setOriginalBlobUrl(currentOriginalUrl);
                }
              })
              .catch(() => {
                if (!isCancelled) setOriginalBlobUrl(undefined);
              });
          } else if (recId) {
            apiClient.medicalRecords.getFileBlob(recId)
              .then((blob) => {
                if (!isCancelled && blob) {
                  currentOriginalUrl = URL.createObjectURL(blob);
                  setOriginalBlobUrl(currentOriginalUrl);
                }
              })
              .catch(() => {
                if (!isCancelled) setOriginalBlobUrl(undefined);
              });
          } else {
            if (!isCancelled) setOriginalBlobUrl(undefined);
          }
        });
    }

    return () => {
      isCancelled = true;
      if (currentGradcamUrl) {
        URL.revokeObjectURL(currentGradcamUrl);
      }
      if (currentOriginalUrl) {
        URL.revokeObjectURL(currentOriginalUrl);
      }
    };
  }, [activeReport?.id, activeReport?.medicalRecordId, heatmapAvailable]);

  const gradcamUrl = gradcamBlobUrl || activeReport?.gradcamUrl;
  const originalUrl = originalBlobUrl || activeReport?.imageUrl;

  if (user?.role === "patient") {
    return null;
  }

  if (loadingRemote) {
    return (
      <div className="space-y-4">
        <Button asChild variant="ghost" size="sm"><Link to="/app/ai-analysis"><ArrowLeft className="h-4 w-4" /> Back</Link></Button>
        <Card><CardContent className="p-8 text-center text-muted-foreground">Loading analysis from backend...</CardContent></Card>
      </div>
    );
  }

  if (!activeReport || !activePatient) {
    return (
      <div className="space-y-4">
        <Button asChild variant="ghost" size="sm"><Link to="/app/ai-analysis"><ArrowLeft className="h-4 w-4" /> Back</Link></Button>
        <Card><CardContent className="p-8 text-center text-muted-foreground">Analysis not found.</CardContent></Card>
      </div>
    );
  }

  // Save clinical review without releasing (status = reviewed, is_released_to_patient = false)
  const handleSaveReview = async () => {
    if (!decision) {
      toast.error("Please select a review decision first.");
      return;
    }
    if (!notes || notes.trim().length < 5) {
      toast.error("Please enter a clinical assessment (at least 5 characters).");
      return;
    }
    setIsSavingReview(true);
    try {
      const mappedDecision = decision === "accepted" ? "accepted" : decision === "rejected" ? "rejected" : "not_clinically_relevant";
      const revRes = await apiClient.ai.review(activeReport.id, {
        decision: mappedDecision,
        clinical_interpretation: notes,
        release_to_patient: false,
      });
      const updatedData = revRes?.data || revRes;
      if (updatedData && (updatedData.status || updatedData.analysis_id)) {
        setRemoteReport(mapBackendToReport(updatedData));
      } else {
        const freshRes = await apiClient.ai.getDetail(activeReport.id);
        const freshData = freshRes?.data || freshRes;
        if (freshData) {
          setRemoteReport(mapBackendToReport(freshData));
        }
      }
      reviewAIReport(activeReport.id, decision, notes);
      toast.success("Doctor clinical review saved successfully.");
    } catch (err: any) {
      toast.error(err.message || "Failed to save doctor review.");
    } finally {
      setIsSavingReview(false);
    }
  };

  // Explicit Release to Patient after confirmation
  const handleConfirmRelease = async () => {
    setIsReleasing(true);
    try {
      const relRes = await apiClient.ai.release(activeReport.id);
      const updatedData = relRes?.data || relRes;
      if (updatedData && (updatedData.status || updatedData.analysis_id)) {
        setRemoteReport(mapBackendToReport(updatedData));
      } else {
        const freshRes = await apiClient.ai.getDetail(activeReport.id);
        const freshData = freshRes?.data || freshRes;
        if (freshData) {
          setRemoteReport(mapBackendToReport(freshData));
        }
      }
      setShowReleaseModal(false);
      toast.success("AI analysis successfully released to patient.");
    } catch (err: any) {
      toast.error(err.message || "Failed to release AI analysis to patient.");
    } finally {
      setIsReleasing(false);
    }
  };

  // Fast-track unified review and release (backward compatibility)
  const submit = async () => {
    if (!decision) {
      toast.error("Select a review decision first.");
      return;
    }
    try {
      const mappedDecision = decision === "accepted" ? "accepted" : decision === "rejected" ? "rejected" : "not_clinically_relevant";
      const revRes = await apiClient.ai.review(activeReport.id, {
        decision: mappedDecision,
        clinical_interpretation: notes || "Clinician review and evaluation recorded.",
        release_to_patient: true,
      });
      if (revRes) {
        const freshRes = await apiClient.ai.getDetail(activeReport.id);
        const freshData = freshRes?.data || freshRes;
        if (freshData) {
          setRemoteReport(mapBackendToReport(freshData));
        }
      }
      reviewAIReport(activeReport.id, decision, notes);
      toast.success("Doctor review saved and released to patient.");
    } catch (err: any) {
      toast.error(err.message || "Failed to save doctor review.");
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title={`AI analysis — ${activeReport.imageType}`}
        description={`${activeReport.id} · ${fmtDate(activeReport.date)} · ${activePatient.firstName} ${activePatient.lastName} (${activePatient.id})`}
        status={{ label: activeReport.status, tone: activeReport.isReleasedToPatient ? "success" : "info" }}
        actions={<Button asChild variant="outline" size="sm"><Link to="/app/ai-analysis"><ArrowLeft className="h-4 w-4" /> All analyses</Link></Button>}
      />

      {/* Low-confidence warning if flagged by backend model */}
      {activeReport.lowConfidence && (
        <Alert variant="destructive" className="border-warning/50 bg-warning/10 text-warning-foreground" data-testid="low-confidence-alert">
          <ShieldAlert className="h-4 w-4 text-warning" />
          <AlertTitle>Low-confidence AI result</AlertTitle>
          <AlertDescription>
            Doctor review is required before any patient-facing interpretation. The model's classification confidence is below the high-reliability threshold.
          </AlertDescription>
        </Alert>
      )}

      {/* AI section — visually separated */}
      <Card className="border-primary/30">
        <CardHeader className="flex-row items-center justify-between gap-3">
          <div className="min-w-0">
            <CardTitle className="text-base flex items-center gap-2"><Brain className="h-4 w-4 text-primary shrink-0" /> AI prediction</CardTitle>
            <CardDescription className="truncate">Model: {activeReport.modelName || model.name} · {activeReport.modelArchitecture || model.architecture}</CardDescription>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-center gap-2 rounded-md border border-border bg-muted/40 p-3 text-xs">
            <Cpu className="h-4 w-4 text-muted-foreground shrink-0" />
            <span className="font-medium">{activeReport.modelName || model.name}</span>
            <Badge variant="outline">v{activeReport.modelVersion ?? model.version}</Badge>
            <Badge variant="outline">{activeReport.modelArchitecture || model.architecture}</Badge>
            <Badge variant={heatmapAvailable ? "outline" : "secondary"}>
              Grad-CAM {heatmapAvailable ? "available" : "unavailable"}
            </Badge>
          </div>

          {activeReport.status === "processing" ? (
            <p className="text-sm text-muted-foreground">Analysis is still processing…</p>
          ) : (
            <>
              <MedicalImageViewer heatmapAvailable={heatmapAvailable} originalSrc={originalUrl} gradcamSrc={gradcamUrl} />

              <div className="grid gap-4 sm:grid-cols-[1fr_260px]">
                <div className="min-w-0">
                  <p className="text-xs text-muted-foreground">Predicted class</p>
                  <p className="text-lg font-semibold" data-testid="predicted-class-value">{activeReport.prediction ?? "—"}</p>
                  {activeReport.explanation && <p className="mt-2 text-sm text-muted-foreground">{activeReport.explanation}</p>}
                </div>
                <ConfidenceBreakdown probabilities={activeReport.probabilities} confidence={activeReport.confidence} topLabel={activeReport.prediction} />
              </div>
            </>
          )}
        </CardContent>
      </Card>

      <Card className="border-warning/30 bg-warning/5">
        <CardContent className="p-4 text-sm flex items-start gap-2">
          <ShieldAlert className="h-4 w-4 mt-0.5 text-warning shrink-0" />
          <p className="text-muted-foreground">
            <span className="font-medium text-warning-foreground">Disclaimer.</span> CliniXAI AI results are clinical decision-support information and are not a final diagnosis. The treating doctor must interpret AI findings together with symptoms, medical history, examination findings, and other clinical information.
          </p>
        </CardContent>
      </Card>

      {/* Doctor review — clearly separated */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Doctor review & clinical assessment</CardTitle>
          <CardDescription>Review AI findings and provide clinical assessment. Releasing allows the patient to view the finalized report.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-center gap-4 rounded-lg border bg-muted/40 p-3 text-xs">
            <div>
              <span className="text-muted-foreground font-medium">Lifecycle Status: </span>
              <Badge variant={activeReport.backendStatus === "reviewed" ? "default" : "secondary"} data-testid="lifecycle-status-badge">
                {activeReport.backendStatus === "reviewed" ? "Reviewed" : "Awaiting Doctor Review"}
              </Badge>
            </div>
            <div>
              <span className="text-muted-foreground font-medium">Patient Visibility: </span>
              <Badge
                variant={activeReport.isReleasedToPatient ? "outline" : "secondary"}
                className={activeReport.isReleasedToPatient ? "border-green-600 text-green-700 dark:text-green-400" : "text-amber-700 dark:text-amber-400"}
                data-testid="patient-visibility-badge"
              >
                {activeReport.isReleasedToPatient ? "Visible to Patient (Released)" : "Not Visible to Patient"}
              </Badge>
            </div>
          </div>

          <div>
            <Label>Decision</Label>
            <div className="mt-1 flex flex-wrap gap-2" role="radiogroup" aria-label="Review decision">
              {DECISIONS.map(({ value, label, icon: Icon }) => (
                <Button
                  key={value}
                  type="button"
                  size="sm"
                  variant={decision === value ? "default" : "outline"}
                  aria-pressed={decision === value}
                  onClick={() => setDecision(value)}
                  data-testid={`decision-btn-${value}`}
                >
                  <Icon className="h-4 w-4" /> {label}
                </Button>
              ))}
            </div>
          </div>
          <div>
            <Label htmlFor="ai-notes">Clinical assessment</Label>
            <Textarea
              id="ai-notes"
              data-testid="clinical-interpretation-input"
              rows={3}
              placeholder="Enter your clinical interpretation and notes for the patient..."
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            />
          </div>
          <div className="flex flex-wrap items-center gap-3 pt-1">
            {activeReport.doctorNote && <Badge variant="outline">Current review: {activeReport.doctorNote}</Badge>}
            {activeReport.reviewedOn && <Badge variant="outline">Reviewed on {fmtDate(activeReport.reviewedOn)}</Badge>}

            {/* Save Clinical Review Button */}
            <Button
              id="btn-save-review"
              data-testid="btn-save-review"
              onClick={handleSaveReview}
              disabled={isSavingReview}
              className="gap-2"
            >
              {isSavingReview ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
              {(activeReport.backendStatus === "reviewed" || activeReport.status?.toLowerCase().includes("reviewed")) ? "Update Review" : "Save Clinical Review"}
            </Button>

            {/* Explicit Release to Patient Button */}
            {(activeReport.backendStatus === "reviewed" || activeReport.status?.toLowerCase().includes("reviewed")) && !activeReport.isReleasedToPatient && (
              <Button
                id="btn-release-to-patient"
                data-testid="btn-release-to-patient"
                variant="default"
                onClick={() => setShowReleaseModal(true)}
                disabled={isReleasing}
                className="gap-2 bg-emerald-600 hover:bg-emerald-700 text-white"
              >
                {isReleasing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                Release to Patient
              </Button>
            )}

            {/* Fast-track Review & Release Button for Backward Compatibility */}
            <Button
              id="btn-review-and-release"
              data-testid="btn-review-and-release"
              variant="outline"
              size="sm"
              onClick={submit}
              className="gap-2 text-xs"
            >
              <CheckCircle2 className="h-3.5 w-3.5" />
              {activeReport.isReleasedToPatient ? "Update Review & Release" : "Quick Review & Release"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Explicit Release Confirmation Dialog */}
      <Dialog open={showReleaseModal} onOpenChange={setShowReleaseModal}>
        <DialogContent className="sm:max-w-md" data-testid="release-confirmation-dialog">
          <DialogHeader>
            <DialogTitle>Release AI Analysis to Patient</DialogTitle>
            <DialogDescription>
              Release this reviewed AI result to the patient? The patient will be able to view the reviewed clinical interpretation, prediction, confidence, and advisory report.
            </DialogDescription>
          </DialogHeader>
          <div className="rounded-md border p-3 text-xs space-y-1 bg-muted/40">
            <p><span className="font-semibold">Patient:</span> {activePatient.firstName} {activePatient.lastName} ({activePatient.id})</p>
            <p><span className="font-semibold">Clinical Interpretation:</span> {notes || activeReport.doctorNote || "Clinical review recorded."}</p>
            <p><span className="font-semibold">Review Decision:</span> {decision || activeReport.doctorDecision || "Accepted"}</p>
          </div>
          <DialogFooter className="flex flex-row items-center justify-end gap-2 pt-2">
            <Button
              id="btn-cancel-release"
              data-testid="btn-cancel-release"
              variant="outline"
              onClick={() => setShowReleaseModal(false)}
              disabled={isReleasing}
            >
              Cancel
            </Button>
            <Button
              id="btn-confirm-release"
              data-testid="btn-confirm-release"
              variant="default"
              className="bg-emerald-600 hover:bg-emerald-700 text-white"
              onClick={handleConfirmRelease}
              disabled={isReleasing}
            >
              {isReleasing ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <Send className="h-4 w-4 mr-1" />}
              Release to Patient
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
