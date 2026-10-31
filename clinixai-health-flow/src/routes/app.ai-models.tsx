import { useMemo, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Cpu, Search, ScanEye, Brain } from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/app-shell/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { EmptyState } from "@/components/dashboard/states";
import { useClinix } from "@/lib/store/clinix-store";
import { fmtDate } from "@/lib/mock/domain";
import type { AIModel } from "@/lib/mock/ai-models";

export const Route = createFileRoute("/app/ai-models")({
  head: () => ({ meta: [{ title: "AI Models — CliniXAI Admin" }, { name: "robots", content: "noindex" }] }),
  component: AIModelsPage,
});

const STATUS_TONE: Record<AIModel["status"], string> = {
  active: "bg-success/10 text-success border-success/20",
  disabled: "bg-error/10 text-error border-error/20",
  maintenance: "bg-warning/10 text-warning border-warning/20",
};

function AIModelsPage() {
  const { aiModels, aiReports, setAIModelStatus } = useClinix();
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("all");
  const [modality, setModality] = useState("all");
  const [detail, setDetail] = useState<AIModel | null>(null);

  const modalities = ["all", ...Array.from(new Set(aiModels.map((m) => m.modality)))];

  const rows = useMemo(() => {
    return aiModels.filter((m) => {
      if (status !== "all" && m.status !== status) return false;
      if (modality !== "all" && m.modality !== modality) return false;
      if (q && !`${m.name} ${m.architecture} ${m.version}`.toLowerCase().includes(q.toLowerCase())) return false;
      return true;
    });
  }, [aiModels, q, status, modality]);

  const totalPredictions = aiModels.reduce((s, m) => s + m.predictions, 0);
  const meanConfidence = aiModels.length
    ? aiModels.reduce((s, m) => s + m.avgConfidence, 0) / aiModels.length
    : 0;
  const activeCount = aiModels.filter((m) => m.status === "active").length;

  const changeStatus = (m: AIModel, next: AIModel["status"]) => {
    if (next === m.status) return;
    setAIModelStatus(m.id, next);
    toast.success(`${m.name} set to ${next}`);
  };

  const relatedReports = detail
    ? aiReports.filter((r) => r.modelId === detail.id).slice(0, 8)
    : [];

  return (
    <div className="space-y-6">
      <PageHeader title="AI Model Management" description="Registry of every AI/ML model deployed across CliniXAI." status={{ label: "Mock data", tone: "info" }} />

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Kpi label="Total models" value={String(aiModels.length)} />
        <Kpi label="Active" value={String(activeCount)} />
        <Kpi label="Total predictions" value={totalPredictions.toLocaleString("en-IN")} />
        <Kpi label="Mean confidence" value={`${Math.round(meanConfidence * 100)}%`} />
      </div>

      <Card><CardContent className="grid gap-3 p-4 sm:grid-cols-2 xl:grid-cols-[minmax(0,1fr)_minmax(0,160px)_minmax(0,160px)] [&>*]:min-w-0">
        <div className="relative"><Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" /><Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search model, architecture…" aria-label="Search AI models" className="pl-9" /></div>
        <Select value={status} onValueChange={setStatus}>
          <SelectTrigger><SelectValue placeholder="Status" /></SelectTrigger>
          <SelectContent>{["all", "active", "disabled", "maintenance"].map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
        </Select>
        <Select value={modality} onValueChange={setModality}>
          <SelectTrigger><SelectValue placeholder="Modality" /></SelectTrigger>
          <SelectContent>{modalities.map((m) => <SelectItem key={m} value={m}>{m}</SelectItem>)}</SelectContent>
        </Select>
      </CardContent></Card>

      {rows.length === 0 ? (
        <EmptyState icon={Cpu} title="No models match" description="Try clearing filters or search terms." />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {rows.map((m) => (
            <Card key={m.id} className="min-w-0">
              <CardContent className="space-y-3 p-4">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="truncate font-display text-sm font-semibold text-foreground">{m.name}</p>
                    <p className="text-xs text-muted-foreground">{m.modality} • {m.version}</p>
                  </div>
                  <Badge variant="outline" className={STATUS_TONE[m.status] + " shrink-0"}>{m.status}</Badge>
                </div>

                <div className="grid grid-cols-2 gap-2 text-xs text-muted-foreground">
                  <div><span className="block text-foreground">{m.architecture}</span>Architecture</div>
                  <div><span className="block text-foreground">{m.inputSize}</span>Input size</div>
                  <div><span className="block text-foreground">{fmtDate(m.lastTrained)}</span>Last trained</div>
                  <div><span className="block text-foreground">{m.predictions.toLocaleString("en-IN")}</span>Predictions</div>
                  <div><span className="block text-foreground">{Math.round(m.avgConfidence * 100)}%</span>Avg. confidence</div>
                  <div><span className="block text-foreground">{Math.round(m.accuracy * 100)}%</span>Accuracy</div>
                </div>

                <div className="flex flex-wrap items-center gap-1.5">
                  <Badge variant="outline" className="gap-1"><ScanEye className="h-3 w-3" /> Grad-CAM {m.gradcam}</Badge>
                  {m.classes.slice(0, 3).map((c) => <Badge key={c} variant="secondary" className="truncate">{c}</Badge>)}
                  {m.classes.length > 3 && <Badge variant="secondary">+{m.classes.length - 3}</Badge>}
                </div>

                <div className="flex flex-wrap items-center gap-2 pt-1">
                  <Button size="sm" variant="outline" className="flex-1" onClick={() => setDetail(m)}>View details</Button>
                  <Select value={m.status} onValueChange={(v) => changeStatus(m, v as AIModel["status"])}>
                    <SelectTrigger className="h-9 w-[130px] shrink-0"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="active">Active</SelectItem>
                      <SelectItem value="maintenance">Maintenance</SelectItem>
                      <SelectItem value="disabled">Disabled</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Dialog open={!!detail} onOpenChange={(o) => !o && setDetail(null)}>
        <DialogContent className="max-h-[85vh] max-w-lg overflow-y-auto">
          {detail && (
            <>
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2"><Brain className="h-4 w-4 text-primary" /> {detail.name}</DialogTitle>
                <DialogDescription>{detail.architecture} • {detail.version}</DialogDescription>
              </DialogHeader>
              <div className="space-y-4 text-sm">
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <Field label="Dataset size" value={detail.datasetSize.toLocaleString("en-IN")} />
                  <Field label="Input size" value={detail.inputSize} />
                  <Field label="Accuracy" value={`${Math.round(detail.accuracy * 100)}%`} />
                  <Field label="Avg. confidence" value={`${Math.round(detail.avgConfidence * 100)}%`} />
                  <Field label="Last trained" value={fmtDate(detail.lastTrained)} />
                  <Field label="Grad-CAM" value={detail.gradcam} />
                </div>
                <div>
                  <p className="mb-1 text-xs font-semibold text-foreground">Notes</p>
                  <p className="text-xs text-muted-foreground">{detail.notes}</p>
                </div>
                <div>
                  <p className="mb-1 text-xs font-semibold text-foreground">Class labels</p>
                  <div className="flex flex-wrap gap-1.5">{detail.classes.map((c) => <Badge key={c} variant="secondary">{c}</Badge>)}</div>
                </div>
                <div>
                  <p className="mb-1 text-xs font-semibold text-foreground">Recent predictions</p>
                  {relatedReports.length === 0 ? (
                    <p className="text-xs text-muted-foreground">No predictions recorded for this model yet.</p>
                  ) : (
                    <div className="space-y-1.5">
                      {relatedReports.map((r) => (
                        <div key={r.id} className="flex items-center justify-between gap-2 rounded-lg border border-border p-2 text-xs">
                          <span className="min-w-0 truncate">{r.prediction ?? r.imageType} • {r.patientId}</span>
                          <span className="shrink-0 text-muted-foreground">{r.confidence ? `${Math.round(r.confidence * 100)}%` : "—"}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}

function Kpi({ label, value }: { label: string; value: string }) {
  return (
    <Card><CardContent className="p-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 truncate font-display text-lg font-bold text-foreground">{value}</p>
    </CardContent></Card>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border p-2">
      <p className="text-muted-foreground">{label}</p>
      <p className="truncate font-medium text-foreground">{value}</p>
    </div>
  );
}
