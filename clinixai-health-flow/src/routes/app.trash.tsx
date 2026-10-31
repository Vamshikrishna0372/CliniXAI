import { useMemo, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Trash2, RotateCcw, XCircle } from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/app-shell/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription,
  AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { EmptyState } from "@/components/dashboard/states";
import { useClinix, type TrashItem, type TrashKind } from "@/lib/store/clinix-store";
import { fmtDateTime } from "@/lib/mock/domain";

export const Route = createFileRoute("/app/trash")({
  head: () => ({ meta: [{ title: "Recycle Bin — CliniXAI Admin" }, { name: "robots", content: "noindex" }] }),
  component: TrashPage,
});

const KIND_LABEL: Record<TrashKind, string> = {
  patient: "Patient",
  doctor: "Doctor",
  staff: "Staff",
  department: "Department",
  "ai-report": "AI Report",
};

const KIND_TONE: Record<TrashKind, string> = {
  patient: "bg-info/10 text-info border-info/20",
  doctor: "bg-primary/10 text-primary border-primary/20",
  staff: "bg-warning/10 text-warning border-warning/20",
  department: "bg-secondary/10 text-secondary-foreground border-secondary/20",
  "ai-report": "bg-accent/10 text-accent-foreground border-accent/20",
};

function relativeTime(iso: string) {
  const diffMs = Date.now() - new Date(iso).getTime();
  const mins = Math.round(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  return `${days}d ago`;
}

function TrashPage() {
  const { trash, restoreTrash, purgeTrash } = useClinix();
  const [kind, setKind] = useState<TrashKind | "all">("all");

  const rows = useMemo(() => {
    return [...trash]
      .filter((t) => kind === "all" || t.kind === kind)
      .sort((a, b) => new Date(b.deletedAt).getTime() - new Date(a.deletedAt).getTime());
  }, [trash, kind]);

  const onRestore = (t: TrashItem) => {
    restoreTrash(t.id);
    toast.success(`${t.label} restored`);
  };

  const onPurge = (t: TrashItem) => {
    purgeTrash(t.id);
    toast.success(`${t.label} permanently deleted`);
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Recycle Bin"
        description="Soft-deleted records. Restore within retention or delete permanently."
        status={{ label: `${trash.length} item${trash.length === 1 ? "" : "s"}`, tone: "info" }}
      />

      <Card><CardContent className="p-4">
        <Select value={kind} onValueChange={(v) => setKind(v as TrashKind | "all")}>
          <SelectTrigger className="w-full sm:w-[220px]"><SelectValue placeholder="Filter by kind" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All types</SelectItem>
            {(Object.keys(KIND_LABEL) as TrashKind[]).map((k) => <SelectItem key={k} value={k}>{KIND_LABEL[k]}</SelectItem>)}
          </SelectContent>
        </Select>
      </CardContent></Card>

      {rows.length === 0 ? (
        <EmptyState icon={Trash2} title="Recycle bin is empty" description="Deleted patients, staff, doctors, departments and AI reports will appear here." />
      ) : (
        <div className="space-y-3">
          {rows.map((t) => (
            <Card key={t.id} className="min-w-0">
              <CardContent className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
                <div className="min-w-0 space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="truncate font-medium text-foreground">{t.label}</p>
                    <Badge variant="outline" className={KIND_TONE[t.kind] + " shrink-0"}>{KIND_LABEL[t.kind]}</Badge>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Deleted by {t.deletedBy} • {relativeTime(t.deletedAt)} • {fmtDateTime(t.deletedAt)}
                  </p>
                </div>
                <div className="flex shrink-0 gap-2">
                  <Button size="sm" variant="outline" className="gap-1.5" onClick={() => onRestore(t)}>
                    <RotateCcw className="h-3.5 w-3.5" /> Restore
                  </Button>
                  <AlertDialog>
                    <AlertDialogTrigger asChild>
                      <Button size="sm" variant="destructive" className="gap-1.5">
                        <XCircle className="h-3.5 w-3.5" /> Delete permanently
                      </Button>
                    </AlertDialogTrigger>
                    <AlertDialogContent>
                      <AlertDialogHeader>
                        <AlertDialogTitle>Permanently delete "{t.label}"?</AlertDialogTitle>
                        <AlertDialogDescription>
                          This action cannot be undone. The record will be removed from the recycle bin forever.
                        </AlertDialogDescription>
                      </AlertDialogHeader>
                      <AlertDialogFooter>
                        <AlertDialogCancel>Cancel</AlertDialogCancel>
                        <AlertDialogAction onClick={() => onPurge(t)}>Delete permanently</AlertDialogAction>
                      </AlertDialogFooter>
                    </AlertDialogContent>
                  </AlertDialog>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
