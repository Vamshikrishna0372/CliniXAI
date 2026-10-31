import { useState, useEffect } from "react";
import { createFileRoute, Link, Outlet, useMatch } from "@tanstack/react-router";
import { Brain, ChevronRight, Info, Loader2, RefreshCw } from "lucide-react";
import { PageHeader } from "@/components/app-shell/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { AIBadge } from "@/components/domain/status-badge";
import { EmptyState } from "@/components/dashboard/states";
import { useAuth } from "@/lib/auth-context";
import { fmtDate } from "@/lib/mock/domain";
import { useClinix } from "@/lib/store/clinix-store";
import { apiClient } from "@/lib/api-client";

export const Route = createFileRoute("/app/ai-reports")({
  head: () => ({ meta: [{ title: "AI Reports — CliniXAI" }, { name: "robots", content: "noindex" }] }),
  component: AIReportsPage,
});

const VISIBLE = new Set(["doctor-reviewed", "finalized", "REVIEWED", "reviewed"]);

function AIReportsPage() {
  const isDetail = useMatch({ from: "/app/ai-reports/$id", shouldThrow: false });

  const { user } = useAuth();
  const { aiReports, doctors, patients } = useClinix();
  const patient = patients.find((p) => p.email === user?.email || p.id === user?.id);
  const patId = patient ? patient.id : user?.id;

  const [remoteItems, setRemoteItems] = useState<any[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [page, setPage] = useState<number>(1);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const fetchLiveReports = async (pageNumber: number) => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiClient.ai.listAnalyses({ page: pageNumber, page_size: 10 });
      const items = res?.items || res?.data || [];
      setRemoteItems(items);
      setTotal(res?.total || items.length);
      setPage(pageNumber);
    } catch (err: any) {
      console.error("Failed to load live AI analyses:", err);
      setError(err?.message || "Failed to load reports from server.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (user) {
      fetchLiveReports(1);
    }
  }, [user]);

  if (isDetail) {
    return <Outlet />;
  }

  // If remote items loaded from API, use them; otherwise fall back to synced store reports
  const displayItems = remoteItems.length > 0 ? remoteItems.map((r: any) => ({
    id: r.analysis_id,
    patientId: r.patient_id,
    doctorId: r.doctor_id,
    date: r.created_at ? String(r.created_at).split("T")[0] : "",
    imageType: r.model?.name || "Medical Image",
    status: r.status === "reviewed" || r.status === "REVIEWED" ? "doctor-reviewed" : r.status,
    prediction: r.prediction?.predicted_class,
    confidence: r.prediction?.confidence,
    appointmentId: r.appointment_id,
  })) : (user?.role === "patient"
    ? aiReports.filter((r) => (r.patientId === patId || r.patientId === user?.id) && VISIBLE.has(r.status))
    : aiReports);

  const totalPages = Math.ceil(total / 10) || 1;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <PageHeader title="AI Reports" description="Clinical decision-support insights from your medical images." />
        <Button variant="outline" size="sm" onClick={() => fetchLiveReports(page)} disabled={loading}>
          {loading ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="mr-1 h-3.5 w-3.5" />}
          Refresh
        </Button>
      </div>

      <Alert>
        <Info className="h-4 w-4" />
        <AlertTitle>AI results are advisory</AlertTitle>
        <AlertDescription>AI-generated results are clinical decision-support information and should be interpreted by a qualified healthcare professional. Reports are only shown here once a doctor has reviewed them.</AlertDescription>
      </Alert>

      {loading && displayItems.length === 0 ? (
        <Card><CardContent className="p-8 text-center text-muted-foreground"><Loader2 className="mx-auto h-6 w-6 animate-spin mb-2" />Loading AI reports from server...</CardContent></Card>
      ) : error && displayItems.length === 0 ? (
        <Card className="border-destructive/30 bg-destructive/5"><CardContent className="p-6 text-center text-destructive">{error}</CardContent></Card>
      ) : displayItems.length === 0 ? (
        <EmptyState icon={Brain} title="No AI reports yet" description="AI analyses of your medical images will appear here once reviewed by your doctor." />
      ) : (
        <div className="grid gap-3">
          {displayItems.map((r) => {
            const doc = doctors.find((d) => d.id === r.doctorId);
            return (
              <Card key={r.id} className="card-hover">
                <CardContent className="p-4 sm:p-5">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="font-display text-base font-semibold">{r.id}</p>
                        <AIBadge status={r.status} />
                      </div>
                      <p className="mt-0.5 text-sm">{r.imageType}</p>
                      <p className="mt-1 text-xs text-muted-foreground">{fmtDate(r.date)} {doc && `• ${doc.name}`} {r.appointmentId && `• ${r.appointmentId}`}</p>
                      {r.prediction && <p className="mt-2 text-sm"><span className="text-muted-foreground">AI prediction:</span> {r.prediction} {r.confidence && <span className="text-muted-foreground">({Math.round(r.confidence > 1 ? r.confidence : r.confidence * 100)}%)</span>}</p>}
                    </div>
                    <Button asChild size="sm" variant="ghost"><Link to="/app/ai-reports/$id" params={{ id: r.id }}>Open <ChevronRight className="ml-1 h-4 w-4" /></Link></Button>
                  </div>
                </CardContent>
              </Card>
            );
          })}

          {totalPages > 1 && (
            <div className="flex items-center justify-between pt-2">
              <p className="text-xs text-muted-foreground">Page {page} of {totalPages} ({total} total analyses)</p>
              <div className="flex gap-2">
                <Button size="sm" variant="outline" disabled={page <= 1 || loading} onClick={() => fetchLiveReports(page - 1)}>Previous</Button>
                <Button size="sm" variant="outline" disabled={page >= totalPages || loading} onClick={() => fetchLiveReports(page + 1)}>Next</Button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
