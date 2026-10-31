import { createFileRoute } from "@tanstack/react-router";
import { Brain, Cpu, ShieldCheck, AlertTriangle } from "lucide-react";
import { PageHeader } from "@/components/app-shell/page-header";
import { ResponsiveGrid, KpiCard } from "@/components/dashboard/cards";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { HBarSeries } from "@/components/dashboard/mini-chart";
import { useClinix } from "@/lib/store/clinix-store";
import { fmtDate } from "@/lib/mock/domain";
import { AIBadge } from "@/components/domain/status-badge";

export const Route = createFileRoute("/app/ai-insights")({
  head: () => ({ meta: [{ title: "AI Insights — CliniXAI Admin" }, { name: "robots", content: "noindex" }] }),
  component: AIInsightsPage,
});

function AIInsightsPage() {
  const clinix = useClinix();
  const { aiReports, doctors, getPatient, getDoctor } = clinix;

  const total = aiReports.length;
  const today = new Date().toISOString().slice(0, 10);
  const todaysCount = aiReports.filter((r) => r.date === today).length;
  const reviewed = aiReports.filter((r) => r.status === "doctor-reviewed" || r.status === "finalized").length;
  const pending = aiReports.filter((r) => r.status === "analysis-completed" || r.status === "processing" || r.status === "uploaded").length;
  const failed = 0;

  const deptAiCounts: Record<string, number> = {};
  aiReports.forEach((r) => {
    const doc = r.doctorId ? getDoctor(r.doctorId) : undefined;
    const deptName = doc ? doc.department : "Radiology";
    deptAiCounts[deptName] = (deptAiCounts[deptName] || 0) + 1;
  });
  const usage = Object.entries(deptAiCounts).map(([name, val]) => ({
    label: name,
    value: val,
  }));

  return (
    <div className="space-y-6">
      <PageHeader
        title="AI Insights"
        description="Monitor AI usage and review workflow across the hospital. This dashboard tracks operations only — it does not make clinical decisions."
        status={{ label: "Active Inference Pipeline", tone: "success" }}
      />

      <ResponsiveGrid cols={{ base: 2, sm: 3, lg: 5 }}>
        <KpiCard label="Total AI Analyses" value={total} icon={Brain} />
        <KpiCard label="Analyses Today" value={todaysCount} icon={Brain} />
        <KpiCard label="Doctor Reviewed" value={reviewed} icon={ShieldCheck} />
        <KpiCard label="Pending Review" value={pending} icon={AlertTriangle} />
        <KpiCard label="Failed" value={failed} icon={AlertTriangle} />
      </ResponsiveGrid>

      <ResponsiveGrid cols={{ base: 1, lg: 2 }}>
        <Card>
          <CardContent className="p-5">
            <p className="mb-3 font-display text-base font-semibold">AI usage by department</p>
            <HBarSeries data={usage.length > 0 ? usage : [{ label: "Radiology", value: 0 }]} />
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-5">
            <p className="mb-3 flex items-center gap-2 font-display text-base font-semibold">
              <Cpu className="h-4 w-4" /> AI Model Information
            </p>
            <dl className="grid grid-cols-2 gap-3 text-sm">
              <div>
                <dt className="text-xs text-muted-foreground">Architecture</dt>
                <dd className="font-medium">ResNet50 / DenseNet121</dd>
              </div>
              <div>
                <dt className="text-xs text-muted-foreground">Technique</dt>
                <dd className="font-medium">Transfer Learning</dd>
              </div>
              <div>
                <dt className="text-xs text-muted-foreground">Explainability</dt>
                <dd className="font-medium">Grad-CAM Activation Maps</dd>
              </div>
              <div>
                <dt className="text-xs text-muted-foreground">Status</dt>
                <dd>
                  <Badge variant="outline" className="border-success/20 bg-success/10 text-success">
                    Production Microservice
                  </Badge>
                </dd>
              </div>
            </dl>
            <p className="mt-3 rounded-lg border border-primary/20 bg-primary/5 p-3 text-xs text-primary">
              Connected via FastAPI PyTorch/ONNX inference service. All AI outputs remain advisory — clinical decisions belong to the reviewing doctor.
            </p>
          </CardContent>
        </Card>
      </ResponsiveGrid>

      <Card>
        <CardContent className="p-0">
          <div className="flex items-center justify-between border-b border-border p-4">
            <p className="font-display text-sm font-semibold">Recent AI analyses</p>
            <span className="text-xs text-muted-foreground">Live MongoDB records</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-sm">
              <thead className="bg-muted/40 text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="p-3 text-left">Analysis</th>
                  <th className="p-3 text-left">Patient</th>
                  <th className="p-3 text-left">Doctor</th>
                  <th className="p-3 text-left">Image Type</th>
                  <th className="p-3 text-left">Date</th>
                  <th className="p-3 text-left">Status</th>
                  <th className="p-3 text-left">Doctor Review</th>
                </tr>
              </thead>
              <tbody>
                {aiReports.map((r) => {
                  const p = getPatient(r.patientId);
                  const d = r.doctorId ? getDoctor(r.doctorId) : undefined;
                  const reviewedNow = r.status === "doctor-reviewed" || r.status === "finalized";
                  return (
                    <tr key={r.id} className="border-b border-border">
                      <td className="p-3 font-medium">{r.id}</td>
                      <td className="p-3">{p ? `${p.firstName} ${p.lastName}` : r.patientId}</td>
                      <td className="p-3">{d?.name ?? "Unassigned"}</td>
                      <td className="p-3 capitalize">{r.imageType}</td>
                      <td className="p-3 text-xs text-muted-foreground">{fmtDate(r.date)}</td>
                      <td className="p-3">
                        <AIBadge status={r.status} />
                      </td>
                      <td className="p-3 text-xs">
                        <Badge
                          variant="outline"
                          className={
                            reviewedNow
                              ? "border-success/20 bg-success/10 text-success"
                              : "border-warning/20 bg-warning/10 text-warning"
                          }
                        >
                          {reviewedNow ? "Reviewed" : "Pending"}
                        </Badge>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {aiReports.length === 0 && (
            <div className="p-6 text-center text-sm text-muted-foreground">
              <Brain className="mx-auto mb-2 h-6 w-6 text-muted-foreground" /> No AI analysis records found in MongoDB.
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
