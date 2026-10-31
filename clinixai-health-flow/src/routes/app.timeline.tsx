import { useEffect, useMemo, useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import type { LucideIcon } from "lucide-react";
import {
  Activity, Brain, Calendar, FileText, Image as ImgIcon, Pill, ReceiptText,
  UserPlus, CalendarClock, Stethoscope, LogIn as CheckInIcon, Loader2,
} from "lucide-react";
import { apiClient } from "@/lib/api-client";
import { PageHeader } from "@/components/app-shell/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/dashboard/states";
import { useAuth } from "@/lib/auth-context";
import { useClinix } from "@/lib/store/clinix-store";
import { fmtDate, inr, billTotal } from "@/lib/mock/domain";
import { resolveFollowUpStatus } from "@/lib/mock/ai-models";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/app/timeline")({
  head: () => ({ meta: [{ title: "Clinical Timeline — CliniXAI" }, { name: "robots", content: "noindex" }] }),
  validateSearch: (search: Record<string, unknown>) => ({
    patient_id: typeof search.patient_id === "string" ? search.patient_id : typeof search.patientId === "string" ? search.patientId : undefined,
  }),
  component: TimelinePage,
});

type EventKind = "registration" | "appointment" | "checkin" | "consultation" | "ai" | "prescription" | "billing" | "follow-up" | "document";

type ClinicalEvent = {
  id: string;
  kind: EventKind;
  title: string;
  description?: string;
  date: string;
  statusLabel?: string;
  to?: { to: string; params?: Record<string, string> };
  episodeKey: string; // appointmentId or "standalone"
};

const KIND_META: Record<EventKind, { icon: LucideIcon; label: string }> = {
  registration: { icon: UserPlus, label: "Registration" },
  appointment: { icon: Calendar, label: "Appointment" },
  checkin: { icon: CheckInIcon, label: "Check-in" },
  consultation: { icon: Stethoscope, label: "Consultation" },
  ai: { icon: Brain, label: "AI Analysis" },
  prescription: { icon: Pill, label: "Prescription" },
  billing: { icon: ReceiptText, label: "Billing" },
  "follow-up": { icon: CalendarClock, label: "Follow-up" },
  document: { icon: FileText, label: "Document" },
};

const FILTERS: ("all" | EventKind)[] = ["all", "appointment", "checkin", "consultation", "ai", "prescription", "billing", "follow-up", "document"];

function buildEvents(state: ReturnType<typeof useClinix>, patientId: string): ClinicalEvent[] {
  const events: ClinicalEvent[] = [];
  const patient = state.patients.find((p) => p.id === patientId);
  if (patient) {
    events.push({ id: `reg-${patientId}`, kind: "registration", title: "Patient registered", description: `Welcome, ${patient.firstName} — record created.`, date: patient.registeredOn, episodeKey: "standalone" });
  }

  for (const a of state.appointments.filter((a) => a.patientId === patientId)) {
    const doc = state.doctors.find((d) => d.id === a.doctorId);
    events.push({
      id: `apt-${a.id}`, kind: "appointment", episodeKey: a.id,
      title: `Appointment ${a.status === "completed" ? "completed" : a.status === "cancelled" ? "cancelled" : "booked"} — ${doc?.name ?? "Doctor"}`,
      description: `${doc?.department ?? ""} • ${a.reason}`, date: a.date, statusLabel: a.status,
      to: { to: "/app/appointments/$id", params: { id: a.id } },
    });
    if (a.status !== "scheduled" && a.status !== "confirmed" && a.status !== "cancelled") {
      events.push({
        id: `checkin-${a.id}`, kind: "checkin", episodeKey: a.id,
        title: `Checked in${a.token ? ` — token ${a.token}` : ""}`, date: a.date,
        to: { to: "/app/appointments/$id", params: { id: a.id } },
      });
    }
  }

  for (const c of state.consultations.filter((c) => c.patientId === patientId)) {
    if (c.status === "not-started") continue;
    const doc = state.doctors.find((d) => d.id === c.doctorId);
    events.push({
      id: `con-${c.id}`, kind: "consultation", episodeKey: c.appointmentId,
      title: `Consultation ${c.status === "completed" ? "completed" : "in progress"} — ${doc?.name ?? "Doctor"}`,
      description: c.aiUsed ? "AI-assisted diagnosis" : undefined, date: c.date, statusLabel: c.status,
      to: { to: "/app/consultations/$id", params: { id: c.appointmentId } },
    });
  }

  for (const r of state.aiReports.filter((r) => r.patientId === patientId)) {
    events.push({
      id: `ai-${r.id}`, kind: "ai", episodeKey: r.appointmentId ?? "standalone",
      title: `AI analysis — ${r.imageType}`, description: r.prediction ? `${r.prediction}${r.confidence ? ` (${Math.round(r.confidence * 100)}%)` : ""}` : "Processing", date: r.date, statusLabel: r.status,
      to: { to: "/app/ai-reports/$id", params: { id: r.id } },
    });
  }

  for (const rx of state.prescriptions.filter((rx) => rx.patientId === patientId)) {
    events.push({
      id: `rx-${rx.id}`, kind: "prescription", episodeKey: rx.appointmentId,
      title: "Prescription issued", description: rx.diagnosis, date: rx.date,
      to: { to: "/app/prescriptions/$id", params: { id: rx.id } },
    });
  }

  for (const b of state.bills.filter((b) => b.patientId === patientId)) {
    events.push({
      id: `bill-${b.id}`, kind: "billing", episodeKey: b.appointmentId,
      title: `Bill ${b.status === "paid" ? "paid" : "generated"}`, description: `${inr(billTotal(b))} • ${b.id}`, date: b.date, statusLabel: b.status,
      to: { to: "/app/bills/$id", params: { id: b.id } },
    });
  }

  for (const f of state.followUps.filter((f) => f.patientId === patientId)) {
    const status = resolveFollowUpStatus(f);
    events.push({
      id: `fu-${f.id}`, kind: "follow-up", episodeKey: f.appointmentId ?? "standalone",
      title: "Follow-up scheduled", description: `${f.reason} • due ${fmtDate(f.dueDate)}`, date: f.createdOn, statusLabel: status,
    });
  }

  for (const d of state.documents.filter((d) => d.patientId === patientId)) {
    events.push({
      id: `doc-${d.id}`, kind: "document", episodeKey: d.appointmentId ?? "standalone",
      title: `${d.category} uploaded`, description: d.name, date: d.date, statusLabel: d.status,
      to: { to: "/app/documents" },
    });
  }

  return events.sort((a, b) => (a.date < b.date ? 1 : a.date > b.date ? -1 : 0));
}

