import { useMemo, useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { ChevronLeft, ChevronRight, CalendarDays } from "lucide-react";
import { PageHeader } from "@/components/app-shell/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { EmptyState } from "@/components/dashboard/states";
import { AppointmentBadge } from "@/components/domain/status-badge";
import { fmtDate, type Appointment, type AppointmentStatus } from "@/lib/mock/domain";
import { useAuth } from "@/lib/auth-context";
import { useClinix } from "@/lib/store/clinix-store";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/app/calendar")({
  head: () => ({ meta: [{ title: "Appointment Calendar — CliniXAI" }, { name: "robots", content: "noindex" }] }),
  component: CalendarPage,
});

type ViewMode = "day" | "week" | "month";

const LEGEND: { status: AppointmentStatus; label: string }[] = [
  { status: "scheduled", label: "Scheduled" },
  { status: "confirmed", label: "Confirmed" },
  { status: "checked-in", label: "Checked In" },
  { status: "in-queue", label: "In Queue" },
  { status: "in-consultation", label: "In Consultation" },
  { status: "completed", label: "Completed" },
  { status: "cancelled", label: "Cancelled" },
  { status: "no-show", label: "No Show" },
];

const LEGEND_DOT: Record<AppointmentStatus, string> = {
  scheduled: "bg-muted-foreground/50",
  confirmed: "bg-primary",
  "checked-in": "bg-primary",
  "in-queue": "bg-warning",
  "in-consultation": "bg-warning",
  completed: "bg-success",
  cancelled: "bg-error",
  "no-show": "bg-muted-foreground/50",
};

const toIso = (d: Date) => d.toISOString().slice(0, 10);
const startOfWeek = (d: Date) => {
  const x = new Date(d);
  const day = x.getDay();
  x.setDate(x.getDate() - day);
  x.setHours(0, 0, 0, 0);
  return x;
};
const startOfMonth = (d: Date) => new Date(d.getFullYear(), d.getMonth(), 1);
const addDays = (d: Date, n: number) => {
  const x = new Date(d);
  x.setDate(x.getDate() + n);
  return x;
};
const sameDay = (a: Date, b: Date) => toIso(a) === toIso(b);

