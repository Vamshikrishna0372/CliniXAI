import { useMemo, useState, useEffect, useCallback } from "react";
import { createFileRoute, Link, Outlet, useMatch } from "@tanstack/react-router";
import { Search, Plus, RotateCw, Loader2, Calendar, AlertCircle } from "lucide-react";
import { PageHeader } from "@/components/app-shell/page-header";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { AppointmentCard } from "@/components/domain/appointment-card";
import { EmptyState } from "@/components/dashboard/states";
import { AppointmentBadge } from "@/components/domain/status-badge";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/lib/auth-context";
import { fmtDate, type Appointment } from "@/lib/mock/domain";
import { useClinix } from "@/lib/store/clinix-store";
import { toast } from "sonner";

export const Route = createFileRoute("/app/appointments")({
  head: () => ({ meta: [{ title: "Appointments — CliniXAI" }, { name: "robots", content: "noindex" }] }),
  component: AppointmentsPage,
});

const TABS = ["upcoming", "today", "completed", "cancelled", "all"] as const;
type Tab = (typeof TABS)[number];

function getTodayString(): string {
  return new Date().toISOString().slice(0, 10);
}

function AppointmentsPage() {
  const isDetail = useMatch({ from: "/app/appointments/$id", shouldThrow: false });

  const { user } = useAuth();
  const {
    appointments,
    doctors,
    patients,
    confirmAppointment,
    checkInAppointment,
    completeAppointment,
    cancelAppointment,
    refreshAppointments,
  } = useClinix();

  const [tab, setTab] = useState<Tab>("upcoming");
  const [q, setQ] = useState("");
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [confirmingId, setConfirmingId] = useState<string | null>(null);
  const [completingId, setCompletingId] = useState<string | null>(null);
  const [cancellingApt, setCancellingApt] = useState<Appointment | null>(null);
  const [cancelReason, setCancelReason] = useState("Doctor schedule change");
  const [isCancelling, setIsCancelling] = useState(false);

  // Sync latest authoritative appointments from backend on mount
  useEffect(() => {
    refreshAppointments().catch(() => {});
  }, [refreshAppointments]);

  const handleManualRefresh = useCallback(async () => {
    setIsRefreshing(true);
    try {
      await refreshAppointments();
      toast.success("Schedule refreshed", { description: "Latest appointment records loaded." });
    } catch {
      toast.error("Failed to refresh schedule");
    } finally {
      setIsRefreshing(false);
    }
  }, [refreshAppointments]);

  const isStaff = user?.role === "staff" || user?.role === "admin";
  const isDoctor = user?.role === "doctor";
  const getDoctor = (id: string) => doctors.find((d) => d.id === id);
  const getPatient = (id: string) => patients.find((p) => p.id === id);

  const scoped = useMemo(() => {
    if (user?.role === "patient") {
      const patient = patients.find((p) => p.email === user.email || p.id === user.id);
      const patId = (user as any).patientId || (patient ? patient.id : user.id);
      return appointments.filter((a) => a.patientId === patId || a.patientId === user.id || a.patientId === (user as any).patientId);
    }
    if (user?.role === "doctor") {
      const doctor = doctors.find((d) => d.email === user.email || d.id === user.id);
      const docId = (user as any).doctorId || (doctor ? doctor.id : user.id);
      return appointments.filter((a) => a.doctorId === docId || a.doctorId === user.id || a.doctorId === (user as any).doctorId);
    }
    return appointments;
  }, [user, appointments, patients, doctors]);

  const todayStr = useMemo(() => getTodayString(), []);

  const filtered = useMemo(() => {
    const list = scoped.filter((a) => {
      if (tab === "today") {
        if (a.date !== todayStr) return false;
      } else if (tab === "upcoming") {
        if (!["scheduled", "confirmed", "checked-in", "in-queue", "in-consultation"].includes(a.status)) return false;
      } else if (tab === "completed") {
        if (a.status !== "completed") return false;
      } else if (tab === "cancelled") {
        if (!(a.status === "cancelled" || a.status === "no-show")) return false;
      }

      if (q) {
        const doc = getDoctor(a.doctorId);
        const pat = getPatient(a.patientId);
        const hay = `${a.id} ${a.reason || ""} ${doc?.name || ""} ${pat?.firstName || ""} ${pat?.lastName || ""} ${a.patientId}`.toLowerCase();
        if (!hay.includes(q.toLowerCase())) return false;
      }
      return true;
    });

    // Deterministic arrangement:
    // For 'upcoming' and 'today': chronologically ascending (soonest appointments first)
    // For 'completed' and 'cancelled': descending (most recent first)
    // For 'all': upcoming visits first, followed by historical visits
    return list.sort((a, b) => {
      const keyA = `${a.date} ${a.time}`;
      const keyB = `${b.date} ${b.time}`;
      if (tab === "upcoming" || tab === "today") {
        return keyA.localeCompare(keyB);
      }
      if (tab === "completed" || tab === "cancelled") {
        return keyB.localeCompare(keyA);
      }
      // Tab === 'all'
      const isActiveA = ["scheduled", "confirmed", "checked-in", "in-queue", "in-consultation"].includes(a.status);
      const isActiveB = ["scheduled", "confirmed", "checked-in", "in-queue", "in-consultation"].includes(b.status);
      if (isActiveA && !isActiveB) return -1;
      if (!isActiveA && isActiveB) return 1;
      return keyB.localeCompare(keyA);
    });
  }, [scoped, tab, q, todayStr, doctors, patients]);

  if (isDetail) {
    return <Outlet />;
  }

  const handleConfirm = async (id: string) => {
    setConfirmingId(id);
    try {
      await confirmAppointment(id);
      toast.success("Appointment confirmed", { description: `Visit ${id} is now confirmed.` });
    } catch (err: any) {
      toast.error("Confirmation failed", { description: err?.message || "Could not confirm appointment." });
    } finally {
      setConfirmingId(null);
    }
  };

  const handleCheckIn = (id: string) => {
    const entry = checkInAppointment(id);
    if (entry) {
      toast.success("Patient checked in", { description: `Token ${entry.token} assigned.` });
    } else {
      toast.success("Patient checked in");
    }
  };

  const handleComplete = async (id: string) => {
    setCompletingId(id);
    try {
      await completeAppointment(id);
      toast.success("Appointment completed", { description: `Visit ${id} marked completed.` });
    } catch (err: any) {
      toast.error("Could not complete appointment", { description: err?.message || "Please try again." });
    } finally {
      setCompletingId(null);
    }
  };

  const handleCancelSubmit = async () => {
    if (!cancellingApt) return;
    setIsCancelling(true);
    try {
      await cancelAppointment(cancellingApt.id, cancelReason);
      toast.success("Appointment cancelled", { description: `Visit ${cancellingApt.id} has been cancelled.` });
      setCancellingApt(null);
    } catch (err: any) {
      toast.error("Cancellation failed", { description: err?.message || "Could not cancel appointment." });
    } finally {
      setIsCancelling(false);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title={isStaff ? "Appointment Management" : isDoctor ? "Doctor Schedule & Appointments" : "My Appointments"}
        description={
          isStaff
            ? "Operate today's schedule, confirm, reschedule, or check patients in."
            : isDoctor
            ? "Manage assigned patient visits, review appointment details, confirm slots, and conduct consultations."
            : "View and manage all your upcoming and past visits."
        }
        actions={
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={isRefreshing}
              onClick={handleManualRefresh}
              title="Refresh appointments"
            >
              <RotateCw className={`mr-1.5 h-3.5 w-3.5 ${isRefreshing ? "animate-spin" : ""}`} />
              Refresh
            </Button>
            {user?.role === "patient" && (
              <Button asChild>
                <Link to="/app/book" search={{ doctorId: "", step: 0 }}>
                  <Plus className="mr-1 h-4 w-4" /> Book
                </Link>
              </Button>
            )}
          </div>
        }
      />

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <Tabs value={tab} onValueChange={(v) => setTab(v as Tab)} className="w-full sm:w-auto">
          <TabsList className="grid w-full grid-cols-5 sm:w-auto">
            {TABS.map((t) => (
              <TabsTrigger key={t} value={t} className="capitalize">
                {t === "today" ? "Today" : t}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search by patient, doctor, ID, or reason…"
            aria-label="Search appointments"
            className="pl-9"
          />
        </div>
      </div>

      {filtered.length === 0 ? (
        <EmptyState
          title="No appointments"
          description={
            tab === "today"
              ? "No appointments scheduled for today."
              : tab === "upcoming"
              ? "No upcoming appointments found."
              : "Nothing in this view."
          }
          action={
            user?.role === "patient" ? (
              <Button asChild>
                <Link to="/app/book" search={{ doctorId: "", step: 0 }}>
                  Book appointment
                </Link>
              </Button>
            ) : undefined
          }
        />
      ) : isStaff || isDoctor ? (
        <Card>
          <CardContent className="p-0">
            <ul className="divide-y divide-border">
              {filtered.map((a) => {
                const doc = getDoctor(a.doctorId);
                const pat = getPatient(a.patientId);
                const isToday = a.date === todayStr;
                const patFullName = pat
                  ? `${pat.firstName} ${pat.lastName}`.trim()
                  : a.patientId;

                return (
                  <li
                    key={a.id}
                    className="grid grid-cols-1 gap-2 p-4 transition-colors hover:bg-muted/30 sm:grid-cols-[130px_1fr_1.2fr_130px_auto] sm:items-center"
                  >
                    <div>
                      <div className="flex items-center gap-1.5">
                        <p className="text-sm font-semibold">{a.time}</p>
                        {isToday && (
                          <span className="rounded bg-primary/10 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-primary">
                            Today
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-muted-foreground">{fmtDate(a.date)}</p>
                    </div>

                    <div className="min-w-0">
                      {a.patientId ? (
                        <Link
                          to="/app/patients/$id"
                          params={{ id: a.patientId }}
                          className="truncate text-sm font-semibold text-foreground hover:text-primary hover:underline block"
                        >
                          {patFullName}
                        </Link>
                      ) : (
                        <p className="truncate text-sm font-medium text-foreground">{patFullName}</p>
                      )}
                      <p className="truncate text-xs font-mono text-muted-foreground">{a.patientId}</p>
                    </div>

                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-foreground">
                        {a.reason || "General Consultation"}
                      </p>
                      <p className="truncate text-xs text-muted-foreground">
                        {doc?.name || "Assigned Doctor"} • {doc?.specialization || "Clinical"}
                      </p>
                    </div>

                    <div>
                      <AppointmentBadge status={a.status} />
                    </div>

                    <div className="flex flex-wrap items-center gap-2 sm:justify-end">
                      {a.patientId && (
                        <Button asChild size="sm" variant="ghost" className="text-primary hover:bg-primary/10 hover:text-primary">
                          <Link to="/app/patients/$id" params={{ id: a.patientId }}>
                            Workspace
                          </Link>
                        </Button>
                      )}

                      <Button asChild size="sm" variant="outline">
                        <Link to="/app/appointments/$id" params={{ id: a.id }}>
                          View
                        </Link>
                      </Button>

                      {a.status === "scheduled" && (
                        <Button
                          size="sm"
                          variant="secondary"
                          disabled={confirmingId === a.id}
                          onClick={() => handleConfirm(a.id)}
                        >
                          {confirmingId === a.id ? (
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          ) : (
                            "Confirm"
                          )}
                        </Button>
                      )}

                      {(a.status === "scheduled" || a.status === "confirmed") && isStaff && (
                        <Button size="sm" onClick={() => handleCheckIn(a.id)}>
                          Check In
                        </Button>
                      )}

                      {(a.status === "checked-in" || a.status === "in-queue" || a.status === "in-consultation") && isDoctor && (
                        <Button asChild size="sm">
                          <Link to="/app/consultations/$id" params={{ id: a.id }}>
                            Consultation
                          </Link>
                        </Button>
                      )}

                      {a.status === "in-consultation" && (
                        <Button
                          size="sm"
                          variant="outline"
                          className="border-success/40 text-success hover:bg-success/10"
                          disabled={completingId === a.id}
                          onClick={() => handleComplete(a.id)}
                        >
                          {completingId === a.id ? (
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          ) : (
                            "Complete"
                          )}
                        </Button>
                      )}

                      {(a.status === "scheduled" || a.status === "confirmed") && (
                        <Button
                          size="sm"
                          variant="ghost"
                          className="text-destructive hover:bg-destructive/10"
                          onClick={() => {
                            setCancellingApt(a);
                            setCancelReason("Doctor schedule change");
                          }}
                        >
                          Cancel
                        </Button>
                      )}
                    </div>
                  </li>
                );
              })}
            </ul>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-[minmax(0,1fr)] gap-3">
          {filtered.map((a) => (
            <AppointmentCard key={a.id} appointment={a} />
          ))}
        </div>
      )}

      {/* Doctor/Staff Cancellation Confirmation Modal */}
      <Dialog open={!!cancellingApt} onOpenChange={(open) => !open && setCancellingApt(null)}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-destructive">
              <AlertCircle className="h-5 w-5" />
              Cancel Appointment {cancellingApt?.id}
            </DialogTitle>
            <DialogDescription>
              Are you sure you want to cancel the appointment for {cancellingApt?.patientId} on{" "}
              {cancellingApt?.date} at {cancellingApt?.time}?
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-3 py-2">
            <Label htmlFor="cancel-reason">Cancellation Reason</Label>
            <Input
              id="cancel-reason"
              value={cancelReason}
              onChange={(e) => setCancelReason(e.target.value)}
              placeholder="e.g. Doctor emergency, patient request..."
            />
          </div>

          <DialogFooter className="gap-2 sm:gap-0">
            <Button
              variant="outline"
              disabled={isCancelling}
              onClick={() => setCancellingApt(null)}
            >
              Keep Appointment
            </Button>
            <Button
              variant="destructive"
              disabled={isCancelling}
              onClick={handleCancelSubmit}
            >
              {isCancelling ? (
                <>
                  <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                  Cancelling…
                </>
              ) : (
                "Yes, Cancel Visit"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
