import { useMemo, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { CalendarClock, CheckCircle2, XCircle, CalendarPlus, Clock, AlertTriangle } from "lucide-react";
import { PageHeader } from "@/components/app-shell/page-header";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter, DialogTrigger,
} from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { EmptyState } from "@/components/dashboard/states";
import { fmtDate, todayIso } from "@/lib/mock/domain";
import { useClinix } from "@/lib/store/clinix-store";
import { dueDateFor, resolveFollowUpStatus, type FollowUp, type FollowUpInterval } from "@/lib/mock/ai-models";
import { toast } from "sonner";

export const Route = createFileRoute("/app/follow-ups")({
  head: () => ({ meta: [{ title: "Follow-ups — CliniXAI" }, { name: "robots", content: "noindex" }] }),
  component: FollowUpsPage,
});

const TABS = ["all", "upcoming", "overdue", "completed", "cancelled"] as const;
const INTERVALS: { value: FollowUpInterval; label: string }[] = [
  { value: "7d", label: "7 days" },
  { value: "15d", label: "15 days" },
  { value: "30d", label: "30 days" },
  { value: "custom", label: "Custom date" },
];

const intervalBadgeLabel = (i: FollowUpInterval) => (i === "custom" ? "Custom" : i.replace("d", " days"));

function StatusBadge({ status }: { status: string }) {
  if (status === "overdue") return <Badge variant="destructive">Overdue</Badge>;
  if (status === "completed") return <Badge variant="outline" className="border-success/40 text-success">Completed</Badge>;
  if (status === "cancelled") return <Badge variant="secondary">Cancelled</Badge>;
  return <Badge variant="outline">Upcoming</Badge>;
}

