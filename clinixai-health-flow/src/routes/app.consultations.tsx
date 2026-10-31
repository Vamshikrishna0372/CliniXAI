import { useEffect, useMemo, useState } from "react";
import { createFileRoute, Link, useNavigate, Outlet, useMatch } from "@tanstack/react-router";
import { Search, Stethoscope, RefreshCw, AlertCircle, Clock, CheckCircle2, User, ArrowRight } from "lucide-react";
import { PageHeader } from "@/components/app-shell/page-header";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/dashboard/states";
import { AppointmentBadge } from "@/components/domain/status-badge";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import { toast } from "sonner";

export const Route = createFileRoute("/app/consultations")({
  head: () => ({ meta: [{ title: "Consultations — CliniXAI" }, { name: "robots", content: "noindex" }] }),
  component: ConsultationsPage,
});

const TABS = ["all", "in-progress", "completed"] as const;
type Tab = (typeof TABS)[number];

interface ConsultationItem {
  consultation_id: string;
  appointment_id: string;
  patient_id: string;
  doctor_id: string;
  department_id: string;
  status: "in_progress" | "completed" | "cancelled";
  chief_complaint?: {
    complaint?: string;
    duration?: string;
    description?: string;
  } | null;
  started_at?: string;
  completed_at?: string;
  created_at: string;
  patient_name?: string;
}

function ConsultationsPage() {
  const isChild = useMatch({ from: "/app/consultations/$id", shouldThrow: false });

  const { user } = useAuth();
  const navigate = useNavigate();
  const [tab, setTab] = useState<Tab>("all");
  const [q, setQ] = useState("");
  const [consultations, setConsultations] = useState<ConsultationItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchConsultations = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiClient.consultations.list();
      // res can be PaginatedResponse: { data: [...] } or direct array
      const items = Array.isArray(res?.data) ? res.data : Array.isArray(res) ? res : [];
      setConsultations(items);
    } catch (err: any) {
      setError(err?.message || "Failed to load consultations");
      toast.error("Could not fetch consultations from server");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchConsultations();
  }, []);

  const filtered = useMemo(() => {
    return consultations.filter((c) => {
      const status = (c.status || "").toLowerCase();
      if (tab === "in-progress" && status !== "in_progress") return false;
      if (tab === "completed" && status !== "completed") return false;

      if (q.trim()) {
        const query = q.toLowerCase();
        const complaint = c.chief_complaint?.complaint?.toLowerCase() || "";
        const cId = c.consultation_id?.toLowerCase() || "";
        const aptId = c.appointment_id?.toLowerCase() || "";
        const pId = c.patient_id?.toLowerCase() || "";
        const matches = cId.includes(query) || aptId.includes(query) || pId.includes(query) || complaint.includes(query);
        if (!matches) return false;
      }
      return true;
    });
  }, [consultations, tab, q]);

  if (isChild) {
    return <Outlet />;
  }

  const openConsultation = (item: ConsultationItem) => {
    navigate({ to: "/app/consultations/$id", params: { id: item.consultation_id || item.appointment_id } });
  };

  const formatDate = (isoString?: string) => {
    if (!isoString) return "—";
    try {
      const d = new Date(isoString);
      return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
    } catch {
      return isoString;
    }
  };

  const formatTime = (isoString?: string) => {
    if (!isoString) return "";
    try {
      const d = new Date(isoString);
      return d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
    } catch {
      return "";
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Clinical Consultations"
        description={
          user?.role === "doctor"
            ? "Doctor clinical encounters, patient assessments, and diagnostic documentation."
            : "Review authorized clinical encounters and diagnostic summaries."
        }
        actions={
          <Button variant="outline" size="sm" onClick={fetchConsultations} disabled={loading} className="gap-1.5">
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} /> Refresh
          </Button>
        }
      />

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <Tabs value={tab} onValueChange={(v) => setTab(v as Tab)} className="w-full sm:w-auto">
          <TabsList className="grid w-full grid-cols-3 sm:w-auto">
            {TABS.map((t) => (
              <TabsTrigger key={t} value={t} className="capitalize">
                {t.replace("-", " ")}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search by consultation ID, appointment, or complaint…"
            className="pl-9"
            aria-label="Search consultations"
          />
        </div>
      </div>

      {loading ? (
        <Card className="border-border/60">
          <CardContent className="p-12 text-center text-muted-foreground flex flex-col items-center justify-center gap-3">
            <RefreshCw className="h-6 w-6 animate-spin text-primary" />
            <p className="text-sm font-medium">Loading clinical consultations from database…</p>
          </CardContent>
        </Card>
      ) : error ? (
        <Card className="border-destructive/40 bg-destructive/5">
          <CardContent className="p-8 text-center flex flex-col items-center justify-center gap-3">
            <AlertCircle className="h-8 w-8 text-destructive" />
            <p className="text-sm font-semibold text-destructive">{error}</p>
            <Button size="sm" variant="outline" onClick={fetchConsultations}>
              Retry Connection
            </Button>
          </CardContent>
        </Card>
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={Stethoscope}
          title="No consultations found"
          description={
            q ? "No records match your active search filter." : "There are no consultation encounters in this view."
          }
        />
      ) : (
        <Card className="border-border/60 shadow-sm overflow-hidden">
          <CardContent className="p-0">
            <ul className="divide-y divide-border">
              {filtered.map((c) => {
                const isInProgress = c.status === "in_progress";
                const isCompleted = c.status === "completed";
                const complaintText = c.chief_complaint?.complaint || "Clinical Examination";

                return (
                  <li
                    key={c.consultation_id}
                    className="grid grid-cols-1 gap-3 p-4 sm:grid-cols-[140px_1fr_1.5fr_130px_auto] sm:items-center hover:bg-muted/40 transition-colors"
                  >
                    <div>
                      <span className="font-mono text-xs font-semibold text-primary block">{c.consultation_id}</span>
                      <p className="text-xs text-muted-foreground flex items-center gap-1 mt-0.5">
                        <Clock className="h-3 w-3" />
                        {formatDate(c.started_at || c.created_at)} {formatTime(c.started_at || c.created_at)}
                      </p>
                    </div>

                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium flex items-center gap-1.5">
                        <User className="h-3.5 w-3.5 text-muted-foreground" />
                        <span>{c.patient_id}</span>
                      </p>
                      <p className="truncate text-xs text-muted-foreground">Appt: {c.appointment_id}</p>
                    </div>

                    <div className="min-w-0">
                      <p className="truncate text-sm text-foreground font-medium">{complaintText}</p>
                      <p className="truncate text-xs text-muted-foreground">
                        Doctor: {c.doctor_id} · Dept: {c.department_id || "Clinical"}
                      </p>
                    </div>

                    <div>
                      <AppointmentBadge status={c.status} />
                    </div>

                    <div className="flex flex-wrap gap-2 sm:justify-end">
                      {isCompleted ? (
                        <Button
                          asChild
                          size="sm"
                          variant="outline"
                          className="gap-1 border-primary/20 hover:bg-primary/5"
                        >
                          <Link to="/app/consultations/$id" params={{ id: c.consultation_id }}>
                            View Summary <ArrowRight className="h-3.5 w-3.5" />
                          </Link>
                        </Button>
                      ) : (
                        <Button
                          size="sm"
                          onClick={() => openConsultation(c)}
                          className="gap-1 bg-primary hover:bg-primary/90 text-primary-foreground shadow-sm"
                        >
                          <Stethoscope className="h-3.5 w-3.5" /> Open Workspace
                        </Button>
                      )}
                    </div>
                  </li>
                );
              })}
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
