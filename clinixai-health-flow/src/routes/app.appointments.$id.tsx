import { useState, useEffect } from "react";
import { createFileRoute, Link, useParams, useNavigate } from "@tanstack/react-router";
import { ArrowLeft, Calendar, Clock, MapPin, User, FileText, Brain, ReceiptText, Pill, X, CalendarClock } from "lucide-react";
import { PageHeader } from "@/components/app-shell/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { StatusProgress } from "@/components/domain/stepper";
import { AppointmentBadge } from "@/components/domain/status-badge";
import { EmptyState } from "@/components/dashboard/states";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import { fmtDate } from "@/lib/mock/domain";
import { useClinix } from "@/lib/store/clinix-store";
import { apiClient } from "@/lib/api-client";
import { toast } from "sonner";

import { useAuth } from "@/lib/auth-context";

export const Route = createFileRoute("/app/appointments/$id")({
  head: () => ({ meta: [{ title: "Appointment Details — CliniXAI" }, { name: "robots", content: "noindex" }] }),
  component: AppointmentDetailPage,
});

const STAGES = ["Booked","Confirmed","Checked In","In Queue","Consultation","Completed"];
const STAGE_INDEX: Record<string, number> = {
  scheduled: 0, confirmed: 1, "checked-in": 2, "in-queue": 3, "in-consultation": 4, completed: 5, cancelled: -1, "no-show": -1,
};

