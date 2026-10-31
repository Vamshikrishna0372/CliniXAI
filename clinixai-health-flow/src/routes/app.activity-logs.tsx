import { useMemo, useState, useEffect } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Search, ShieldAlert, ArrowUpDown, ChevronLeft, ChevronRight, List, History } from "lucide-react";
import { PageHeader } from "@/components/app-shell/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { EmptyState } from "@/components/dashboard/states";
import { fmtDateTime, fmtDate } from "@/lib/mock/domain";
import { useClinix, type ClinixState } from "@/lib/store/clinix-store";

import { apiClient } from "@/lib/api-client";
import { toast } from "sonner";

export const Route = createFileRoute("/app/activity-logs")({
  head: () => ({ meta: [{ title: "Activity Logs — CliniXAI Admin" }, { name: "robots", content: "noindex" }] }),
  component: ActivityLogsPage,
});

const PAGE_SIZE = 15;

function ActivityLogsPage() {
  const [logs, setLogs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [role, setRole] = useState("all");
  const [action, setAction] = useState("all");
  const [status, setStatus] = useState("all");
  const [sortDir, setSortDir] = useState<"desc" | "asc">("desc");
  const [page, setPage] = useState(1);
  const [view, setView] = useState<"table" | "timeline">("table");

  const loadLogs = async () => {
    setLoading(true);
    try {
      const res = await apiClient.auditLogs.list({ limit: 100 });
      if (res && res.items) {
        const mapped = res.items.map((it: any) => ({
          id: it.audit_id,
          user: it.actor_id || "System",
          role: it.role || "admin",
          action: it.action,
          entity: it.resource,
          entityId: it.resource_id,
          timestamp: it.timestamp,
          status: "success",
        }));
        setLogs(mapped);
      }
    } catch (err: any) {
      console.warn("Could not fetch audit logs:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadLogs();
  }, []);

  const actions = ["all", ...Array.from(new Set(logs.map((l) => l.action)))];

  const rows = useMemo(() => {
    const filtered = logs.filter((l) => {
      if (role !== "all" && l.role !== role) return false;
      if (action !== "all" && l.action !== action) return false;
      if (status !== "all" && l.status !== status) return false;
      if (q && !`${l.user} ${l.entity} ${l.entityId ?? ""} ${l.action}`.toLowerCase().includes(q.toLowerCase())) return false;
      return true;
    });
    return [...filtered].sort((a, b) => {
      const diff = new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime();
      return sortDir === "desc" ? -diff : diff;
    });
  }, [logs, q, role, action, status, sortDir]);

  const totalPages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  const pageRows = rows.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  const setFilter = (fn: () => void) => { fn(); setPage(1); };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Activity & Audit Logs"
        description="Immutable historical record of important system actions."
        status={{ label: "Read-only", tone: "info" }}
        actions={
          <div className="flex gap-2">
            <Button size="sm" variant={view === "table" ? "default" : "outline"} className="gap-1.5" onClick={() => setView("table")}><List className="h-3.5 w-3.5" /> Table</Button>
            <Button size="sm" variant={view === "timeline" ? "default" : "outline"} className="gap-1.5" onClick={() => setView("timeline")}><History className="h-3.5 w-3.5" /> Timeline</Button>
          </div>
        }
      />

      <Card><CardContent className="grid gap-3 p-4 sm:grid-cols-2 xl:grid-cols-[minmax(0,1fr)_minmax(0,140px)_minmax(0,180px)_minmax(0,140px)] [&>*]:min-w-0">
        <div className="relative"><Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" /><Input value={q} onChange={(e) => setFilter(() => setQ(e.target.value))} placeholder="Search entity, ID, user…" className="pl-9" /></div>
        <Select value={role} onValueChange={(v) => setFilter(() => setRole(v))}>
          <SelectTrigger><SelectValue placeholder="Role" /></SelectTrigger>
          <SelectContent>{["all","admin","doctor","staff","patient","system"].map((r) => <SelectItem key={r} value={r}>{r}</SelectItem>)}</SelectContent>
        </Select>
        <Select value={action} onValueChange={(v) => setFilter(() => setAction(v))}>
          <SelectTrigger><SelectValue placeholder="Action" /></SelectTrigger>
          <SelectContent>{actions.map((a) => <SelectItem key={a} value={a}>{a}</SelectItem>)}</SelectContent>
        </Select>
        <Select value={status} onValueChange={(v) => setFilter(() => setStatus(v))}>
          <SelectTrigger><SelectValue placeholder="Status" /></SelectTrigger>
          <SelectContent>{["all","success","warning","failure"].map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
        </Select>
      </CardContent></Card>

      {rows.length === 0 ? (
        <EmptyState icon={ShieldAlert} title="No log entries match" description="Try clearing filters or searching a different entity ID." />
      ) : view === "timeline" ? (
        <ActivityTimeline entries={rows} />
      ) : (
        <Card><CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[820px] text-sm">
              <thead className="bg-muted/40 text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="p-3 text-left">
                    <button className="flex items-center gap-1" onClick={() => setSortDir((d) => d === "desc" ? "asc" : "desc")} aria-label="Sort by timestamp">
                      Timestamp <ArrowUpDown className="h-3 w-3" />
                    </button>
                  </th>
                  <th className="p-3 text-left">User</th>
                  <th className="p-3 text-left">Role</th>
                  <th className="p-3 text-left">Action</th>
                  <th className="p-3 text-left">Entity</th>
                  <th className="p-3 text-left">Entity ID</th>
                  <th className="p-3 text-left">Status</th>
                </tr>
              </thead>
              <tbody>
                {pageRows.map((l) => (
                  <tr key={l.id} className="border-b border-border">
                    <td className="p-3 text-xs text-muted-foreground">{fmtDateTime(l.timestamp)}</td>
                    <td className="p-3 font-medium">{l.user}</td>
                    <td className="p-3 text-xs capitalize">{l.role}</td>
                    <td className="p-3">{l.action}</td>
                    <td className="p-3">{l.entity}</td>
                    <td className="p-3 text-xs text-muted-foreground">{l.entityId ?? "—"}</td>
                    <td className="p-3">
                      <Badge variant="outline" className={
                        l.status === "success" ? "bg-success/10 text-success border-success/20"
                        : l.status === "failure" ? "bg-error/10 text-error border-error/20"
                        : "bg-warning/10 text-warning border-warning/20"
                      }>{l.status}</Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex items-center justify-between gap-2 border-t border-border p-3 text-xs text-muted-foreground">
            <span>Page {page} of {totalPages} • {rows.length} entries</span>
            <div className="flex gap-2">
              <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))}><ChevronLeft className="h-4 w-4" /></Button>
              <Button size="sm" variant="outline" disabled={page >= totalPages} onClick={() => setPage((p) => Math.min(totalPages, p + 1))}><ChevronRight className="h-4 w-4" /></Button>
            </div>
          </div>
        </CardContent></Card>
      )}
    </div>
  );
}


type LogEntry = ClinixState["activityLog"][number];

const STATUS_DOT: Record<LogEntry["status"], string> = {
  success: "bg-success",
  warning: "bg-warning",
  failure: "bg-error",
};

function ActivityTimeline({ entries }: { entries: LogEntry[] }) {
  const groups = useMemo(() => {
    const map = new Map<string, LogEntry[]>();
    for (const e of entries) {
      const day = fmtDate(e.timestamp.slice(0, 10));
      if (!map.has(day)) map.set(day, []);
      map.get(day)!.push(e);
    }
    return Array.from(map.entries());
  }, [entries]);

  return (
    <div className="space-y-6">
      {groups.map(([day, items]) => (
        <div key={day} className="space-y-3">
          <p className="sticky top-0 z-[1] w-fit rounded-full bg-muted px-3 py-1 text-xs font-semibold text-muted-foreground">{day}</p>
          <div className="space-y-3 border-l border-border pl-4">
            {items.map((l) => (
              <div key={l.id} className="relative min-w-0">
                <span className={`absolute -left-[21px] top-1.5 h-2.5 w-2.5 shrink-0 rounded-full ${STATUS_DOT[l.status]}`} />
                <Card><CardContent className="flex flex-wrap items-center gap-2 p-3">
                  <span className="text-xs font-medium text-muted-foreground">{fmtDateTime(l.timestamp).split(",").pop()?.trim()}</span>
                  <span className="min-w-0 truncate font-medium text-foreground">{l.user}</span>
                  <Badge variant="outline" className="shrink-0 text-[10px] capitalize">{l.role}</Badge>
                  <span className="min-w-0 truncate text-sm text-muted-foreground">{l.action}</span>
                  <Badge variant="secondary" className="shrink-0 text-[10px]">{l.entity}{l.entityId ? ` • ${l.entityId}` : ""}</Badge>
                </CardContent></Card>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