function TimelinePage() {
  const { user } = useAuth();
  const state = useClinix();
  const search = Route.useSearch();
  const searchPatId = search.patient_id;

  const canPickPatient = user?.role === "doctor" || user?.role === "staff" || user?.role === "admin";
  const myPatient = state.patients.find((p) => p.email === user?.email || p.id === user?.id || (p as any).patientId === user?.patientId);
  const myPatId = (user?.patientId && user.patientId.startsWith("PAT-"))
    ? user.patientId
    : (myPatient?.id && myPatient.id.startsWith("PAT-"))
      ? myPatient.id
      : (user?.id || "");

  const initialPatientId = searchPatId || (canPickPatient ? (state.patients[0]?.id ?? myPatId) : myPatId);
  const [patientId, setPatientId] = useState(initialPatientId);
  const [filter, setFilter] = useState<(typeof FILTERS)[number]>("all");
  const [backendEvents, setBackendEvents] = useState<ClinicalEvent[] | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (searchPatId && searchPatId !== patientId) {
      setPatientId(searchPatId);
    }
  }, [searchPatId]);

  const effectivePatientId = user?.role === "patient" ? myPatId : patientId;

  useEffect(() => {
    if (!effectivePatientId) {
      setBackendEvents([]);
      return;
    }
    let cancelled = false;
    setLoading(true);
    apiClient.patients
      .getTimeline(effectivePatientId)
      .then((res) => {
        if (cancelled) return;
        const rawEvents = res?.events || [];
        const mapped: ClinicalEvent[] = rawEvents.map((ev: any) => {
          let kind: EventKind = "document";
          const et = (ev.event_type || "").toLowerCase();
          if (et === "appointment") kind = "appointment";
          else if (et === "check_in" || et === "checkin") kind = "checkin";
          else if (et === "consultation") kind = "consultation";
          else if (et === "ai_analysis" || et === "ai_review") kind = "ai";
          else if (et === "prescription") kind = "prescription";
          else if (et === "billing" || et === "payment") kind = "billing";
          else if (et === "follow_up" || et === "followup") kind = "follow-up";
          else if (et === "document") kind = "document";
          else if (et === "registration") kind = "registration";

          const apptId = ev.metadata?.appointment_id || (et === "appointment" ? ev.event_id : (ev.event_id?.startsWith("chk_") ? ev.event_id.replace("chk_", "") : "standalone"));

          let toLink: { to: string; params?: Record<string, string> } | undefined = undefined;
          if (kind === "appointment" || kind === "checkin") {
            toLink = { to: "/app/appointments/$id", params: { id: apptId } };
          } else if (kind === "consultation") {
            toLink = { to: "/app/consultations/$id", params: { id: apptId } };
          } else if (kind === "prescription") {
            toLink = { to: "/app/prescriptions/$id", params: { id: ev.event_id } };
          } else if (kind === "ai") {
            toLink = { to: "/app/ai-reports/$id", params: { id: ev.event_id } };
          } else if (kind === "billing") {
            toLink = { to: "/app/bills/$id", params: { id: ev.event_id } };
          } else if (kind === "document") {
            toLink = { to: "/app/documents" };
          }

          return {
            id: ev.event_id,
            kind,
            title: ev.title || "Clinical Event",
            description: ev.description,
            date: ev.timestamp ? String(ev.timestamp).split("T")[0] : "",
            statusLabel: ev.status,
            to: toLink,
            episodeKey: apptId || "standalone",
          };
        });
        setBackendEvents(mapped);
      })
      .catch((err) => {
        if (cancelled) return;
        console.warn("Failed to load backend timeline, using store data:", err);
        setBackendEvents(buildEvents(state, effectivePatientId));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [effectivePatientId, state]);

  const scopedEvents = useMemo(() => {
    let events = backendEvents !== null ? backendEvents : buildEvents(state, effectivePatientId);
    if (user?.role === "doctor") {
      const docProfile = state.doctors.find((d) => d.id === user.id || d.email === user.email || d.id === user.doctorId);
      const activeDocId = docProfile?.id || user.id || "";
      const apptIds = new Set(state.appointments.filter((a) => a.doctorId === activeDocId).map((a) => a.id));
      events = events.filter((e) => e.episodeKey === "standalone" || apptIds.has(e.episodeKey) || e.kind === "registration");
    }
    return events;
  }, [backendEvents, state, effectivePatientId, user]);

  const filtered = useMemo(() => (filter === "all" ? scopedEvents : scopedEvents.filter((e) => e.kind === filter)), [scopedEvents, filter]);

  const episodes = useMemo(() => {
    const map = new Map<string, ClinicalEvent[]>();
    for (const e of filtered) {
      const list = map.get(e.episodeKey) ?? [];
      list.push(e);
      map.set(e.episodeKey, list);
    }
    return Array.from(map.entries()).sort((a, b) => {
      const da = a[1][0]?.date ?? "";
      const db = b[1][0]?.date ?? "";
      return da < db ? 1 : -1;
    });
  }, [filtered]);

  const patient = state.patients.find((p) => p.id === effectivePatientId);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Clinical Timeline"
        description={user?.role === "patient" ? "Your chronological healthcare journey at CliniXAI." : "Chronological patient journey — appointment through billing and follow-up."}
      />

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        {canPickPatient && (
          <Select value={patientId} onValueChange={setPatientId}>
            <SelectTrigger className="w-full sm:w-64"><SelectValue placeholder="Select patient" /></SelectTrigger>
            <SelectContent>
              {state.patients.map((p) => <SelectItem key={p.id} value={p.id}>{p.firstName} {p.lastName} • {p.id}</SelectItem>)}
            </SelectContent>
          </Select>
        )}
        <div className="flex min-w-0 flex-1 flex-wrap gap-1.5 sm:justify-end">
          {FILTERS.map((f) => (
            <Button key={f} size="sm" variant={filter === f ? "default" : "outline"} className="h-7 rounded-full px-3 text-xs capitalize" onClick={() => setFilter(f)}>
              {f === "all" ? "All" : KIND_META[f].label}
            </Button>
          ))}
        </div>
      </div>

      {patient && canPickPatient && (
        <p className="text-sm text-muted-foreground">Showing timeline for <span className="font-medium text-foreground">{patient.firstName} {patient.lastName}</span> ({patient.id})</p>
      )}

      {episodes.length === 0 ? (
        <EmptyState title="No events yet" description="Activity will appear here as it happens." />
      ) : (
        <div className="space-y-5">
          {episodes.map(([key, events]) => (
            <Card key={key}>
              <CardContent className="p-4 sm:p-5">
                {key !== "standalone" && (
                  <div className="mb-3 flex flex-wrap items-center gap-2 border-b border-border pb-2">
                    <Calendar className="h-4 w-4 shrink-0 text-primary" />
                    <p className="min-w-0 truncate text-sm font-semibold text-foreground">Episode — {key}</p>
                  </div>
                )}
                <ol className="relative space-y-4 border-l border-border pl-5">
                  {events.map((e) => {
                    const Icon = KIND_META[e.kind].icon;
                    const body = (
                      <div className="rounded-xl border border-border bg-card p-3 transition-colors hover:bg-muted/40">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <p className="min-w-0 truncate text-sm font-semibold text-foreground">{e.title}</p>
                          <div className="flex shrink-0 items-center gap-2">
                            {e.statusLabel && <Badge variant="outline" className="capitalize">{e.statusLabel}</Badge>}
                            <span className="text-xs text-muted-foreground">{fmtDate(e.date)}</span>
                          </div>
                        </div>
                        {e.description && <p className="mt-1 truncate text-xs text-muted-foreground">{e.description}</p>}
                      </div>
                    );
                    return (
                      <li key={e.id} className="relative">
                        <span className="absolute -left-[30px] top-0 grid h-8 w-8 place-items-center rounded-full bg-primary/10 text-primary ring-4 ring-background">
                          <Icon className="h-4 w-4" />
                        </span>
                        {e.to ? <Link to={e.to.to} params={e.to.params as never} className="block">{body}</Link> : body}
                      </li>
                    );
                  })}
                </ol>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