function FollowUpsPage() {
  const { followUps, patients, doctors, getPatient, scheduleFollowUp, updateFollowUp, setFollowUpStatus } = useClinix();
  const [tab, setTab] = useState<(typeof TABS)[number]>("all");
  const [open, setOpen] = useState(false);
  const [rescheduleId, setRescheduleId] = useState<string | null>(null);

  const resolved = useMemo(() => followUps.map((f) => ({ ...f, status: resolveFollowUpStatus(f) })), [followUps]);

  const today = todayIso();
  const weekAhead = new Date(today);
  weekAhead.setDate(weekAhead.getDate() + 7);
  const weekAheadIso = weekAhead.toISOString().slice(0, 10);

  const kpis = useMemo(() => ({
    upcoming: resolved.filter((f) => f.status === "upcoming").length,
    dueThisWeek: resolved.filter((f) => f.status === "upcoming" && f.dueDate <= weekAheadIso).length,
    overdue: resolved.filter((f) => f.status === "overdue").length,
    completed: resolved.filter((f) => f.status === "completed").length,
  }), [resolved, weekAheadIso]);

  const list = useMemo(() => resolved
    .filter((f) => tab === "all" || f.status === tab)
    .sort((a, b) => a.dueDate.localeCompare(b.dueDate)), [resolved, tab]);

  const markCompleted = (f: FollowUp) => {
    setFollowUpStatus(f.id, "completed");
    toast.success("Follow-up marked completed.");
  };
  const cancel = (f: FollowUp) => {
    setFollowUpStatus(f.id, "cancelled");
    toast.success("Follow-up cancelled.");
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Follow-ups"
        description="Track and schedule patient follow-ups."
        actions={
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <Button size="sm"><CalendarPlus className="h-4 w-4" /> Schedule follow-up</Button>
            </DialogTrigger>
            <ScheduleDialog
              patients={patients}
              doctors={doctors}
              onSubmit={(input) => {
                scheduleFollowUp(input);
                toast.success("Follow-up scheduled.");
                setOpen(false);
              }}
            />
          </Dialog>
        }
      />

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Kpi icon={Clock} label="Upcoming" value={kpis.upcoming} />
        <Kpi icon={CalendarClock} label="Due this week" value={kpis.dueThisWeek} />
        <Kpi icon={AlertTriangle} label="Overdue" value={kpis.overdue} tone="destructive" />
        <Kpi icon={CheckCircle2} label="Completed" value={kpis.completed} tone="success" />
      </div>

      <Tabs value={tab} onValueChange={(v) => setTab(v as (typeof TABS)[number])} className="w-full">
        <TabsList className="grid w-full grid-cols-5">
          {TABS.map((t) => <TabsTrigger key={t} value={t} className="capitalize">{t}</TabsTrigger>)}
        </TabsList>
      </Tabs>

      {list.length === 0 ? <EmptyState icon={CalendarClock} title="No follow-ups" description="Nothing in this view." /> : (
        <Card><CardContent className="p-0">
          <ul className="divide-y divide-border">
            {list.map((f) => {
              const p = getPatient(f.patientId);
              return (
                <li key={f.id} className="grid grid-cols-[minmax(0,1fr)] gap-2 p-4 sm:grid-cols-[minmax(0,1fr)_minmax(0,1.6fr)_minmax(0,110px)_minmax(0,100px)_minmax(0,110px)_auto] sm:items-center [&>*]:min-w-0">
                  <div className="min-w-0"><p className="truncate text-sm font-medium">{p?.firstName} {p?.lastName}</p><p className="text-xs text-muted-foreground">{p?.id}</p></div>
                  <div className="min-w-0"><p className="truncate text-sm">{f.reason}</p>{f.notes && <p className="truncate text-xs text-muted-foreground">{f.notes}</p>}</div>
                  <div className="text-sm">{fmtDate(f.dueDate)}</div>
                  <div><Badge variant="outline">{intervalBadgeLabel(f.interval)}</Badge></div>
                  <div><StatusBadge status={f.status} /></div>
                  <div className="flex flex-wrap justify-end gap-2">
                    {(f.status === "upcoming" || f.status === "overdue") && (
                      <>
                        <Button size="sm" variant="outline" onClick={() => markCompleted(f)}><CheckCircle2 className="h-4 w-4" /> Complete</Button>
                        <Button size="sm" variant="outline" onClick={() => setRescheduleId(f.id)}><CalendarClock className="h-4 w-4" /> Reschedule</Button>
                        <Button size="sm" variant="ghost" onClick={() => cancel(f)}><XCircle className="h-4 w-4" /> Cancel</Button>
                      </>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        </CardContent></Card>
      )}

      <Dialog open={!!rescheduleId} onOpenChange={(v) => !v && setRescheduleId(null)}>
        {rescheduleId && (
          <RescheduleDialog
            followUp={followUps.find((f) => f.id === rescheduleId)!}
            onSubmit={(patch) => {
              updateFollowUp(rescheduleId, { ...patch, status: "upcoming" });
              toast.success("Follow-up rescheduled.");
              setRescheduleId(null);
            }}
          />
        )}
      </Dialog>
    </div>
  );
}

function Kpi({ icon: Icon, label, value, tone }: { icon: typeof Clock; label: string; value: number; tone?: "success" | "destructive" }) {
  return (
    <Card>
      <CardContent className="flex items-center gap-3 p-4">
        <Icon className={`h-5 w-5 shrink-0 ${tone === "destructive" ? "text-destructive" : tone === "success" ? "text-success" : "text-primary"}`} />
        <div className="min-w-0">
          <p className="text-xl font-semibold tabular-nums">{value}</p>
          <p className="truncate text-xs text-muted-foreground">{label}</p>
        </div>
      </CardContent>
    </Card>
  );
}

function ScheduleDialog({
  patients, doctors, onSubmit,
}: {
  patients: { id: string; firstName: string; lastName: string }[];
  doctors: { id: string; name: string }[];
  onSubmit: (input: { patientId: string; doctorId: string; interval: FollowUpInterval; reason: string; dueDate?: string; notes?: string }) => void;
}) {
  const [patientId, setPatientId] = useState(patients[0]?.id ?? "");
  const [doctorId, setDoctorId] = useState(doctors[0]?.id ?? "");
  const [interval, setInterval] = useState<FollowUpInterval>("7d");
  const [customDate, setCustomDate] = useState(dueDateFor("7d"));
  const [reason, setReason] = useState("");
  const [notes, setNotes] = useState("");

  const dueDate = interval === "custom" ? customDate : dueDateFor(interval);

  const submit = () => {
    if (!patientId || !doctorId || !reason.trim()) {
      toast.error("Select a patient and enter a reason.");
      return;
    }
    onSubmit({ patientId, doctorId, interval, reason: reason.trim(), dueDate, notes: notes.trim() || undefined });
  };

  return (
    <DialogContent>
      <DialogHeader>
        <DialogTitle>Schedule follow-up</DialogTitle>
        <DialogDescription>Set a due date and reason for this patient's follow-up.</DialogDescription>
      </DialogHeader>
      <div className="space-y-3">
        <div>
          <Label>Patient</Label>
          <Select value={patientId} onValueChange={setPatientId}>
            <SelectTrigger><SelectValue placeholder="Select patient" /></SelectTrigger>
            <SelectContent>
              {patients.map((p) => <SelectItem key={p.id} value={p.id}>{p.firstName} {p.lastName} ({p.id})</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <div>
          <Label>Doctor</Label>
          <Select value={doctorId} onValueChange={setDoctorId}>
            <SelectTrigger><SelectValue placeholder="Select doctor" /></SelectTrigger>
            <SelectContent>
              {doctors.map((d) => <SelectItem key={d.id} value={d.id}>{d.name}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <div>
          <Label>Interval</Label>
          <div className="mt-1 flex flex-wrap gap-2">
            {INTERVALS.map((i) => (
              <Button key={i.value} type="button" size="sm" variant={interval === i.value ? "default" : "outline"} onClick={() => setInterval(i.value)}>
                {i.label}
              </Button>
            ))}
          </div>
        </div>
        {interval === "custom" ? (
          <div><Label htmlFor="custom-date">Custom due date</Label><Input id="custom-date" type="date" value={customDate} onChange={(e) => setCustomDate(e.target.value)} /></div>
        ) : (
          <p className="text-xs text-muted-foreground">Due date: {fmtDate(dueDate)}</p>
        )}
        <div><Label htmlFor="reason">Reason</Label><Input id="reason" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. Review persistent cough" /></div>
        <div><Label htmlFor="notes">Notes (optional)</Label><Textarea id="notes" rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} /></div>
      </div>
      <DialogFooter>
        <Button onClick={submit}><CalendarPlus className="h-4 w-4" /> Schedule</Button>
      </DialogFooter>
    </DialogContent>
  );
}

function RescheduleDialog({ followUp, onSubmit }: { followUp: FollowUp; onSubmit: (patch: { dueDate: string; interval: FollowUpInterval; notes?: string }) => void }) {
  const [interval, setInterval] = useState<FollowUpInterval>(followUp.interval);
  const [customDate, setCustomDate] = useState(followUp.dueDate);
  const [notes, setNotes] = useState(followUp.notes ?? "");
  const dueDate = interval === "custom" ? customDate : dueDateFor(interval);

  return (
    <DialogContent>
      <DialogHeader>
        <DialogTitle>Reschedule follow-up</DialogTitle>
        <DialogDescription>{followUp.reason}</DialogDescription>
      </DialogHeader>
      <div className="space-y-3">
        <div>
          <Label>Interval</Label>
          <div className="mt-1 flex flex-wrap gap-2">
            {INTERVALS.map((i) => (
              <Button key={i.value} type="button" size="sm" variant={interval === i.value ? "default" : "outline"} onClick={() => setInterval(i.value)}>
                {i.label}
              </Button>
            ))}
          </div>
        </div>
        {interval === "custom" ? (
          <div><Label htmlFor="rs-date">New due date</Label><Input id="rs-date" type="date" value={customDate} onChange={(e) => setCustomDate(e.target.value)} /></div>
        ) : (
          <p className="text-xs text-muted-foreground">New due date: {fmtDate(dueDate)}</p>
        )}
        <div><Label htmlFor="rs-notes">Notes</Label><Textarea id="rs-notes" rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} /></div>
      </div>
      <DialogFooter>
        <Button onClick={() => onSubmit({ dueDate, interval, notes: notes.trim() || undefined })}><CalendarClock className="h-4 w-4" /> Save</Button>
      </DialogFooter>
    </DialogContent>
  );
}
