import { useState, useEffect, useCallback, useMemo } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import {
  Activity, Users, Calendar, Brain, ReceiptText, FileText, TrendingUp, Stethoscope,
  UserPlus, ListOrdered, CalendarClock, Pill, Building2, BarChart3, CheckCircle2,
  Clock, AlertTriangle, ArrowRight, RefreshCw,
} from "lucide-react";
import { PageHeader } from "@/components/app-shell/page-header";
import { ResponsiveGrid, KpiCard, InfoCard, QuickActionCard, ListCard } from "@/components/dashboard/cards";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useAuth } from "@/lib/auth-context";
import { ROLE_LABEL } from "@/lib/roles";
import { useClinix } from "@/lib/store/clinix-store";
import { billTotal, inr, fmtDateTime, todayIso } from "@/lib/mock/domain";
import { apiClient } from "@/lib/api-client";

export const Route = createFileRoute("/app/")({
  head: () => ({ meta: [{ title: "Dashboard — CliniXAI" }] }),
  component: DashboardPage,
});

function DashboardPage() {
  const { user } = useAuth();
  if (!user) return null;
  if (user.role === "admin") return <AdminDashboard firstName={user.firstName} />;
  if (user.role === "doctor") return <DoctorDashboard user={user} />;
  if (user.role === "staff") return <StaffDashboard firstName={user.firstName} />;
  return <PatientDashboard user={user} />;
}

