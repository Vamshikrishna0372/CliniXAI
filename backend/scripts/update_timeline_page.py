with open("clinixai-health-flow/src/routes/app.timeline.tsx", "r", encoding="utf-8") as f:
    text = f.read()

# 1. Update imports
import_old = """import { useMemo, useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import type { LucideIcon } from "lucide-react";
import {
  Activity, Brain, Calendar, FileText, Image as ImgIcon, Pill, ReceiptText,
  UserPlus, CalendarClock, Stethoscope, LogIn as CheckInIcon,
} from "lucide-react";"""

import_new = """import { useEffect, useMemo, useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import type { LucideIcon } from "lucide-react";
import {
  Activity, Brain, Calendar, FileText, Image as ImgIcon, Pill, ReceiptText,
  UserPlus, CalendarClock, Stethoscope, LogIn as CheckInIcon, Loader2,
} from "lucide-react";
import { apiClient } from "@/lib/api-client";"""

text = text.replace(import_old, import_new)

# 2. Update Route definition with validateSearch
route_old = """export const Route = createFileRoute("/app/timeline")({
  head: () => ({ meta: [{ title: "Clinical Timeline — CliniXAI" }, { name: "robots", content: "noindex" }] }),
  component: TimelinePage,
});"""

route_new = """export const Route = createFileRoute("/app/timeline")({
  head: () => ({ meta: [{ title: "Clinical Timeline — CliniXAI" }, { name: "robots", content: "noindex" }] }),
  validateSearch: (search: Record<string, unknown>) => ({
    patient_id: typeof search.patient_id === "string" ? search.patient_id : typeof search.patientId === "string" ? search.patientId : undefined,
  }),
  component: TimelinePage,
});"""

text = text.replace(route_old, route_new)

# 3. Update TimelinePage body to fetch from backend API
func_old = """function TimelinePage() {
  const { user } = useAuth();
  const state = useClinix();
  const canPickPatient = user?.role === "doctor" || user?.role === "staff" || user?.role === "admin";
  const myPatient = state.patients.find((p) => p.email === user?.email || p.id === user?.id);
  const myPatId = myPatient ? myPatient.id : (user?.id || "");
  const [patientId, setPatientId] = useState(canPickPatient ? (state.patients[0]?.id ?? myPatId) : myPatId);
  const [filter, setFilter] = useState<(typeof FILTERS)[number]>("all");

  const effectivePatientId = user?.role === "patient" ? myPatId : patientId;


  const scopedEvents = useMemo(() => {
    let events = buildEvents(state, effectivePatientId);
    if (user?.role === "doctor") {
      const docProfile = state.doctors.find((d) => d.id === user.id || d.email === user.email || d.id === user.doctorId);
      const activeDocId = docProfile?.id || user.id || "";
      const apptIds = new Set(state.appointments.filter((a) => a.doctorId === activeDocId).map((a) => a.id));
      events = events.filter((e) => e.episodeKey === "standalone" || apptIds.has(e.episodeKey) || e.kind === "registration");
    }
    return events;
  }, [state, effectivePatientId, user]);"""

func_new = """function TimelinePage() {
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
  }, [backendEvents, state, effectivePatientId, user]);"""

text = text.replace(func_old, func_new)

with open("clinixai-health-flow/src/routes/app.timeline.tsx", "w", encoding="utf-8", newline="") as f:
    f.write(text)

print("Updated app.timeline.tsx successfully")

