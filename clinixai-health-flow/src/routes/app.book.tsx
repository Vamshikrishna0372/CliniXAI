import { useState, useMemo, useEffect, useCallback } from "react";
import { createFileRoute, useNavigate, Link } from "@tanstack/react-router";
import { z } from "zod";
import { Check, ArrowLeft, ArrowRight, Calendar as CalIcon, IndianRupee, Info, Search, Loader2 } from "lucide-react";
import { PageHeader } from "@/components/app-shell/page-header";
import { Stepper } from "@/components/domain/stepper";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { fmtDate } from "@/lib/mock/domain";
import { useClinix } from "@/lib/store/clinix-store";
import { apiClient } from "@/lib/api-client";

const searchSchema = z.object({
  doctorId: z.string().optional().default(""),
  step: z.number().int().optional().default(0),
});

export const Route = createFileRoute("/app/book")({
  head: () => ({ meta: [{ title: "Book Appointment — CliniXAI" }, { name: "robots", content: "noindex" }] }),
  validateSearch: (s: Record<string, unknown>) => searchSchema.parse(s),
  component: BookPage,
});

import { useAuth } from "@/lib/auth-context";

const STEPS = ["Doctor", "Date", "Time", "Reason", "Review", "Confirm"];

function BookPage() {
  const { user } = useAuth();
  const { doctorId: initialDoctor } = Route.useSearch();
  const navigate = useNavigate();
  const { doctors, appointments, bookAppointment, patients } = useClinix();

  const [step, setStep] = useState(initialDoctor ? 1 : 0);
  const [doctorId, setDoctorId] = useState(initialDoctor);
  const [q, setQ] = useState("");
  const [dept, setDept] = useState("All");
  const [date, setDate] = useState<string>("");
  const [time, setTime] = useState<string>("");
  const [reason, setReason] = useState("");
  const [note, setNote] = useState("");
  const [confirmedId, setConfirmedId] = useState<string | null>(null);

  // Real-time slot availability from backend
  const [availableSlots, setAvailableSlots] = useState<string[]>([]);
  const [slotsLoading, setSlotsLoading] = useState(false);

  const fetchSlots = useCallback(async (dId: string, d: string) => {
    if (!dId || !d) { setAvailableSlots([]); return; }
    setSlotsLoading(true);
    try {
      const res = await apiClient.doctors.getAvailability(dId, d);
      const rawSlots = res?.data?.available_slots || res?.available_slots || [];
      const slots: string[] = rawSlots.map((s: any) => s.start_time || s);
      setAvailableSlots(slots);
    } catch {
      // Fallback to doctor's hardcoded slots if backend unavailable
      const fallbackDoc = doctors.find((doc) => doc.id === dId);
      setAvailableSlots(fallbackDoc?.availableSlots ?? []);
    } finally {
      setSlotsLoading(false);
    }
  }, [doctors]);

  useEffect(() => {
    if (step === 2 && doctorId && date) {
      fetchSlots(doctorId, date);
    }
  }, [step, doctorId, date, fetchSlots]);

  const depts = useMemo(() => ["All", ...Array.from(new Set(doctors.map((d) => d.department)))], [doctors]);
  const doctorList = useMemo(() => doctors.filter((d) => {
    if (dept !== "All" && d.department !== dept) return false;
    if (q && !`${d.name} ${d.specialization} ${d.department}`.toLowerCase().includes(q.toLowerCase())) return false;
    return true;
  }), [doctors, dept, q]);

  const doctor = doctors.find((d) => d.id === doctorId);

  const bookedTimesForDate = useMemo(() => {
    if (!doctorId || !date) return new Set<string>();
    return new Set(
      appointments
        .filter((a) => a.doctorId === doctorId && a.date === date && a.status !== "cancelled")
        .map((a) => a.time),
    );
  }, [appointments, doctorId, date]);

  const canNext = useMemo(() => {
    if (step === 0) return !!doctorId;
    if (step === 1) return !!date;
    if (step === 2) return !!time;
    if (step === 3) return reason.trim().length >= 3;
    return true;
  }, [step, doctorId, date, time, reason]);

  const next = () => setStep((s) => Math.min(s + 1, STEPS.length - 1));
  const back = () => setStep((s) => Math.max(s - 1, 0));

  const confirm = async () => {
    if (!doctor || !date || !time || !reason) return;
    let patId = user?.patientId;
    if (!patId) {
      let patient = patients.find((p) => p.email === user?.email || p.id === user?.patientId || p.id === user?.id || p.id?.startsWith("PAT-"));
      patId = patient ? patient.id : "";
    }
    if (!patId && user?.role === "patient") {
      try {
        const meProfile = await apiClient.patients.getMe();
        if (meProfile?.data?.patient_id) {
          patId = meProfile.data.patient_id;
        }
      } catch {
        // Ignore fallback
      }
    }
    if (!patId) patId = user?.id || "";
    if (!patId) {
      toast.error("Booking Error", { description: "Patient profile is required to book an appointment." });
      return;
    }

    try {
      const appt = await bookAppointment({ patientId: patId, doctorId: doctor.id, date, time, reason, note });
      setConfirmedId(appt.id);
      toast.success("Appointment booked", { description: `${appt.id} confirmed with ${doctor.name}` });
    } catch (err: any) {
      toast.error("Booking Error", { description: err.message || "Failed to book appointment." });
      if (doctor?.id && date) {
        fetchSlots(doctor.id, date);
      }
    }
  };


  if (confirmedId) {
    return (
      <div className="mx-auto max-w-2xl space-y-6">
        <Card>
          <CardContent className="p-6 sm:p-8 text-center">
            <span className="mx-auto grid h-16 w-16 place-items-center rounded-full bg-success/15 text-success">
              <Check className="h-8 w-8" />
            </span>
            <h2 className="mt-4 font-display text-2xl font-bold text-foreground">Appointment Confirmed</h2>
            <p className="mt-1 text-sm text-muted-foreground">Your appointment is booked. Details are below.</p>
            <div className="mt-6 grid gap-3 rounded-xl border border-border bg-muted/30 p-4 text-left sm:grid-cols-2">
              <Row label="Appointment ID" value={confirmedId} />
              <Row label="Doctor" value={doctor?.name ?? "-"} />
              <Row label="Department" value={doctor?.department ?? "-"} />
              <Row label="Date" value={fmtDate(date)} />
              <Row label="Time" value={time} />
              <Row label="Location" value="CliniXAI Medical Centre, MG Road" />
            </div>
            <Alert className="mt-6 text-left">
              <Info className="h-4 w-4" />
              <AlertTitle>Payment at reception</AlertTitle>
              <AlertDescription>
                No online payment is required to book. Charges (if any) are collected at the hospital reception via Cash, UPI, or Card after your consultation.
              </AlertDescription>
            </Alert>
            <div className="mt-6 flex flex-wrap justify-center gap-2">
              <Button variant="outline" asChild><Link to="/app/appointments/$id" params={{ id: confirmedId }}>View Appointment</Link></Button>
              <Button variant="outline" onClick={() => navigate({ to: "/app/appointments" })}>All Appointments</Button>
              <Button onClick={() => navigate({ to: "/app" })}>Back to Dashboard</Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Book Appointment" description="Choose a doctor, pick a slot, and confirm your visit." />
      <Card>
        <CardContent className="p-4 sm:p-6">
          <Stepper steps={STEPS} current={step} />
          <div className="mt-6">
            {step === 0 && (
              <div className="space-y-4">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
                  <div className="relative flex-1">
                    <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                    <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search doctor, specialization…" aria-label="Search doctors" className="pl-9" />
                  </div>
                  <div className="w-full sm:w-56">
                    <Select value={dept} onValueChange={setDept}>
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>{depts.map((d) => <SelectItem key={d} value={d}>{d}</SelectItem>)}</SelectContent>
                    </Select>
                  </div>
                </div>
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {doctorList.map((d) => (
                    <button
                      key={d.id}
                      onClick={() => { setDoctorId(d.id); setTime(""); setDate(""); }}
                      className={cn(
                        "flex items-start gap-3 rounded-xl border p-3 text-left transition-colors",
                        doctorId === d.id ? "border-primary bg-primary/5" : "border-border hover:bg-muted/40",
                      )}
                    >
                      <Avatar className="h-10 w-10 shrink-0"><AvatarFallback className="bg-primary/10 text-primary font-semibold">{d.photoInitial}</AvatarFallback></Avatar>
                      <div className="min-w-0">
                        <p className="truncate text-sm font-semibold text-foreground">{d.name}</p>
                        <p className="truncate text-xs text-muted-foreground">{d.specialization}</p>
                        <p className="mt-1 flex items-center gap-1 text-xs text-muted-foreground"><IndianRupee className="h-3 w-3" />{d.consultationFee}</p>
                      </div>
                    </button>
                  ))}
                  {doctorList.length === 0 && <p className="col-span-full text-sm text-muted-foreground">No doctors match your search.</p>}
                </div>
              </div>
            )}
            {step === 1 && (
              <div className="space-y-3">
                <Label>Select a date</Label>
                <div className="grid grid-cols-3 gap-2 sm:grid-cols-6">
                  {Array.from({ length: 12 }).map((_, i) => {
                    const d = new Date(); d.setDate(d.getDate() + i);
                    const yyyy = d.getFullYear();
                    const mm = String(d.getMonth() + 1).padStart(2, "0");
                    const dd = String(d.getDate()).padStart(2, "0");
                    const key = `${yyyy}-${mm}-${dd}`;
                    const label = d.toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short" });
                    return (
                      <button
                        key={key}
                        onClick={() => { setDate(key); setTime(""); }}
                        className={cn("rounded-lg border p-2 text-xs font-medium transition-colors", date === key ? "border-primary bg-primary/10 text-primary" : "border-border hover:bg-muted/40")}
                      >
                        <CalIcon className="mx-auto mb-1 h-4 w-4" />
                        {label}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}
            {step === 2 && doctor && (
              <div className="space-y-3">
                <Label>Available time slots on {date && fmtDate(date)}</Label>
                {slotsLoading ? (
                  <div className="flex items-center gap-2 py-6 text-sm text-muted-foreground">
                    <Loader2 className="h-4 w-4 animate-spin" /> Loading available slots…
                  </div>
                ) : availableSlots.length === 0 ? (
                  <p className="py-4 text-sm text-muted-foreground">
                    No available slots for this doctor on {fmtDate(date)}. Please select another date.
                  </p>
                ) : (
                  <div className="grid grid-cols-3 gap-2 sm:grid-cols-5">
                    {availableSlots.map((s) => (
                      <button
                        key={s}
                        onClick={() => setTime(s)}
                        className={cn(
                          "rounded-lg border p-2 text-sm font-medium transition-colors",
                          time === s ? "border-primary bg-primary/10 text-primary" : "border-border hover:bg-muted/40",
                        )}
                      >{s}</button>
                    ))}
                  </div>
                )}
              </div>
            )}
            {step === 3 && (
              <div className="space-y-4">
                <div>
                  <Label>Reason for visit</Label>
                  <RadioGroup value={reason} onValueChange={setReason} className="mt-2 grid gap-2 sm:grid-cols-2">
                    {["General consultation","Follow-up","New symptoms","Review reports","Prescription refill"].map((r) => (
                      <label key={r} className={cn("flex items-center gap-2 rounded-lg border p-3 text-sm", reason === r ? "border-primary bg-primary/5" : "border-border")}>
                        <RadioGroupItem value={r} /> {r}
                      </label>
                    ))}
                  </RadioGroup>
                </div>
                <div>
                  <Label htmlFor="note">Optional note</Label>
                  <Textarea id="note" value={note} onChange={(e) => setNote(e.target.value)} placeholder="Anything the doctor should know?" rows={3} />
                </div>
              </div>
            )}
            {step === 4 && doctor && (
              <div className="grid gap-3 rounded-xl border border-border bg-muted/30 p-4 sm:grid-cols-2">
                <Row label="Doctor" value={doctor.name} />
                <Row label="Department" value={doctor.department} />
                <Row label="Date" value={date && fmtDate(date)} />
                <Row label="Time" value={time} />
                <Row label="Reason" value={reason} />
                <Row label="Fee (payable at reception)" value={`₹${doctor.consultationFee}`} />
                {note && <div className="sm:col-span-2"><Row label="Note" value={note} /></div>}
              </div>
            )}
            {step === 5 && (
              <div className="space-y-4 text-center">
                <p className="text-sm text-muted-foreground">Ready to confirm? Once booked, you'll receive appointment details and reminders.</p>
                <Button size="lg" onClick={confirm}>Confirm Appointment</Button>
              </div>
            )}
          </div>
          <div className="mt-6 flex flex-wrap items-center justify-between gap-2 border-t border-border pt-4">
            <Button variant="ghost" onClick={back} disabled={step === 0}><ArrowLeft className="mr-1 h-4 w-4" /> Back</Button>
            {step < STEPS.length - 1 && (
              <Button onClick={next} disabled={!canNext}>Next <ArrowRight className="ml-1 h-4 w-4" /></Button>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <p className="text-[11px] uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="text-sm font-medium text-foreground">{value}</p>
    </div>
  );
}