function DoctorDashboard({ user }: { user: any }) {
  const { doctors } = useClinix();
  const doctor = doctors.find((d) => d.email === user.email || d.id === user.id);
  const docId = user?.doctorId || (doctor ? doctor.id : user.id);
  const today = todayIso();

  const [liveApts, setLiveApts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const res: any = await apiClient.appointments.list({ page_size: 50 });
      if (res && res.data) {
        const items = Array.isArray(res.data) ? res.data : res.data.items || [];
        setLiveApts(items);
      }
    } catch (err) {
      console.warn("Could not load doctor appointments:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Derived metrics from real appointments
  const todaysApts = useMemo(() => {
    return liveApts.filter((a) => {
      const d = a.appointment_date || a.date;
      return d === today;
    });
  }, [liveApts, today]);

  const uniquePatients = useMemo(() => {
    const ids = new Set(liveApts.map((a) => a.patient_id || a.patientId).filter(Boolean));
    return ids.size;
  }, [liveApts]);

  const completedCount = useMemo(() => {
    return liveApts.filter((a) => (a.status || "").toLowerCase() === "completed").length;
  }, [liveApts]);

  const upcomingCount = useMemo(() => {
    return liveApts.filter((a) => {
      const s = (a.status || "").toLowerCase();
      return s === "scheduled" || s === "confirmed" || s === "in-queue" || s === "checked-in";
    }).length;
  }, [liveApts]);

  const kpis = [
    { label: "Today's Appointments", value: todaysApts.length, icon: Calendar, loading },
    { label: "Active Patients", value: uniquePatients, icon: Users, loading },
    { label: "Upcoming / Scheduled", value: upcomingCount, icon: Clock, loading },
    { label: "Completed Encounters", value: completedCount, icon: CheckCircle2, loading },
  ];

  const quick = [
    { label: "All Appointments", description: "Manage clinical appointments", icon: Calendar, to: "/app/appointments" },
    { label: "My Patients", description: "Search & view clinical workspace", icon: Users, to: "/app/patients" },
    { label: "Consultations", description: "Open consultation sessions", icon: Stethoscope, to: "/app/consultations" },
    { label: "Prescriptions", description: "Review and issue medications", icon: Pill, to: "/app/prescriptions" },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title={`Welcome back, Dr. ${user.lastName || user.firstName}`}
        description={`${ROLE_LABEL.doctor} • Clinical Dashboard & Patient Care Hub.`}
        actions={
          <Button variant="outline" size="sm" onClick={loadData} disabled={loading}>
            <RefreshCw className={`mr-1.5 h-4 w-4 ${loading ? "animate-spin" : ""}`} /> Refresh
          </Button>
        }
      />

      <ResponsiveGrid cols={{ base: 1, sm: 2, lg: 4 }}>
        {kpis.map((k) => (
          <KpiCard key={k.label} {...k} />
        ))}
      </ResponsiveGrid>

      <QuickActions items={quick} />

      {/* Today's Schedule Card */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-3">
          <div>
            <CardTitle className="text-base font-semibold">Today's Clinical Schedule</CardTitle>
            <CardDescription className="text-xs">
              {todaysApts.length > 0
                ? `${todaysApts.length} patient${todaysApts.length === 1 ? "" : "s"} scheduled for today (${today})`
                : `No appointments scheduled for today (${today})`}
            </CardDescription>
          </div>
          <Button asChild variant="ghost" size="sm">
            <Link to="/app/appointments">
              View All <ArrowRight className="ml-1 h-3.5 w-3.5" />
            </Link>
          </Button>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center justify-center p-8 text-sm text-muted-foreground">
              <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> Loading schedule...
            </div>
          ) : todaysApts.length === 0 ? (
            <div className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">
              No appointments scheduled for today. Check{" "}
              <Link to="/app/appointments" className="text-primary underline">
                All Appointments
              </Link>{" "}
              for upcoming patient visits.
            </div>
          ) : (
            <ul className="divide-y divide-border">
              {todaysApts.map((apt: any) => {
                const patId = apt.patient_id || apt.patientId;
                const aptId = apt.appointment_id || apt.id;
                const patName = apt.patient_name || apt.patientName || patId;
                const time = apt.start_time || apt.appointment_time || "09:00";
                const status = apt.status || "scheduled";
                const reason = apt.reason_for_visit || apt.reason || "Routine Consultation";

                return (
                  <li key={aptId} className="flex flex-wrap items-center justify-between gap-3 py-3">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <Link
                          to="/app/patients/$id"
                          params={{ id: patId }}
                          className="font-medium text-primary hover:underline"
                        >
                          {patName}
                        </Link>
                        <Badge variant="outline" className="text-[10px] font-mono">
                          {patId}
                        </Badge>
                      </div>
                      <p className="text-xs text-muted-foreground">
                        {time} • {reason} • Apt ID: {aptId}
                      </p>
                    </div>

                    <div className="flex items-center gap-2">
                      <Badge variant="secondary" className="capitalize text-xs">
                        {status.replace(/_/g, " ")}
                      </Badge>
                      <Button asChild size="sm" variant="outline">
                        <Link to="/app/patients/$id" params={{ id: patId }}>
                          Clinical Workspace
                        </Link>
                      </Button>
                      <Button asChild size="sm" variant="ghost">
                        <Link to="/app/appointments/$id" params={{ id: aptId }}>
                          Details
                        </Link>
                      </Button>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function StaffDashboard({ firstName }: { firstName: string }) {
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<any>(null);

  const loadData = useCallback(async () => {
    try {
      const res = await apiClient.staff.getDashboardOverview();
      if (res && res.data) {
        setData(res.data);
      }
    } catch (err) {
      console.warn("Could not fetch staff dashboard overview:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
    const onFocus = () => loadData();
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, [loadData]);

  const metrics = data?.metrics || {
    today_appointments: 0,
    waiting_patients: 0,
    checked_in_today: 0,
    completed_consultations: 0,
    pending_bills: 0,
    today_collected_amount: 0,
    total_registered_patients: 0,
  };

  const kpis = [
    { label: "Today's Appointments", value: metrics.today_appointments, icon: Calendar, loading },
    { label: "Waiting in Queue", value: metrics.waiting_patients, icon: ListOrdered, loading },
    { label: "Checked-In Today", value: metrics.checked_in_today, icon: Activity, loading },
    { label: "Completed Visits", value: metrics.completed_consultations, icon: CheckCircle2, loading },
    { label: "Pending Bills", value: metrics.pending_bills, icon: ReceiptText, loading },
    { label: "Today's Revenue", value: `₹${Number(metrics.today_collected_amount || 0).toLocaleString("en-IN")}`, icon: TrendingUp, loading },
  ];

  const quick = [
    { label: "Register Patient", description: "New patient intake", icon: UserPlus, to: "/app/patient-registration" },
    { label: "Patient Check-In", description: "Verify arrival & assign token", icon: Activity, to: "/app/check-in" },
    { label: "Live Queue", description: "Realtime patient queue flow", icon: ListOrdered, to: "/app/queue" },
    { label: "Billing & Cashier", description: "Record payments & receipts", icon: ReceiptText, to: "/app/billing" },
    { label: "Patient Directory", description: "Search & view patient records", icon: Users, to: "/app/patients" },
    { label: "Daily Schedule", description: "View and filter appointments", icon: CalendarClock, to: "/app/appointments" },
  ];

  const queueItems = data?.active_queue || [];
  const upcoming = data?.upcoming_appointments || [];
  const alerts = data?.operational_alerts || [];
  const activity = data?.recent_activity || [];

  return (
    <div className="space-y-6">
      <PageHeader
        title={`Welcome back, ${firstName}`}
        description={`${ROLE_LABEL.staff} • Front Desk & Operational Workflow Hub.`}
        actions={
          <Button variant="outline" size="sm" onClick={() => { setLoading(true); loadData(); }} disabled={loading}>
            <RefreshCw className={`mr-1.5 h-4 w-4 ${loading ? "animate-spin" : ""}`} /> Refresh
          </Button>
        }
      />

      {alerts.length > 0 && (
        <div className="space-y-2">
          {alerts.map((al: any, idx: number) => (
            <div
              key={idx}
              className={`flex items-center gap-3 rounded-lg border p-3 text-sm ${
                al.severity === "warning"
                  ? "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300"
                  : "border-blue-500/30 bg-blue-500/10 text-blue-700 dark:text-blue-300"
              }`}
            >
              <AlertTriangle className="h-4 w-4 shrink-0" />
              <div className="flex-1">
                <span className="font-semibold">{al.title}: </span>
                <span>{al.message}</span>
              </div>
            </div>
          ))}
        </div>
      )}

      <ResponsiveGrid cols={{ base: 1, sm: 2, lg: 3, xl: 6 }}>
        {kpis.map((k) => (
          <KpiCard key={k.label} {...k} />
        ))}
      </ResponsiveGrid>

      <QuickActions items={quick} />

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Active Live Queue */}
        <Card className="flex flex-col">
          <CardHeader className="flex flex-row items-center justify-between pb-3">
            <div>
              <CardTitle className="text-base font-semibold">Active Queue</CardTitle>
              <CardDescription className="text-xs">Checked-in patients waiting for doctor</CardDescription>
            </div>
            <Button asChild variant="ghost" size="sm">
              <Link to="/app/queue">
                View Queue <ArrowRight className="ml-1 h-3.5 w-3.5" />
              </Link>
            </Button>
          </CardHeader>
          <CardContent className="flex-1">
            {queueItems.length === 0 ? (
              <div className="flex h-36 flex-col items-center justify-center text-center text-muted-foreground">
                <ListOrdered className="mb-2 h-8 w-8 text-muted-foreground/40" />
                <p className="text-sm font-medium">No waiting patients</p>
                <p className="text-xs">Checked-in patients will appear here immediately</p>
              </div>
            ) : (
              <ul className="divide-y divide-border">
                {queueItems.slice(0, 5).map((qItem: any) => (
                  <li key={qItem.appointment_id} className="flex items-center justify-between py-2.5">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="rounded bg-primary/10 px-1.5 py-0.5 font-mono text-xs font-bold text-primary">
                          {qItem.token_number}
                        </span>
                        <span className="text-sm font-medium">{qItem.patient_name || qItem.patient_id}</span>
                      </div>
                      <p className="text-xs text-muted-foreground">
                        Dr. {qItem.doctor_name || qItem.doctor_id} • Pos #{qItem.position}
                      </p>
                    </div>
                    <Badge variant={qItem.status === "in_consultation" ? "default" : "outline"} className="capitalize text-xs">
                      {qItem.status.replace("_", " ")}
                    </Badge>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        {/* Upcoming Appointments Today */}
        <Card className="flex flex-col">
          <CardHeader className="flex flex-row items-center justify-between pb-3">
            <div>
              <CardTitle className="text-base font-semibold">Today's Schedule</CardTitle>
              <CardDescription className="text-xs">Upcoming scheduled visits</CardDescription>
            </div>
            <Button asChild variant="ghost" size="sm">
              <Link to="/app/appointments">
                Calendar <ArrowRight className="ml-1 h-3.5 w-3.5" />
              </Link>
            </Button>
          </CardHeader>
          <CardContent className="flex-1">
            {upcoming.length === 0 ? (
              <div className="flex h-36 flex-col items-center justify-center text-center text-muted-foreground">
                <Calendar className="mb-2 h-8 w-8 text-muted-foreground/40" />
                <p className="text-sm font-medium">No upcoming appointments</p>
                <p className="text-xs">All scheduled visits for today are handled or complete</p>
              </div>
            ) : (
              <ul className="divide-y divide-border">
                {upcoming.slice(0, 5).map((apt: any) => (
                  <li key={apt.appointment_id} className="flex items-center justify-between py-2.5">
                    <div>
                      <p className="text-sm font-medium">{apt.patient_name || apt.patient_id}</p>
                      <p className="text-xs text-muted-foreground">
                        {apt.appointment_time} • Dr. {apt.doctor_name || apt.doctor_id}
                      </p>
                    </div>
                    <Button asChild size="sm" variant="outline">
                      <Link to="/app/check-in">Check In</Link>
                    </Button>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>

      {activity.length > 0 && (
        <ListCard
          title="Recent Operational Activity"
          action={
            <Button asChild variant="ghost" size="sm">
              <Link to="/app/activity-logs">View all</Link>
            </Button>
          }
          items={activity.map((a: any, i: number) => ({
            id: a.id || String(i),
            primary: `${a.action || "Activity"} · ${a.details || ""}`,
            secondary: a.actor || "Staff",
            meta: a.timestamp ? fmtDateTime(a.timestamp) : "Recent",
          }))}
        />
      )}
    </div>
  );
}

function PatientDashboard({ user }: { user: any }) {
  const { appointments, aiReports, prescriptions, bills, patients } = useClinix();
  const patient = patients.find((p) => p.email === user.email || p.id === user.id || p.id === user.patientId);
  const patId = user?.patientId || patient?.id || user.id;

  const mine = appointments.filter((a) => a.patientId === patId || a.patientId === user.id || (user.patientId && a.patientId === user.patientId));
  const upcoming = mine.filter((a) => ["confirmed", "scheduled", "checked-in", "in-queue"].includes(a.status)).length;
  const myAi = aiReports.filter((r) => r.patientId === patId || r.patientId === user.id || (user.patientId && r.patientId === user.patientId)).length;
  const myRx = prescriptions.filter((p) => p.patientId === patId || p.patientId === user.id || (user.patientId && p.patientId === user.patientId)).length;
  const pendingBills = bills.filter((b) => (b.patientId === patId || b.patientId === user.id || (user.patientId && b.patientId === user.patientId)) && b.status === "pending").length;

  const kpis = [
    { label: "Upcoming Appointments", value: upcoming, icon: CalendarClock },
    { label: "AI Reports", value: myAi, icon: Brain },
    { label: "Active Prescriptions", value: myRx, icon: Pill },
    { label: "Pending Bills", value: pendingBills, icon: ReceiptText },
  ];
  const quick = [
    { label: "Book Appointment", description: "Find the right doctor", icon: Calendar, to: "/app/book" },
    { label: "View Records", description: "Your medical history", icon: FileText, to: "/app/medical-records" },
    { label: "AI Reports", description: "Explainable insights", icon: Brain, to: "/app/ai-reports" },
  ];

  return (
    <div className="space-y-6">
      <PageHeader title={`Welcome back, ${user.firstName}`} description={`${ROLE_LABEL.patient} • Here's what's happening today.`} status={{ label: "All systems normal", tone: "success" }} />
      <ResponsiveGrid cols={{ base: 1, sm: 2, lg: 4 }}>{kpis.map((k) => <KpiCard key={k.label} {...k} />)}</ResponsiveGrid>
      <QuickActions items={quick} />
      <InfoCard icon={Activity} title="Your CliniXAI workspace" description="Use the sidebar or ⌘K to jump to any module." />
    </div>
  );
}

function QuickActions({ items }: { items: { label: string; description: string; icon: React.ComponentType<{ className?: string }>; to: string }[] }) {
  return (
    <section>
      <h2 className="mb-3 font-display text-sm font-semibold uppercase tracking-wide text-muted-foreground">Quick actions</h2>
      <ResponsiveGrid cols={{ base: 1, sm: 2, lg: 3 }}>
        {items.map((q) => (
          <Link key={q.label} to={q.to}>
            <QuickActionCard label={q.label} description={q.description} icon={q.icon} />
          </Link>
        ))}
      </ResponsiveGrid>
    </section>
  );
}

function AdminDashboard({ firstName }: { firstName: string }) {
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<any>(null);

  const loadData = useCallback(async () => {
    try {
      const res = await apiClient.admin.getDashboardOverview();
      if (res && res.data) {
        setData(res.data);
      }
    } catch (err) {
      console.warn("Could not fetch admin dashboard overview:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
    const onFocus = () => loadData();
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, [loadData]);

  const metrics = data || {
    total_patients: 0,
    active_doctors: 0,
    total_doctors: 0,
    active_staff: 0,
    total_staff: 0,
    active_users: 0,
    disabled_users: 0,
    password_setup_required_users: 0,
    today_appointments: 0,
    today_completed_consultations: 0,
    waiting_patients: 0,
    pending_appointments: 0,
    cancelled_appointments: 0,
    pending_bills: 0,
    collected_revenue: 0,
    today_revenue: 0,
    recent_activity: [],
    operational_alerts: [],
    system_status: "operational",
  };

  const availableDocs = Math.max(0, metrics.active_doctors - (metrics.today_completed_consultations > 0 ? 0 : 0));
  const alerts = metrics.operational_alerts || [];
  const activity = metrics.recent_activity || [];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Admin Operations Center"
        description={`Welcome back, ${firstName}. Hospital Overview • Monitor operations, clinical activity, and system health.`}
        status={{ label: metrics.system_status === "operational" ? "Operational" : "Degraded", tone: "success" }}
        actions={
          <Button variant="outline" size="sm" onClick={() => { setLoading(true); loadData(); }} disabled={loading}>
            <RefreshCw className={`mr-1.5 h-4 w-4 ${loading ? "animate-spin" : ""}`} /> Refresh
          </Button>
        }
      />

      {alerts.length > 0 && (
        <div className="space-y-2">
          {alerts.map((al: any, idx: number) => (
            <div
              key={idx}
              className={`flex items-center gap-3 rounded-lg border p-3 text-sm ${
                al.severity === "warning"
                  ? "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300"
                  : "border-blue-500/30 bg-blue-500/10 text-blue-700 dark:text-blue-300"
              }`}
            >
              <AlertTriangle className="h-4 w-4 shrink-0" />
              <div className="flex-1">
                <span className="font-semibold">{al.title}: </span>
                <span>{al.message}</span>
              </div>
            </div>
          ))}
        </div>
      )}

      <ResponsiveGrid cols={{ base: 1, sm: 2, lg: 4 }}>
        <KpiCard
          label="Today's Appointments"
          value={metrics.today_appointments}
          icon={Calendar}
          delta={`${metrics.today_completed_consultations} completed`}
          trend="up"
          loading={loading}
        />
        <KpiCard
          label="Patients in Queue"
          value={metrics.waiting_patients}
          icon={CheckCircle2}
          delta={`${metrics.pending_appointments} pending`}
          loading={loading}
        />
        <KpiCard
          label="Active Doctors"
          value={`${metrics.active_doctors} / ${metrics.total_doctors}`}
          icon={Stethoscope}
          delta={`${metrics.active_staff} active staff`}
          loading={loading}
        />
        <KpiCard
          label="Pending Invoices"
          value={metrics.pending_bills}
          icon={ReceiptText}
          delta={`₹${Number(metrics.collected_revenue || 0).toLocaleString("en-IN")} collected`}
          trend="up"
          loading={loading}
        />
      </ResponsiveGrid>

      <ResponsiveGrid cols={{ base: 1, sm: 3 }}>
        <KpiCard
          label="Active System Users"
          value={metrics.active_users}
          icon={Users}
          delta={`${metrics.disabled_users} disabled`}
          loading={loading}
        />
        <KpiCard
          label="Total Registered Patients"
          value={metrics.total_patients}
          icon={Activity}
          loading={loading}
        />
        <KpiCard
          label="Today's Collected Revenue"
          value={`₹${Number(metrics.today_revenue || 0).toLocaleString("en-IN")}`}
          icon={TrendingUp}
          trend="up"
          loading={loading}
        />
      </ResponsiveGrid>

      <ResponsiveGrid cols={{ base: 1, lg: 2 }}>
        <Card>
          <CardContent className="p-5">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <p className="font-display text-base font-semibold">Today's Operations</p>
                <p className="text-xs text-muted-foreground">Live view of appointment and queue status.</p>
              </div>
              <Button asChild variant="ghost" size="sm"><Link to="/app/appointments">View all</Link></Button>
            </div>
            <ul className="space-y-2 text-sm">
              <OpsRow label="Today's Total Appointments" value={metrics.today_appointments} icon={Calendar} />
              <OpsRow label="Waiting in Queue" value={metrics.waiting_patients} icon={Clock} />
              <OpsRow label="Completed Consultations" value={metrics.today_completed_consultations} icon={CheckCircle2} />
              <OpsRow label="Pending Scheduled Visits" value={metrics.pending_appointments} icon={CalendarClock} />
              <OpsRow label="Cancelled / No-Show" value={metrics.cancelled_appointments} icon={AlertTriangle} />
              <OpsRow label="Pending Invoices" value={metrics.pending_bills} icon={ReceiptText} />
            </ul>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-5">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <p className="font-display text-base font-semibold">Live Hospital Status</p>
                <p className="text-xs text-muted-foreground">Authoritative clinical and staff metrics.</p>
              </div>
              <span className="flex items-center gap-1.5 text-xs text-success">
                <span className="h-2 w-2 animate-pulse rounded-full bg-success" /> Live
              </span>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <StatusTile label="Doctors Active" value={metrics.active_doctors} tone="success" />
              <StatusTile label="Hospital Staff Active" value={metrics.active_staff} tone="info" />
              <StatusTile label="Waiting Patients" value={metrics.waiting_patients} tone="info" />
              <StatusTile label="Pending Invoices" value={metrics.pending_bills} tone="warning" />
              <StatusTile label="Disabled Accounts" value={metrics.disabled_users} tone="warning" />
              <StatusTile label="Setup Required" value={metrics.password_setup_required_users} tone="info" />
            </div>
          </CardContent>
        </Card>
      </ResponsiveGrid>

      <section>
        <h2 className="mb-3 font-display text-sm font-semibold uppercase tracking-wide text-muted-foreground">Quick actions</h2>
        <ResponsiveGrid cols={{ base: 1, sm: 2, lg: 3 }}>
          <Link to="/app/doctors"><QuickActionCard label="Add Doctor" description="Onboard a clinician" icon={Stethoscope} /></Link>
          <Link to="/app/staff"><QuickActionCard label="Add Hospital Staff" description="Register a new staff member" icon={UserPlus} /></Link>
          <Link to="/app/users"><QuickActionCard label="User Accounts" description="Manage system access & roles" icon={Users} /></Link>
          <Link to="/app/appointments"><QuickActionCard label="Today's Appointments" description="Operational calendar" icon={Calendar} /></Link>
          <Link to="/app/reports"><QuickActionCard label="View Reports" description="Generate operational reports" icon={FileText} /></Link>
          <Link to="/app/analytics"><QuickActionCard label="Open Analytics" description="Hospital-wide insights" icon={BarChart3} /></Link>
        </ResponsiveGrid>
      </section>

      {activity.length > 0 && (
        <ListCard
          title="Recent Administrative Activity"
          action={<Button asChild variant="ghost" size="sm"><Link to="/app/activity-logs">View all</Link></Button>}
          items={activity.map((a: any, idx: number) => ({
            id: a.audit_id || String(idx),
            primary: `${a.action || "Action"} · ${a.resource || ""}${a.resource_id ? " (" + a.resource_id + ")" : ""}`,
            secondary: `${a.actor_id || "System"} (${a.role || "Admin"})`,
            meta: a.timestamp ? fmtDateTime(a.timestamp) : "Recent",
          }))}
        />
      )}
    </div>
  );
}

function OpsRow({ label, value, icon: Icon }: { label: string; value: number; icon: React.ComponentType<{ className?: string }> }) {
  return (
    <li className="flex items-center justify-between rounded-lg border border-border bg-muted/30 px-3 py-2">
      <span className="flex items-center gap-2 text-sm text-foreground"><Icon className="h-4 w-4 text-muted-foreground" /> {label}</span>
      <span className="font-display text-base font-bold text-foreground">{value}</span>
    </li>
  );
}

function StatusTile({ label, value, tone }: { label: string; value: number; tone: "success" | "warning" | "info" }) {
  const toneCls = {
    success: "border-success/20 bg-success/5",
    warning: "border-warning/20 bg-warning/5",
    info: "border-primary/20 bg-primary/5",
  }[tone];
  return (
    <div className={`rounded-xl border ${toneCls} p-3`}>
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 font-display text-xl font-bold text-foreground">{value}</p>
    </div>
  );
}
