import { useEffect, useState, useMemo } from "react";
import { createFileRoute, Link, Outlet, useMatch } from "@tanstack/react-router";
import { Eye, Pill, RefreshCw, AlertCircle, Calendar, User, CheckCircle2, XCircle } from "lucide-react";
import { PageHeader } from "@/components/app-shell/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/dashboard/states";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useAuth } from "@/lib/auth-context";
import { apiClient } from "@/lib/api-client";
import { toast } from "sonner";

export const Route = createFileRoute("/app/prescriptions")({
  head: () => ({ meta: [{ title: "Prescriptions — CliniXAI" }, { name: "robots", content: "noindex" }] }),
  component: PrescriptionsPage,
});

interface PrescriptionItem {
  prescription_id: string;
  consultation_id: string;
  appointment_id?: string;
  patient_id?: string;
  doctor_id?: string;
  medications: Array<{
    name: string;
    dosage: string;
    frequency: string;
    duration: string;
    route?: string;
    instructions?: string;
  }>;
  instructions?: string;
  status: "active" | "issued" | "cancelled" | "draft";
  prescription_date?: string;
  issued_at?: string;
  issued_by?: string;
  created_at?: string;
}

function PrescriptionsPage() {
  const isDetail = useMatch({ from: "/app/prescriptions/$id", shouldThrow: false });

  const { user } = useAuth();
  const [prescriptions, setPrescriptions] = useState<PrescriptionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<"all" | "active" | "cancelled">("all");

  const fetchPrescriptions = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiClient.prescriptions.list();
      const items = Array.isArray(res?.data)
        ? res.data
        : Array.isArray(res?.items)
        ? res.items
        : Array.isArray(res)
        ? res
        : [];
      setPrescriptions(items);
    } catch (err: any) {
      const msg = err?.message || "Failed to load prescriptions from clinical server.";
      setError(msg);
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPrescriptions();
  }, [user?.role]);

  const filtered = useMemo(() => {
    if (statusFilter === "all") return prescriptions;
    if (statusFilter === "active") {
      return prescriptions.filter((p) => p.status === "active" || p.status === "issued");
    }
    return prescriptions.filter((p) => p.status === "cancelled");
  }, [prescriptions, statusFilter]);

  if (isDetail) {
    return <Outlet />;
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <PageHeader
          title="Clinical Prescriptions"
          description={
            user?.role === "patient"
              ? "Official digital prescriptions issued by your attending CliniXAI healthcare providers."
              : "Prescription records issued across clinical encounters."
          }
        />
        <Button variant="outline" size="sm" onClick={fetchPrescriptions} disabled={loading} className="gap-1.5">
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} /> Refresh
        </Button>
      </div>

      <div className="flex items-center gap-3">
        <Tabs value={statusFilter} onValueChange={(v: any) => setStatusFilter(v)}>
          <TabsList>
            <TabsTrigger value="all">All ({prescriptions.length})</TabsTrigger>
            <TabsTrigger value="active">
              Active ({prescriptions.filter((p) => p.status === "active" || p.status === "issued").length})
            </TabsTrigger>
            <TabsTrigger value="cancelled">
              Cancelled ({prescriptions.filter((p) => p.status === "cancelled").length})
            </TabsTrigger>
          </TabsList>
        </Tabs>
      </div>

      {loading ? (
        <Card className="border-border/60">
          <CardContent className="p-16 text-center text-muted-foreground flex flex-col items-center justify-center gap-3">
            <RefreshCw className="h-7 w-7 animate-spin text-primary" />
            <p className="text-sm font-medium text-foreground">Loading prescriptions from clinical repository…</p>
          </CardContent>
        </Card>
      ) : error ? (
        <Card className="border-destructive/40 bg-destructive/5">
          <CardContent className="p-8 text-center space-y-3">
            <AlertCircle className="h-8 w-8 text-destructive mx-auto" />
            <p className="font-semibold text-destructive">{error}</p>
            <Button variant="outline" size="sm" onClick={fetchPrescriptions}>
              Retry
            </Button>
          </CardContent>
        </Card>
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={Pill}
          title={statusFilter === "all" ? "No prescriptions found" : `No ${statusFilter} prescriptions`}
          description={
            user?.role === "patient"
              ? "Prescriptions issued by your physician during consultations will appear here."
              : "No prescriptions match the selected status filter."
          }
        />
      ) : (
        <div className="grid gap-3">
          {filtered.map((rx) => {
            const isActive = rx.status === "active" || rx.status === "issued";
            const dateStr = rx.prescription_date || (rx.created_at ? new Date(rx.created_at).toLocaleDateString() : "—");
            const medNames = rx.medications?.map((m) => m.name).join(", ") || "No medications specified";

            return (
              <Card key={rx.prescription_id} className="card-hover border-border/70 hover:border-primary/50 transition-colors">
                <CardContent className="p-4 sm:p-5">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div className="min-w-0 space-y-1.5">
                      <div className="flex items-center gap-2">
                        <span className="font-display text-base font-bold text-foreground tracking-tight">
                          {rx.prescription_id}
                        </span>
                        <Badge
                          variant="outline"
                          className={
                            isActive
                              ? "border-success/40 bg-success/10 text-success text-[10px] uppercase font-semibold"
                              : "border-muted-foreground/40 bg-muted/20 text-muted-foreground text-[10px] uppercase font-semibold"
                          }
                        >
                          {isActive ? (
                            <span className="flex items-center gap-1">
                              <CheckCircle2 className="h-3 w-3" /> Active
                            </span>
                          ) : (
                            <span className="flex items-center gap-1">
                              <XCircle className="h-3 w-3" /> Cancelled
                            </span>
                          )}
                        </Badge>
                      </div>

                      <p className="text-sm font-medium text-foreground line-clamp-1">
                        <span className="text-muted-foreground">Medications: </span>
                        {medNames}
                      </p>

                      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground pt-1">
                        <span className="flex items-center gap-1">
                          <User className="h-3 w-3" /> Doctor: {rx.issued_by || rx.doctor_id}
                        </span>
                        <span className="flex items-center gap-1">
                          <Calendar className="h-3 w-3" /> Date: {dateStr}
                        </span>
                        <span>
                          {rx.medications?.length || 0} item{rx.medications?.length !== 1 ? "s" : ""}
                        </span>
                        {rx.consultation_id && (
                          <span className="text-muted-foreground">
                            Encounter: {rx.consultation_id}
                          </span>
                        )}
                      </div>
                    </div>

                    <div className="flex items-center gap-2 self-end sm:self-center">
                      <Button asChild size="sm" variant="outline" className="gap-1.5 shadow-sm">
                        <Link to="/app/prescriptions/$id" params={{ id: rx.prescription_id }}>
                          <Eye className="h-3.5 w-3.5" /> View Prescription
                        </Link>
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}

