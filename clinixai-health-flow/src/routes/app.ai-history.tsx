import { useEffect, useMemo, useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { Search, Brain, ChevronLeft, ChevronRight, SplitSquareHorizontal, X } from "lucide-react";
import { PageHeader } from "@/components/app-shell/page-header";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { EmptyState } from "@/components/dashboard/states";
import { fmtDate, todayIso } from "@/lib/mock/domain";
import { useClinix } from "@/lib/store/clinix-store";
import { getAIModel, modelForImageType } from "@/lib/mock/ai-models";
import { ConfidenceBreakdown } from "@/components/domain/confidence-breakdown";
import { apiClient } from "@/lib/api-client";
import type { AIReport } from "@/lib/mock/domain";

export const Route = createFileRoute("/app/ai-history")({
  head: () => ({ meta: [{ title: "AI History — CliniXAI" }, { name: "robots", content: "noindex" }] }),
  component: AIHistoryPage,
});

const PAGE_SIZE = 10;

function reviewBadge(r: any) {
  if (r.isReleasedToPatient) return <Badge variant="outline" className="border-emerald-600 text-emerald-700 dark:text-emerald-400">Released</Badge>;
  if (r.backendStatus === "reviewed" || r.status === "doctor-reviewed") return <Badge variant="outline" className="border-success/40 text-success">Reviewed (Unreleased)</Badge>;
  if (r.backendStatus === "awaiting_review" || !r.reviewDecision) return <Badge variant="secondary" className="text-amber-700 dark:text-amber-400">Awaiting Review</Badge>;
  if (r.reviewDecision === "accepted") return <Badge variant="outline" className="border-success/40 text-success">Accepted</Badge>;
  if (r.reviewDecision === "rejected") return <Badge variant="destructive">Rejected</Badge>;
  return <Badge variant="secondary">Not relevant</Badge>;
}

function AIHistoryPage() {
  const { aiReports, getPatient } = useClinix();
  const [remoteList, setRemoteList] = useState<AIReport[]>([]);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("all");
  const [type, setType] = useState("all");
  const [modelFilter, setModelFilter] = useState("all");
  const [decisionFilter, setDecisionFilter] = useState("all");
  const [page, setPage] = useState(1);
  const [compareMode, setCompareMode] = useState(false);
  const [selected, setSelected] = useState<string[]>([]);

  useEffect(() => {
    apiClient.ai.listAnalyses({ page_size: 50 })
      .then((res) => {
        const items = res?.items || res?.data || [];
        if (Array.isArray(items) && items.length > 0) {
          const mapped: AIReport[] = items.map((b: any) => {
            const modName = b.model?.name || "Brain MRI";
            const isRev = b.status === "reviewed" || b.status === "REVIEWED";
            const isRel = Boolean(b.is_released_to_patient);
            return {
              id: b.analysis_id,
              patientId: b.patient_id,
              doctorId: b.doctor_id,
              date: b.created_at ? String(b.created_at).split("T")[0] : todayIso(),
              imageType: modName.includes("Chest") ? "Chest X-Ray" : modName.includes("Brain") ? "Brain MRI" : modName,
              modelId: b.model?.module_id?.toLowerCase().includes("brain") ? "brain-mri" : "chest-xray",
              modelVersion: b.model?.version || "1.0.0",
              prediction: b.prediction?.predicted_class || "—",
              confidence: typeof b.prediction?.confidence === "number" ? b.prediction.confidence : 0.95,
              status: isRev ? (isRel ? "finalized" : "doctor-reviewed") : "analysis-completed",
              backendStatus: b.status,
              isReleasedToPatient: isRel,
              reviewDecision: b.doctor_review?.decision,
              doctorNote: b.doctor_review?.clinical_interpretation,
              probabilities: b.prediction?.probabilities || [],
              medicalRecordId: b.medical_record_id,
            } as any;
          });
          setRemoteList(mapped);
        }
      })
      .catch((err) => console.error("Could not fetch remote AI analyses for history:", err));
  }, []);

  const allReports = useMemo(() => {
    const ids = new Set(remoteList.map((x) => x.id));
    const unmerged = aiReports.filter((x) => !ids.has(x.id));
    return [...remoteList, ...unmerged];
  }, [remoteList, aiReports]);

  const imageTypes = useMemo(() => Array.from(new Set(allReports.map((r) => r.imageType))), [allReports]);
  const modelIds = useMemo(() => Array.from(new Set(allReports.map((r) => (r.modelId ? getAIModel(r.modelId)?.name : modelForImageType(r.imageType).name)))).filter(Boolean) as string[], [allReports]);

  const list = useMemo(() => allReports.filter((r: any) => {
    if (status !== "all") {
      if (status === "awaiting_review" && r.backendStatus !== "awaiting_review" && r.status !== "analysis-completed") return false;
      if (status === "reviewed" && r.backendStatus !== "reviewed" && r.status !== "doctor-reviewed") return false;
      if (status === "released" && !r.isReleasedToPatient && r.status !== "finalized") return false;
      if (!["awaiting_review", "reviewed", "released"].includes(status) && r.status !== status && r.backendStatus !== status) return false;
    }
    if (type !== "all" && r.imageType !== type) return false;
    const model = getAIModel(r.modelId) ?? modelForImageType(r.imageType);
    if (modelFilter !== "all" && model.name !== modelFilter) return false;
    if (decisionFilter !== "all") {
      if (decisionFilter === "pending" && (r.reviewDecision || r.backendStatus === "reviewed")) return false;
      if (decisionFilter !== "pending" && r.reviewDecision !== decisionFilter) return false;
    }
    if (q) {
      const p = getPatient(r.patientId);
      const hay = `${r.id} ${r.imageType} ${p?.firstName} ${p?.lastName} ${r.patientId} ${r.prediction}`.toLowerCase();
      if (!hay.includes(q.toLowerCase())) return false;
    }
    return true;
  }), [allReports, q, status, type, modelFilter, decisionFilter, getPatient]);

  useEffect(() => { setPage(1); }, [q, status, type, modelFilter, decisionFilter]);

  const totalPages = Math.max(1, Math.ceil(list.length / PAGE_SIZE));
  const pageItems = list.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  const toggleSelect = (id: string) => {
    setSelected((prev) => {
      if (prev.includes(id)) return prev.filter((x) => x !== id);
      if (prev.length >= 2) return [prev[1]!, id];
      return [...prev, id];
    });
  };

  const [reportA, reportB] = selected.map((id) => allReports.find((r) => r.id === id)).filter(Boolean) as AIReport[];

  return (
    <div className="space-y-6">
      <PageHeader
        title="AI analysis history"
        description="All AI analyses and their doctor review status."
        actions={
          <Button
            variant={compareMode ? "default" : "outline"}
            size="sm"
            onClick={() => { setCompareMode((v) => !v); setSelected([]); }}
          >
            <SplitSquareHorizontal className="h-4 w-4" /> {compareMode ? "Exit comparison" : "Compare analyses"}
          </Button>
        }
      />

      {compareMode && (
        <Card className="border-primary/30">
          <CardContent className="p-3 text-xs text-muted-foreground">
            Select exactly two analyses below (checkboxes) to compare side-by-side. Selected: {selected.length}/2.
          </CardContent>
        </Card>
      )}

      {compareMode && reportA && reportB && (
        <ComparisonPanel a={reportA} b={reportB} onClose={() => setSelected([])} />
      )}

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:flex-wrap">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search analysis, patient, prediction…" className="pl-9" aria-label="Search AI history" />
        </div>
        <select className="h-10 rounded-md border border-input bg-background px-2 text-sm" value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Filter by status">
          <option value="all">All statuses</option>
          <option value="awaiting_review">Awaiting Review</option>
          <option value="reviewed">Reviewed (Unreleased)</option>
          <option value="released">Released</option>
        </select>
        <select className="h-10 rounded-md border border-input bg-background px-2 text-sm" value={type} onChange={(e) => setType(e.target.value)} aria-label="Filter by image type">
          <option value="all">All types</option>
          {imageTypes.map((t) => <option key={t}>{t}</option>)}
        </select>
        <select className="h-10 rounded-md border border-input bg-background px-2 text-sm" value={modelFilter} onChange={(e) => setModelFilter(e.target.value)} aria-label="Filter by model">
          <option value="all">All models</option>
          {modelIds.map((m) => <option key={m}>{m}</option>)}
        </select>
        <select className="h-10 rounded-md border border-input bg-background px-2 text-sm" value={decisionFilter} onChange={(e) => setDecisionFilter(e.target.value)} aria-label="Filter by review decision">
          <option value="all">All review decisions</option>
          <option value="pending">Pending review</option>
          <option value="accepted">Accepted</option>
          <option value="rejected">Rejected</option>
          <option value="not-relevant">Not relevant</option>
        </select>
      </div>

      {list.length === 0 ? <EmptyState icon={Brain} title="No AI analyses" description="Nothing matches this filter." /> : (
        <>
          <Card><CardContent className="p-0">
            <ul className="divide-y divide-border">
              {pageItems.map((r: any) => {
                const p = getPatient(r.patientId);
                const model = getAIModel(r.modelId) ?? modelForImageType(r.imageType);
                const confidence = r.confidence ?? 0;
                const isSelected = selected.includes(r.id);
                return (
                  <li key={r.id} className={`grid grid-cols-1 gap-2 p-4 sm:items-center ${compareMode ? "sm:grid-cols-[24px_1.3fr_1fr_120px_110px_140px_auto]" : "sm:grid-cols-[1.4fr_1fr_120px_110px_140px_auto]"}`}>
                    {compareMode && (
                      <Checkbox
                        checked={isSelected}
                        onCheckedChange={() => toggleSelect(r.id)}
                        aria-label={`Select ${r.id} for comparison`}
                        disabled={!isSelected && selected.length >= 2}
                      />
                    )}
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium">{r.imageType}</p>
                      <p className="truncate text-xs text-muted-foreground">{p?.firstName ? `${p.firstName} ${p.lastName}` : r.patientId} · {r.id}</p>
                    </div>
                    <div className="min-w-0">
                      <p className="truncate text-sm">{r.prediction ?? "—"}</p>
                      <p className="text-xs text-muted-foreground">{fmtDate(r.date)} · {model.name}</p>
                    </div>
                    <div className="min-w-0">
                      <p className="text-xs tabular-nums">{Math.round(confidence <= 1 ? confidence * 100 : confidence)}%</p>
                      <div className="mt-1 h-1.5 w-full max-w-[90px] overflow-hidden rounded-full bg-muted">
                        <div className="h-full bg-primary" style={{ width: `${Math.round(confidence <= 1 ? confidence * 100 : confidence)}%` }} />
                      </div>
                    </div>
                    <div><Badge variant="outline">v{r.modelVersion ?? model.version}</Badge></div>
                    <div>{reviewBadge(r)}</div>
                    <div className="flex justify-end">
                      <Button asChild size="sm" variant="outline">
                        <Link to="/app/ai-analysis/$id" params={{ id: r.id }}>View</Link>
                      </Button>
                    </div>
                  </li>
                );
              })}
            </ul>
          </CardContent></Card>
          {totalPages > 1 && (
            <div className="flex items-center justify-between text-sm">
              <p className="text-muted-foreground">Page {page} of {totalPages} · {list.length} results</p>
              <div className="flex gap-2">
                <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))} aria-label="Previous page"><ChevronLeft className="h-4 w-4" /></Button>
                <Button size="sm" variant="outline" disabled={page >= totalPages} onClick={() => setPage((p) => Math.min(totalPages, p + 1))} aria-label="Next page"><ChevronRight className="h-4 w-4" /></Button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function ComparisonPanel({ a, b, onClose }: { a: AIReport; b: AIReport; onClose: () => void }) {
  const { getPatient } = useClinix();
  const pA = getPatient(a.patientId);
  const pB = getPatient(b.patientId);
  const modelA = getAIModel(a.modelId) ?? modelForImageType(a.imageType);
  const modelB = getAIModel(b.modelId) ?? modelForImageType(b.imageType);
  const delta = Math.abs((a.confidence ?? 0) - (b.confidence ?? 0));

  const Col = ({ r, p, model }: { r: AIReport; p?: ReturnType<typeof getPatient>; model: ReturnType<typeof getAIModel> }) => (
    <div className="min-w-0 space-y-3">
      <div>
        <p className="truncate text-sm font-semibold">{p?.firstName} {p?.lastName} <span className="text-xs font-normal text-muted-foreground">({p?.id})</span></p>
        <p className="text-xs text-muted-foreground">{r.id} · {fmtDate(r.date)}</p>
      </div>
      <div className="flex flex-wrap gap-1.5">
        <Badge variant="outline">{model?.name}</Badge>
        <Badge variant="outline">v{r.modelVersion ?? model?.version}</Badge>
      </div>
      <div>
        <p className="text-xs text-muted-foreground">Predicted class</p>
        <p className="text-base font-semibold">{r.prediction ?? "—"}</p>
      </div>
      <ConfidenceBreakdown probabilities={r.probabilities} confidence={r.confidence} topLabel={r.prediction} />
      <div>
        <p className="text-xs text-muted-foreground">Doctor review</p>
        <p className="text-sm">{r.reviewDecision ?? "Pending"} {r.doctorNote ? `— ${r.doctorNote}` : ""}</p>
      </div>
    </div>
  );

  return (
    <Card className="border-primary/40">
      <CardHeader className="flex-row items-center justify-between">
        <div>
          <CardTitle className="text-base">AI analysis comparison</CardTitle>
          <CardDescription>Confidence delta: {Math.round(delta * 100)} percentage points</CardDescription>
        </div>
        <Button variant="ghost" size="icon" aria-label="Close comparison" onClick={onClose}><X className="h-4 w-4" /></Button>
      </CardHeader>
      <CardContent className="grid gap-6 sm:grid-cols-2">
        <Col r={a} p={pA} model={modelA} />
        <div className="border-t pt-3 sm:border-t-0 sm:border-l sm:pl-6 sm:pt-0">
          <Col r={b} p={pB} model={modelB} />
        </div>
      </CardContent>
    </Card>
  );
}
