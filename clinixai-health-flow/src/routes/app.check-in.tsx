import { useEffect, useMemo, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { QrCode, Search, Check, ScanLine, Loader2 } from "lucide-react";
import { PageHeader } from "@/components/app-shell/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { toast } from "sonner";
import { getDoctor, fmtDate } from "@/lib/mock/domain";
import { useClinix } from "@/lib/store/clinix-store";
import { apiClient } from "@/lib/api-client";

export const Route = createFileRoute("/app/check-in")({
  head: () => ({ meta: [{ title: "Patient Check-In — CliniXAI" }, { name: "robots", content: "noindex" }] }),
  component: CheckInPage,
});

const NOT_CHECKINABLE = new Set(["checked-in", "in-queue", "in-consultation", "completed", "cancelled", "no-show"]);

function CheckInPage() {
  const { appointments: mockAppointments, patients, queue: mockQueue, getPatient, checkInAppointment } = useClinix();
  const [q, setQ] = useState("");
  const [qrCode, setQrCode] = useState("");
  const [loadingApt, setLoadingApt] = useState<string | null>(null);
  const [apiAppointments, setApiAppointments] = useState<any[]>([]);
  const [checked, setChecked] = useState<{ token: string; apt: string; patientName?: string; doctorName?: string } | null>(null);

  useEffect(() => {
    // Load today's appointments from backend
    apiClient.appointments
      .list({ limit: 50 })
      .then((res: any) => {
        if (res && res.data) {
          const list = Array.isArray(res.data) ? res.data : res.data.items || [];
          setApiAppointments(list);
        }
      })
      .catch((err) => {
        console.warn("Could not load backend appointments:", err);
      });
  }, []);

  const appointmentsList = useMemo(() => {
    if (apiAppointments.length > 0) {
      return apiAppointments.map((a: any) => ({
        id: a.appointment_id || a.id,
        patientId: a.patient_id || a.patientId,
        patientName: a.patient_name || (a.patient ? `${a.patient.first_name} ${a.patient.last_name}` : null),
        doctorId: a.doctor_id || a.doctorId,
        doctorName: a.doctor_name || (a.doctor ? a.doctor.full_name : null),
        date: a.appointment_date || a.date,
        time: a.appointment_time || a.time,
        status: (a.status || "").toLowerCase().replace("_", "-"),
        rawStatus: a.status,
        queue: a.queue,
      }));
    }
    return mockAppointments;
  }, [apiAppointments, mockAppointments]);

  const results = useMemo(() => {
    if (q.trim().length < 2) return [];
    const needle = q.trim().toLowerCase();
    return appointmentsList
      .filter((a: any) => {
        const p = getPatient(a.patientId);
        const hay = [
          a.id,
          a.patientId,
          a.patientName,
          p?.firstName,
          p?.lastName,
          p?.mobile,
          a.doctorName,
        ]
          .filter(Boolean)
          .join(" ")
          .toLowerCase();
        return hay.includes(needle);
      })
      .slice(0, 10);
  }, [q, appointmentsList, getPatient]);

  const isQueued = (aid: string) => {
    const apt = appointmentsList.find((a: any) => a.id === aid) as any;
    if (apt?.rawStatus && ["in_queue", "checked_in", "in_consultation"].includes(apt.rawStatus)) return true;
    return mockQueue.some((qe: any) => qe.appointmentId === aid);
  };

  const doCheckIn = async (aid: string) => {
    const appt = appointmentsList.find((a: any) => a.id === aid) as any;
    if (!appt) return;
    if (isQueued(aid)) {
      toast.error("Already checked in");
      return;
    }
    if (NOT_CHECKINABLE.has(appt.status)) {
      toast.error(`Cannot check in — appointment is ${appt.status}`);
      return;
    }

    setLoadingApt(aid);
    try {
      // 1. Call real backend API
      const res = await apiClient.appointments.checkIn(aid, { method: "manual" });
      const aptData = res.data;
      const token = aptData?.queue?.token_number || "A-001";
      const patName = appt.patientName || `${getPatient(appt.patientId)?.firstName ?? ""} ${getPatient(appt.patientId)?.lastName ?? ""}`.trim();
      const docName = appt.doctorName || getDoctor(appt.doctorId)?.name;

      setChecked({ token, apt: aid, patientName: patName, doctorName: docName });
      toast.success("Checked in successfully", { description: `Token ${token} assigned` });

      // Synchronize in-memory fallback store as well
      checkInAppointment(aid);
    } catch (err: any) {
      if (err?.status === 409) {
        toast.error("Appointment already checked in. Refreshing status...");
      } else {
        const msg = err?.message || "Check-in failed. Please verify appointment date and status.";
        toast.error(msg);
      }
      // Refresh backend appointments to reflect authoritative state
      apiClient.appointments.list({ limit: 50 }).then((res: any) => {
        if (res && res.data) {
          const list = Array.isArray(res.data) ? res.data : res.data.items || [];
          setApiAppointments(list);
        }
      }).catch(() => {});
    } finally {
      setLoadingApt(null);
    }
  };

  const scanQr = async () => {
    const code = qrCode.trim();
    if (!code) {
      toast.error("Please enter an appointment ID or scan a valid QR code");
      return;
    }
    // Attempt QR check-in API
    try {
      const qrRes = await apiClient.post<any>("/check-in/qr", { token: code });
      const token = qrRes?.data?.queue_token || "A-001";
      setChecked({ token, apt: qrRes?.data?.appointment_id || code });
      toast.success("QR Check-In successful", { description: `Token ${token} assigned` });
      return;
    } catch {
      // Fallback: check if code is appointment id
      const appt = appointmentsList.find((a: any) => a.id.toLowerCase() === code.toLowerCase());
      if (appt) {
        await doCheckIn(appt.id);
      } else {
        toast.error("QR code did not match any valid appointment token");
      }
    }
  };

  if (checked) {
    const apt = appointmentsList.find((a: any) => a.id === checked.apt) as any;
    const docName = checked.doctorName || (apt ? (apt.doctorName || getDoctor(apt?.doctorId ?? "")?.name) : "");
    const patName = checked.patientName || (apt ? (apt.patientName || `${getPatient(apt?.patientId ?? "")?.firstName ?? ""} ${getPatient(apt?.patientId ?? "")?.lastName ?? ""}`.trim()) : "");
    const entry = mockQueue.find((e: any) => e.token === checked.token);
    return (
      <div className="space-y-6">
        <PageHeader title="Check-in confirmed" />
        <Card><CardContent className="p-6 text-center">
          <span className="mx-auto grid h-14 w-14 place-items-center rounded-full bg-success/15 text-success"><Check className="h-7 w-7" /></span>
          <p className="mt-3 text-sm text-muted-foreground">Queue token</p>
          <p className="font-display text-5xl font-bold text-primary">{checked.token}</p>
          <div className="mt-4 grid gap-2 text-sm sm:grid-cols-2">
            <div><span className="text-muted-foreground">Patient:</span> {patName}</div>
            <div><span className="text-muted-foreground">Doctor:</span> {docName}</div>
            <div><span className="text-muted-foreground">Appt:</span> {checked.apt}</div>
            <div><span className="text-muted-foreground">Est. wait:</span> ~{entry?.estWaitMin ?? 15} min</div>
          </div>
          <div className="mt-6"><Button onClick={() => { setChecked(null); setQ(""); setQrCode(""); }}>Check in another</Button></div>
        </CardContent></Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Patient Check-In" description="Find the patient's appointment and confirm arrival." />
      <Tabs defaultValue="search">
        <TabsList className="grid w-full max-w-sm grid-cols-2"><TabsTrigger value="search">Search</TabsTrigger><TabsTrigger value="qr">QR scan</TabsTrigger></TabsList>
        <TabsContent value="search" className="mt-4 space-y-3">
          <div className="relative"><Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" /><Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Appointment ID, patient name/ID or mobile…" className="pl-9" aria-label="Search appointments" /></div>
          {q.trim().length >= 2 && results.length === 0 && (
            <p className="px-1 text-sm text-muted-foreground">No matching appointments.</p>
          )}
          {results.length > 0 && (
            <Card><CardContent className="p-0"><ul className="divide-y divide-border">
              {results.map((a) => { const p = getPatient(a.patientId); const d = getDoctor(a.doctorId); const queued = isQueued(a.id); const blocked = NOT_CHECKINABLE.has(a.status) && !queued; return (
                <li key={a.id} className="flex flex-wrap items-center justify-between gap-2 p-3">
                  <div className="min-w-0"><p className="text-sm font-medium">{p?.firstName} {p?.lastName} <span className="text-xs text-muted-foreground">• {a.id}</span></p><p className="text-xs text-muted-foreground">{d?.name} • {fmtDate(a.date)} {a.time} • {a.status}</p></div>
                  <Button size="sm" disabled={queued || blocked} onClick={() => doCheckIn(a.id)}>{queued ? "Already in queue" : blocked ? "Unavailable" : "Check in"}</Button>
                </li>
              );})}
            </ul></CardContent></Card>
          )}
        </TabsContent>
        <TabsContent value="qr" className="mt-4">
          <Card><CardContent className="p-6 text-center space-y-4">
            <div className="mx-auto grid aspect-square max-w-xs place-items-center rounded-2xl border-2 border-dashed border-primary/40 bg-primary/5">
              <QrCode className="h-16 w-16 text-primary/60" />
            </div>
            <p className="text-sm text-muted-foreground">Ask the patient to show their QR Health Card, or enter the code manually below to simulate a scan.</p>
            <div className="mx-auto flex max-w-sm gap-2">
              <Input value={qrCode} onChange={(e) => setQrCode(e.target.value)} placeholder="Appointment ID e.g. APT-2026-00842" aria-label="QR appointment code" />
              <Button onClick={scanQr}><ScanLine className="mr-1 h-4 w-4" /> Scan</Button>
            </div>
          </CardContent></Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