function AppointmentDetailPage() {
  const { id } = useParams({ from: "/app/appointments/$id" });
  const navigate = useNavigate();
  const { user } = useAuth();
  const { appointments, doctors, patients, prescriptions, bills, aiReports, cancelAppointment, rescheduleAppointment, confirmAppointment, checkInAppointment, completeAppointment } = useClinix();
  const [rescheduleOpen, setRescheduleOpen] = useState(false);
  const [newDate, setNewDate] = useState("");
  const [newTime, setNewTime] = useState("");
  const [liveApt, setLiveApt] = useState<any | null>(null);
  const [loadingLive, setLoadingLive] = useState(true);
  const [errorStatus, setErrorStatus] = useState<number | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [patientDetails, setPatientDetails] = useState<any | null>(null);

  useEffect(() => {
    let active = true;
    setLoadingLive(true);
    setErrorStatus(null);
    apiClient.appointments.getDetail(id)
      .then((res: any) => {
        if (!active) return;
        const data = res?.data || res;
        if (data && (data.appointment_id || data.id)) {
          setLiveApt({
            id: data.appointment_id || data.id,
            patientId: data.patient_id,
            doctorId: data.doctor_id,
            date: data.appointment_date,
            time: data.start_time,
            status: (data.status || "scheduled").toLowerCase().replace(/_/g, "-"),
            reason: data.reason || "General Consultation",
            type: data.appointment_type || "in_person",
            note: data.reason,
            token: data.queue?.token_number || data.token,
          });
        }
      })
      .catch((err: any) => {
        console.warn("Could not load backend appointment detail:", err);
        if (active) {
          setErrorStatus(err?.status || (err?.message?.includes("authorized") ? 403 : 500));
        }
      })
      .finally(() => {
        if (active) setLoadingLive(false);
      });
    return () => { active = false; };
  }, [id]);

  const effectivePatientId = liveApt?.patientId || appointments.find((a) => a.id === id)?.patientId;

  useEffect(() => {
    let active = true;
    if (effectivePatientId) {
      apiClient.patients.getDetail(effectivePatientId)
        .then((res: any) => {
          if (!active) return;
          const data = res?.data || res;
          if (data && (data.patient_id || data.id)) {
            setPatientDetails(data);
          }
        })
        .catch(() => {});
    }
    return () => { active = false; };
  }, [effectivePatientId]);

  const isStaff = user?.role === "staff" || user?.role === "admin";
  const isDoctor = user?.role === "doctor";

  if (errorStatus === 403) {
    return (
      <EmptyState
        title="Access Denied"
        description="You are not authorized to view this appointment."
        action={<Button asChild><Link to="/app/appointments">Back to Appointments</Link></Button>}
      />
    );
  }

  const storeApt = appointments.find((a) => a.id === id);
  const apt = liveApt || storeApt;

  if (loadingLive && !apt) {
    return (
      <Card className="p-12 text-center">
        <p className="text-sm font-medium text-foreground">Loading appointment details…</p>
      </Card>
    );
  }

  if (!apt) {
    return (
      <EmptyState
        title="Appointment not found"
        description="The requested appointment could not be found."
        action={<Button asChild><Link to="/app/appointments">Back</Link></Button>}
      />
    );
  }

  const doc = doctors.find((d) => d.id === apt.doctorId);
  const pat = patients.find((p) => p.id === apt.patientId);
  const rx = prescriptions.find((p) => p.appointmentId === apt.id);
  const bill = bills.find((b) => b.appointmentId === apt.id);
  const ai = aiReports.find((a) => a.appointmentId === apt.id);

  const editable = apt.status !== "completed" && apt.status !== "cancelled" && apt.status !== "no-show";
  const bookedTimes = new Set(
    appointments.filter((a) => a.doctorId === apt.doctorId && a.date === newDate && a.id !== apt.id && a.status !== "cancelled").map((a) => a.time),
  );

  const onConfirm = async () => {
    setActionLoading(true);
    try {
      await confirmAppointment(apt.id);
      toast.success("Appointment confirmed", { description: `${apt.id} is now confirmed.` });
      setLiveApt((prev: any) => prev ? { ...prev, status: "confirmed" } : prev);
    } catch (err: any) {
      toast.error("Confirmation failed", { description: err?.message || "Please check appointment state." });
    } finally {
      setActionLoading(false);
    }
  };

  const onCheckIn = () => {
    const entry = checkInAppointment(apt.id);
    if (entry) toast.success("Patient checked in", { description: `Token ${entry.token} assigned` });
    else toast.success("Patient checked in");
  };

  const onComplete = async () => {
    setActionLoading(true);
    try {
      await completeAppointment(apt.id);
      toast.success("Appointment completed", { description: `${apt.id} is marked completed.` });
      setLiveApt((prev: any) => prev ? { ...prev, status: "completed" } : prev);
    } catch (err: any) {
      toast.error("Could not complete appointment", { description: err?.message || "Please try again." });
    } finally {
      setActionLoading(false);
    }
  };

  const onCancel = async () => {
    setActionLoading(true);
    try {
      await cancelAppointment(apt.id, "Cancelled by user");
      toast.success("Appointment cancelled", { description: `${apt.id} has been cancelled.` });
      setLiveApt((prev: any) => prev ? { ...prev, status: "cancelled" } : prev);
    } catch (err: any) {
      toast.error("Cancellation failed", { description: err?.message || "Please check appointment state." });
    } finally {
      setActionLoading(false);
    }
  };

  const onReschedule = () => {
    if (!newDate || !newTime) return;
    rescheduleAppointment(apt.id, newDate, newTime);
    toast.success("Appointment rescheduled", { description: `${fmtDate(newDate)} at ${newTime}` });
    setRescheduleOpen(false);
    setNewDate(""); setNewTime("");
  };

  return (
    <div className="space-y-6">
      <div>
        <Button asChild variant="ghost" size="sm" className="mb-2"><Link to="/app/appointments"><ArrowLeft className="mr-1 h-4 w-4" /> All appointments</Link></Button>
        <PageHeader
          title={`Appointment ${apt.id}`}
          description={`${doc?.name || "Doctor"} • ${doc?.department || "Consultation"}`}
          actions={
            <div className="flex flex-wrap items-center gap-2">
              <AppointmentBadge status={apt.status} />
              {apt.patientId && (
                <Button asChild size="sm" variant="outline">
                  <Link to="/app/patients/$id" params={{ id: apt.patientId }}>
                    <User className="mr-1.5 h-3.5 w-3.5" /> Clinical Workspace
                  </Link>
                </Button>
              )}
              {apt.status === "scheduled" && (isStaff || isDoctor) && (
                <Button size="sm" variant="secondary" disabled={actionLoading} onClick={onConfirm}>
                  {actionLoading ? "Confirming…" : "Confirm"}
                </Button>
              )}
              {(apt.status === "scheduled" || apt.status === "confirmed") && isStaff && (
                <Button size="sm" onClick={onCheckIn}>Check In</Button>
              )}
              {(apt.status === "scheduled" || apt.status === "confirmed" || apt.status === "checked-in" || apt.status === "in-queue" || apt.status === "in-consultation") && isDoctor && (
                <Button asChild size="sm"><Link to="/app/consultations/$id" params={{ id: apt.id }}>{apt.status === "in-consultation" ? "Open Consultation" : "Start Consultation"}</Link></Button>
              )}
              {(apt.status === "in-consultation") && (
                <Button size="sm" variant="outline" className="text-success border-success/40 hover:bg-success/10" disabled={actionLoading} onClick={onComplete}>
                  {actionLoading ? "Completing…" : "Complete"}
                </Button>
              )}
              {editable && (
                <>
                  <Dialog open={rescheduleOpen} onOpenChange={setRescheduleOpen}>
                    <DialogContent className="max-h-[85vh] max-w-md overflow-y-auto">
                      <DialogHeader><DialogTitle>Reschedule appointment</DialogTitle></DialogHeader>
                      <div className="space-y-4">
                        <div>
                          <Label>New date</Label>
                          <div className="mt-2 grid grid-cols-3 gap-2 sm:grid-cols-4">
                            {Array.from({ length: 8 }).map((_, i) => {
                              const d = new Date(); d.setDate(d.getDate() + i + 1);
                              const key = d.toISOString().slice(0, 10);
                              const label = d.toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short" });
                              return (
                                <button key={key} onClick={() => { setNewDate(key); setNewTime(""); }}
                                  className={cn("rounded-lg border p-2 text-xs font-medium", newDate === key ? "border-primary bg-primary/10 text-primary" : "border-border hover:bg-muted/40")}>
                                  {label}
                                </button>
                              );
                            })}
                          </div>
                        </div>
                        {newDate && (
                          <div>
                            <Label>New time</Label>
                            <div className="mt-2 grid grid-cols-3 gap-2 sm:grid-cols-4">
                              {(doc?.availableSlots || ["09:00", "09:30", "10:00", "10:30", "11:00", "11:30", "14:00", "14:30", "15:00", "15:30"]).map((s) => {
                                const taken = bookedTimes.has(s);
                                return (
                                  <button key={s} disabled={taken} onClick={() => setNewTime(s)}
                                    className={cn("rounded-lg border p-2 text-sm font-medium", taken ? "cursor-not-allowed border-border bg-muted text-muted-foreground line-through" : newTime === s ? "border-primary bg-primary/10 text-primary" : "border-border hover:bg-muted/40")}>
                                    {s}
                                  </button>
                                );
                              })}
                            </div>
                          </div>
                        )}
                      </div>
                      <DialogFooter>
                        <Button variant="outline" onClick={() => setRescheduleOpen(false)}>Cancel</Button>
                        <Button onClick={onReschedule} disabled={!newDate || !newTime}>Confirm reschedule</Button>
                      </DialogFooter>
                    </DialogContent>
                  </Dialog>
                  <Button size="sm" variant="outline" onClick={() => setRescheduleOpen(true)}><CalendarClock className="mr-1 h-3.5 w-3.5" /> Reschedule</Button>
                  <AlertDialog>
                    <AlertDialogTrigger asChild>
                      <Button size="sm" variant="destructive"><X className="mr-1 h-3.5 w-3.5" /> Cancel</Button>
                    </AlertDialogTrigger>
                    <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>Cancel this appointment?</AlertDialogTitle>
                      <AlertDialogDescription>This will cancel your appointment with {doc?.name || "the doctor"} on {fmtDate(apt.date)} at {apt.time}. This action cannot be undone.</AlertDialogDescription>
                    </AlertDialogHeader>
                      <AlertDialogFooter>
                        <AlertDialogCancel>Keep appointment</AlertDialogCancel>
                        <AlertDialogAction onClick={onCancel} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">Yes, cancel</AlertDialogAction>
                      </AlertDialogFooter>
                    </AlertDialogContent>
                  </AlertDialog>
                </>
              )}
            </div>
          }
        />
      </div>

      <Card>
        <CardContent className="p-4 sm:p-6 space-y-4">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Info icon={Calendar} label="Date" value={fmtDate(apt.date)} />
            <Info icon={Clock} label="Time" value={apt.time} />
            <Info
              icon={User}
              label="Patient"
              value={
                apt.patientId ? (
                  <div className="flex flex-col gap-0.5">
                    <Link to="/app/patients/$id" params={{ id: apt.patientId }} className="text-primary hover:underline font-semibold">
                      {patientDetails?.full_name || (patientDetails ? `${patientDetails.first_name} ${patientDetails.last_name}` : null) || (pat ? `${pat.firstName} ${pat.lastName}` : (user?.role === "patient" ? `${user.fullName || user.firstName || "Patient"}` : "Patient"))}
                    </Link>
                    <span className="font-mono text-xs text-muted-foreground">{apt.patientId}</span>
                  </div>
                ) : (
                  pat ? `${pat.firstName} ${pat.lastName}` : "Patient"
                )
              }
            />
            <Info icon={MapPin} label="Location" value="MG Road, Bengaluru" />
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Reason for visit</p>
            <p className="text-sm text-foreground">{apt.reason}</p>
          </div>
          {apt.token && (
            <div className="rounded-lg border border-primary/30 bg-primary/5 p-3">
              <p className="text-xs uppercase tracking-wide text-primary">Queue token</p>
              <p className="font-display text-2xl font-bold text-primary">{apt.token}</p>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-4 sm:p-6">
          <p className="mb-4 text-sm font-semibold">Progress</p>
          {STAGE_INDEX[apt.status] === -1 ? (
            <p className="text-sm text-muted-foreground">This appointment was {apt.status.replace("-", " ")}.</p>
          ) : (
            <StatusProgress steps={STAGES} current={STAGE_INDEX[apt.status] ?? 0} />
          )}
        </CardContent>
      </Card>

      {apt.status === "completed" || rx || bill || ai ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {rx && <RelatedCard icon={Pill} title="Prescription" subtitle={rx.id} to="/app/prescriptions/$id" params={{ id: rx.id }} />}
          {bill && <RelatedCard icon={ReceiptText} title="Bill" subtitle={bill.id} to="/app/bills/$id" params={{ id: bill.id }} />}
          {ai && <RelatedCard icon={Brain} title="AI Report" subtitle={ai.id} to="/app/ai-reports/$id" params={{ id: ai.id }} />}
          <RelatedCard icon={FileText} title="Medical Records" subtitle="View all" to="/app/medical-records" />
        </div>
      ) : (
        <Card><CardContent className="p-4 sm:p-6 text-sm text-muted-foreground">Awaiting doctor consultation — related documents will appear here once completed.</CardContent></Card>
      )}
    </div>
  );
}

function Info({ icon: Icon, label, value }: { icon: React.ComponentType<{ className?: string }>; label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-start gap-2">
      <Icon className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
      <div className="min-w-0"><p className="text-[11px] uppercase tracking-wide text-muted-foreground">{label}</p><div className="truncate text-sm font-medium">{value}</div></div>
    </div>
  );
}

function RelatedCard({ icon: Icon, title, subtitle, to, params }: { icon: React.ComponentType<{ className?: string }>; title: string; subtitle: string; to: string; params?: Record<string, string> }) {
  return (
    <Link to={to as never} params={params as never} className="rounded-2xl border border-border bg-card p-4 card-hover">
      <span className="grid h-10 w-10 place-items-center rounded-xl bg-primary/10 text-primary"><Icon className="h-5 w-5" /></span>
      <p className="mt-3 text-sm font-semibold">{title}</p>
      <p className="text-xs text-muted-foreground">{subtitle}</p>
    </Link>
  );
}
