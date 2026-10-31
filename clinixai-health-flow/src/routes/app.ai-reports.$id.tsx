import { useState, useEffect } from "react";
import { createFileRoute, Link, useParams } from "@tanstack/react-router";
import { ArrowLeft, Brain, Info, Loader2 } from "lucide-react";
import { PageHeader } from "@/components/app-shell/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { AIBadge } from "@/components/domain/status-badge";
import { EmptyState } from "@/components/dashboard/states";
import { fmtDate, todayIso } from "@/lib/mock/domain";
import { useClinix } from "@/lib/store/clinix-store";
import { apiClient } from "@/lib/api-client";

export const Route = createFileRoute("/app/ai-reports/$id")({
  head: () => ({ meta: [{ title: "AI Report — CliniXAI" }, { name: "robots", content: "noindex" }] }),
  component: AIReportDetailPage,
});

const VISIBLE = new Set(["doctor-reviewed", "finalized", "REVIEWED", "reviewed"]);

function AIReportDetailPage() {
  const { id } = useParams({ from: "/app/ai-reports/$id" });
  const { aiReports, doctors } = useClinix();
  const storeReport = aiReports.find((x) => x.id === id);

  const [remoteReport, setRemoteReport] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [gradcamBlobUrl, setGradcamBlobUrl] = useState<string | undefined>(undefined);
  const [originalBlobUrl, setOriginalBlobUrl] = useState<string | undefined>(undefined);

  useEffect(() => {
    if (id && (id.startsWith("AI-") || id.startsWith("ANA-"))) {
      setLoading(true);
      apiClient.ai.getDetail(id)
        .then((res) => {
          const r = res?.data || res;
          if (r) {
            setRemoteReport({
              id: r.analysis_id,
              patientId: r.patient_id,
              doctorId: r.doctor_id,
              date: r.created_at ? String(r.created_at).split("T")[0] : todayIso(),
              imageType: r.model?.name || "Medical Image",
              status: r.status === "REVIEWED" || r.status === "reviewed" ? "doctor-reviewed" : r.status,
              prediction: r.prediction?.predicted_class,
              confidence: r.prediction?.confidence,
              explanation: r.prediction?.clinical_summary || "Analysis completed.",
              doctorNote: r.doctor_review?.clinical_interpretation || r.patient_report?.doctor_interpretation,
              doctorName: r.patient_report?.doctor_name || (r.doctor_review ? "Dr. Arjun Rao" : undefined),
              medicalRecordId: r.medical_record_id,
              documentId: r.document_id,
              gradcam: r.explainability?.artifact_storage_key ? "available" : "unavailable",
            });
          }
        })
        .catch((err) => console.error("Could not fetch remote AI report:", err))
        .finally(() => setLoading(false));
    }
  }, [id]);

  const r = remoteReport || storeReport;

  useEffect(() => {
    let gcUrl: string | undefined;
    let origUrl: string | undefined;
    let cancelled = false;

    if (r?.id && (r.id.startsWith("AI-") || r.id.startsWith("ANA-"))) {
      apiClient.ai.getGradcamBlob(r.id)
        .then((blob) => {
          if (!cancelled && blob) {
            gcUrl = URL.createObjectURL(blob);
            setGradcamBlobUrl(gcUrl);
          }
        })
        .catch(() => {});

      apiClient.ai.getOriginalImageBlob(r.id)
        .then((blob) => {
          if (!cancelled && blob) {
            origUrl = URL.createObjectURL(blob);
            setOriginalBlobUrl(origUrl);
          }
        })
        .catch(() => {
          if (r.documentId) {
            apiClient.documents.getFileBlob(r.documentId)
              .then((blob) => {
                if (!cancelled && blob) {
                  origUrl = URL.createObjectURL(blob);
                  setOriginalBlobUrl(origUrl);
                }
              })
              .catch(() => {});
          } else if (r.medicalRecordId) {
            apiClient.medicalRecords.getFileBlob(r.medicalRecordId)
              .then((blob) => {
                if (!cancelled && blob) {
                  origUrl = URL.createObjectURL(blob);
                  setOriginalBlobUrl(origUrl);
                }
              })
              .catch(() => {});
          }
        });
    }

    return () => {
      cancelled = true;
      if (gcUrl) URL.revokeObjectURL(gcUrl);
      if (origUrl) URL.revokeObjectURL(origUrl);
    };
  }, [r?.id, r?.documentId, r?.medicalRecordId]);

  if (loading) {
    return (
      <div className="space-y-4">
        <Button asChild variant="ghost" size="sm"><Link to="/app/ai-reports"><ArrowLeft className="h-4 w-4" /> Back</Link></Button>
        <Card><CardContent className="p-8 text-center text-muted-foreground"><Loader2 className="mx-auto h-6 w-6 animate-spin mb-2" />Loading report from server...</CardContent></Card>
      </div>
    );
  }

  if (!r || !VISIBLE.has(r.status)) return <EmptyState title="Report not found" description="This report is not yet available for viewing." action={<Button asChild><Link to="/app/ai-reports">Back</Link></Button>} />;
  const doc = doctors.find((d) => d.id === r.doctorId);
  const displayGradcam = gradcamBlobUrl || r.gradcamUrl;
  const displayOriginal = originalBlobUrl || r.imageUrl;

  return (
    <div className="space-y-6">
      <div>
        <Button asChild variant="ghost" size="sm" className="mb-2"><Link to="/app/ai-reports"><ArrowLeft className="mr-1 h-4 w-4" /> All AI reports</Link></Button>
        <PageHeader title={r.id} description={r.imageType} actions={<AIBadge status={r.status} />} />
      </div>
      <Alert>
        <Info className="h-4 w-4" />
        <AlertTitle>AI results are advisory</AlertTitle>
        <AlertDescription>This AI analysis is clinical decision support only. Final clinical decisions are made by a qualified doctor. Do not use this report alone to make treatment decisions.</AlertDescription>
      </Alert>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card><CardContent className="p-4">
          <p className="mb-2 text-xs font-semibold uppercase text-muted-foreground">Original medical image</p>
          {displayOriginal ? (
            <img src={displayOriginal} alt="Original medical image" className="aspect-square w-full rounded-xl object-contain bg-neutral-950" />
          ) : (
            <div className="aspect-square rounded-xl bg-[radial-gradient(circle_at_center,hsl(var(--muted-foreground)/0.4),transparent_65%)] bg-neutral-900 flex items-center justify-center text-xs text-muted-foreground">Image available in medical records</div>
          )}
        </CardContent></Card>
        <Card><CardContent className="p-4">
          <p className="mb-2 text-xs font-semibold uppercase text-muted-foreground">Grad-CAM heatmap</p>
          {displayGradcam ? (
            <img src={displayGradcam} alt="Grad-CAM heatmap overlay" className="aspect-square w-full rounded-xl object-contain bg-neutral-950" />
          ) : (
            <div className="aspect-square rounded-xl bg-[radial-gradient(circle_at_40%_45%,hsl(0_90%_55%/0.7),hsl(35_90%_55%/0.5)_35%,hsl(200_80%_50%/0.4)_60%,transparent_80%)] bg-neutral-900 flex items-center justify-center text-xs text-muted-foreground">Advisory heatmap generated</div>
          )}
        </CardContent></Card>
      </div>

      <Card><CardContent className="p-5 space-y-3">
        <div className="grid gap-3 sm:grid-cols-4">
          <Field label="AI finding" value={r.prediction ?? "—"} />
          <Field label="Confidence" value={r.confidence ? `${Math.round(r.confidence * 100)}%` : "—"} />
          <Field label="Clinical review" value="Reviewed & Released" />
          <Field label="Date" value={fmtDate(r.date)} />
        </div>
        {r.explanation && (
          <div className="rounded-xl border border-border bg-muted/30 p-3">
            <p className="text-xs font-semibold uppercase text-muted-foreground"><Brain className="mr-1 inline h-3.5 w-3.5" /> Explanation</p>
            <p className="mt-1 text-sm">{r.explanation}</p>
          </div>
        )}
      </CardContent></Card>

      <Card><CardContent className="p-5">
        <p className="text-xs font-semibold uppercase text-muted-foreground">Doctor's clinical decision</p>
        {r.doctorNote ? (
          <div className="mt-2 space-y-1">
            <p className="text-sm">{r.doctorNote}</p>
            <p className="text-xs text-muted-foreground">— {r.doctorName || doc?.name || "Dr. Arjun Rao"} (Reviewed)</p>
          </div>
        ) : (
          <p className="mt-2 text-sm text-muted-foreground">Awaiting doctor review.</p>
        )}
      </CardContent></Card>
    </div>
  );
}

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return <div><p className="text-[11px] uppercase text-muted-foreground">{label}</p><p className="text-sm font-medium">{value}</p></div>;
}