function CalendarPage() {
  const { user } = useAuth();
  const { appointments, doctors, patients } = useClinix();
  const [view, setView] = useState<ViewMode>("week");
  const [cursor, setCursor] = useState(new Date());

  const getDoctor = (id: string) => doctors.find((d) => d.id === id);
  const getPatient = (id: string) => patients.find((p) => p.id === id);

  const scoped = useMemo(() => {
    if (user?.role === "patient") {
      const patient = patients.find((p) => p.email === user.email || p.id === user.id);
      const patId = patient ? patient.id : user.id;
      return appointments.filter((a) => a.patientId === patId || a.patientId === user.id);
    }
    if (user?.role === "doctor") {
      const doctor = doctors.find((d) => d.email === user.email || d.id === user.id);
      const docId = doctor ? doctor.id : user.id;
      return appointments.filter((a) => a.doctorId === docId || a.doctorId === user.id);
    }
    return appointments;
  }, [appointments, user, patients, doctors]);


  const byDate = useMemo(() => {
    const map = new Map<string, Appointment[]>();
    for (const a of scoped) {
      const list = map.get(a.date) ?? [];
      list.push(a);
      map.set(a.date, list);
    }
    for (const [, list] of map) list.sort((a, b) => (a.time < b.time ? -1 : 1));
    return map;
  }, [scoped]);

  const title = useMemo(() => {
    if (view === "day") return cursor.toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
    if (view === "week") {
      const start = startOfWeek(cursor);
      const end = addDays(start, 6);
      return `${start.toLocaleDateString("en-IN", { day: "numeric", month: "short" })} – ${end.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}`;
    }
    return cursor.toLocaleDateString("en-IN", { month: "long", year: "numeric" });
  }, [view, cursor]);

  const navigate = (dir: -1 | 1) => {
    setCursor((c) => {
      if (view === "day") return addDays(c, dir);
      if (view === "week") return addDays(c, dir * 7);
      const n = new Date(c);
      n.setMonth(n.getMonth() + dir);
      return n;
    });
  };

  const AppointmentRow = ({ a }: { a: Appointment }) => {
    const doc = getDoctor(a.doctorId);
    const pat = getPatient(a.patientId);
    return (
      <Link
        to="/app/appointments/$id"
        params={{ id: a.id }}
        className="flex min-w-0 items-center gap-2 rounded-lg border border-border bg-card px-2 py-1.5 text-xs transition-colors hover:bg-muted/50"
      >
        <span className={cn("h-2 w-2 shrink-0 rounded-full", LEGEND_DOT[a.status])} />
        <span className="shrink-0 font-medium text-foreground">{a.time}</span>
        <span className="min-w-0 flex-1 truncate text-muted-foreground">
          {user?.role === "patient" ? doc?.name : `${pat?.firstName} ${pat?.lastName}`}
        </span>
      </Link>
    );
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Appointment Calendar"
        description={
          user?.role === "patient" ? "Your appointments at a glance."
          : user?.role === "doctor" ? "Your scheduled consultations at a glance."
          : "All appointments across the hospital."
        }
      />

      <Card>
        <CardContent className="flex flex-col gap-4 p-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex min-w-0 items-center gap-2">
              <Button variant="outline" size="icon" aria-label="Previous" onClick={() => navigate(-1)}><ChevronLeft className="h-4 w-4" /></Button>
              <Button variant="outline" size="sm" onClick={() => setCursor(new Date())}>Today</Button>
              <Button variant="outline" size="icon" aria-label="Next" onClick={() => navigate(1)}><ChevronRight className="h-4 w-4" /></Button>
              <p className="min-w-0 truncate pl-2 text-sm font-semibold text-foreground sm:text-base">{title}</p>
            </div>
            <ToggleGroup type="single" value={view} onValueChange={(v) => v && setView(v as ViewMode)} className="w-full justify-start sm:w-auto">
              <ToggleGroupItem value="day" className="flex-1 sm:flex-none">Day</ToggleGroupItem>
              <ToggleGroupItem value="week" className="flex-1 sm:flex-none">Week</ToggleGroupItem>
              <ToggleGroupItem value="month" className="flex-1 sm:flex-none">Month</ToggleGroupItem>
            </ToggleGroup>
          </div>

          {view === "day" && <DayView date={cursor} list={byDate.get(toIso(cursor)) ?? []} Row={AppointmentRow} />}
          {view === "week" && <WeekView start={startOfWeek(cursor)} byDate={byDate} Row={AppointmentRow} />}
          {view === "month" && <MonthView cursor={cursor} byDate={byDate} onPick={(d) => { setCursor(d); setView("day"); }} />}
        </CardContent>
      </Card>

      <Card>
        <CardContent className="flex flex-wrap items-center gap-x-4 gap-y-2 p-4">
          <span className="flex items-center gap-1.5 text-xs font-semibold text-muted-foreground"><CalendarDays className="h-3.5 w-3.5" /> Legend:</span>
          {LEGEND.map((l) => (
            <span key={l.status} className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <span className={cn("h-2 w-2 rounded-full", LEGEND_DOT[l.status])} /> {l.label}
            </span>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}

function DayView({ date, list, Row }: { date: Date; list: Appointment[]; Row: React.ComponentType<{ a: Appointment }> }) {
  if (list.length === 0) return <EmptyState title="No appointments" description={`Nothing scheduled for ${date.toLocaleDateString("en-IN", { day: "numeric", month: "short" })}.`} />;
  return (
    <ul className="space-y-2">
      {list.map((a) => <li key={a.id}><Row a={a} /></li>)}
    </ul>
  );
}

function WeekView({ start, byDate, Row }: { start: Date; byDate: Map<string, Appointment[]>; Row: React.ComponentType<{ a: Appointment }> }) {
  const days = Array.from({ length: 7 }, (_, i) => addDays(start, i));
  const today = new Date();
  return (
    <>
      <div className="hidden gap-2 sm:grid sm:grid-cols-7">
        {days.map((d) => {
          const list = byDate.get(toIso(d)) ?? [];
          return (
            <div key={toIso(d)} className={cn("min-w-0 rounded-lg border border-border p-2", sameDay(d, today) && "border-primary bg-primary-soft/20")}>
              <p className="mb-2 truncate text-xs font-semibold text-foreground">{d.toLocaleDateString("en-IN", { weekday: "short", day: "numeric" })}</p>
              <div className="space-y-1.5">
                {list.length === 0 ? <p className="text-[11px] text-muted-foreground">No visits</p> : list.map((a) => <Row key={a.id} a={a} />)}
              </div>
            </div>
          );
        })}
      </div>
      <div className="space-y-3 sm:hidden">
        {days.map((d) => {
          const list = byDate.get(toIso(d)) ?? [];
          return (
            <div key={toIso(d)}>
              <p className={cn("mb-1.5 text-xs font-semibold", sameDay(d, today) ? "text-primary" : "text-foreground")}>
                {d.toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "short" })}
              </p>
              {list.length === 0 ? <p className="text-xs text-muted-foreground">No visits</p> : (
                <div className="space-y-1.5">{list.map((a) => <Row key={a.id} a={a} />)}</div>
              )}
            </div>
          );
        })}
      </div>
    </>
  );
}

function MonthView({ cursor, byDate, onPick }: { cursor: Date; byDate: Map<string, Appointment[]>; onPick: (d: Date) => void }) {
  const monthStart = startOfMonth(cursor);
  const gridStart = startOfWeek(monthStart);
  const cells = Array.from({ length: 42 }, (_, i) => addDays(gridStart, i));
  const today = new Date();
  return (
    <div className="grid grid-cols-7 gap-1.5">
      {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((d) => (
        <p key={d} className="px-1 text-center text-[11px] font-semibold uppercase text-muted-foreground">{d}</p>
      ))}
      {cells.map((d) => {
        const iso = toIso(d);
        const list = byDate.get(iso) ?? [];
        const inMonth = d.getMonth() === cursor.getMonth();
        return (
          <button
            key={iso}
            type="button"
            onClick={() => onPick(d)}
            className={cn(
              "min-h-[64px] min-w-0 rounded-lg border border-border p-1 text-left transition-colors hover:bg-muted/50 sm:min-h-[84px] sm:p-1.5",
              !inMonth && "opacity-40",
              sameDay(d, today) && "border-primary",
            )}
          >
            <div className="flex items-center justify-between gap-1">
              <span className="text-[11px] font-medium text-foreground">{d.getDate()}</span>
              {list.length > 0 && <span className="grid h-4 min-w-4 shrink-0 place-items-center rounded-full bg-primary/15 px-1 text-[10px] font-semibold text-primary">{list.length}</span>}
            </div>
            <div className="mt-1 hidden space-y-0.5 sm:block">
              {list.slice(0, 2).map((a) => (
                <p key={a.id} className="truncate text-[10px] text-muted-foreground">{a.time} · {a.reason}</p>
              ))}
              {list.length > 2 && <p className="text-[10px] text-muted-foreground">+{list.length - 2} more</p>}
            </div>
          </button>
        );
      })}
    </div>
  );
}
