import { useMemo, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Plus, Building2, ChevronRight, Search, Trash2 } from "lucide-react";
import { PageHeader } from "@/components/app-shell/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { EmptyState } from "@/components/dashboard/states";
import { todayIso, type Department, type AccountStatus, type Doctor, type Appointment } from "@/lib/mock/domain";
import { useClinix } from "@/lib/store/clinix-store";
import { apiClient } from "@/lib/api-client";
import { toast } from "sonner";

export const Route = createFileRoute("/app/departments")({
  head: () => ({ meta: [{ title: "Departments — CliniXAI Admin" }, { name: "robots", content: "noindex" }] }),
  component: DepartmentsPage,
});

function DepartmentsPage() {
  const { departments, doctors, appointments, addDepartment, updateDepartment, removeDepartment } = useClinix();
  const [q, setQ] = useState("");
  const [openAdd, setOpenAdd] = useState(false);
  const [selected, setSelected] = useState<Department | null>(null);

  const today = todayIso();
  const filtered = useMemo(() => departments.filter((d) =>
    !q || `${d.name} ${d.code}`.toLowerCase().includes(q.toLowerCase())
  ), [departments, q]);

  const stats = useMemo(() => filtered.map((d) => ({
    ...d,
    doctors: doctors.filter((doc) => doc.department === d.name).length,
    todays: appointments.filter((a) => {
      const doc = doctors.find((x) => x.id === a.doctorId);
      return doc?.department === d.name && a.date === today;
    }).length,
  })), [filtered, doctors, appointments, today]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Departments"
        description="Configure clinical departments and monitor doctor coverage."
        actions={
          <Dialog open={openAdd} onOpenChange={setOpenAdd}>
            <DialogTrigger asChild><Button><Plus className="mr-1 h-4 w-4" /> Add department</Button></DialogTrigger>
            <AddDepartmentDialog onClose={async (v) => {
              setOpenAdd(false);
              if (v) {
                try {
                  await apiClient.departments.create({
                    name: v.name,
                    code: v.code,
                    description: v.description,
                  });
                  toast.success("Department added successfully!");
                  window.location.reload();
                } catch (err: any) {
                  toast.error(err?.message || "Failed to add department");
                }
              }
            }} />
          </Dialog>
        }
      />

      <Card><CardContent className="p-4">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input placeholder="Search departments…" value={q} onChange={(e) => setQ(e.target.value)} className="pl-9" />
        </div>
      </CardContent></Card>

      {stats.length === 0 ? (
        <EmptyState icon={Building2} title="No departments" description="Create the first department to start assigning doctors." />
      ) : (
        <Card><CardContent className="p-0">
          <ul className="divide-y divide-border">
            {stats.map((d) => (
              <li key={d.id} className="grid grid-cols-1 gap-3 p-4 sm:grid-cols-[minmax(0,1.6fr)_100px_120px_120px_auto] sm:items-center">
                <div className="flex min-w-0 items-center gap-3">
                  <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-primary/10 text-primary font-bold">{d.code.slice(0,2)}</span>
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold">{d.name}</p>
                    <p className="truncate text-xs text-muted-foreground">{d.code} · {d.description}</p>
                  </div>
                </div>
                <div className="text-xs"><span className="text-muted-foreground">Doctors: </span><span className="font-semibold">{d.doctors}</span></div>
                <div className="text-xs"><span className="text-muted-foreground">Today: </span><span className="font-semibold">{d.todays}</span></div>
                <Badge variant="outline" className={d.status === "active" ? "bg-success/10 text-success border-success/20" : "bg-muted text-muted-foreground"}>{d.status}</Badge>
                <div className="flex min-w-0 flex-wrap justify-end gap-2">
                  <Button size="sm" variant="ghost" onClick={() => setSelected(d)}>Details <ChevronRight className="ml-1 h-4 w-4" /></Button>
                  <AlertDialog>
                    <AlertDialogTrigger asChild>
                      <Button size="sm" variant="ghost" aria-label={`Delete ${d.name}`} className="text-error hover:text-error"><Trash2 className="h-4 w-4" /></Button>
                    </AlertDialogTrigger>
                    <AlertDialogContent>
                      <AlertDialogHeader>
                        <AlertDialogTitle>Remove {d.name}?</AlertDialogTitle>
                        <AlertDialogDescription>This will permanently remove the department record.</AlertDialogDescription>
                      </AlertDialogHeader>
                      <AlertDialogFooter>
                        <AlertDialogCancel>Cancel</AlertDialogCancel>
                        <AlertDialogAction onClick={() => { removeDepartment(d.id); toast.success("Department removed"); }}>Remove</AlertDialogAction>
                      </AlertDialogFooter>
                    </AlertDialogContent>
                  </AlertDialog>
                </div>
              </li>
            ))}
          </ul>
        </CardContent></Card>
      )}

      <Dialog open={!!selected} onOpenChange={(o) => !o && setSelected(null)}>
        <DialogContent className="max-w-lg">
          {selected && (
            <DepartmentDetails
              dept={selected}
              doctors={doctors}
              appointments={appointments}
              onToggle={() => {
                updateDepartment(selected.id, { status: selected.status === "active" ? "inactive" : "active" as AccountStatus });
                setSelected(null); toast.success("Department status updated");
              }}
            />
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}

function DepartmentDetails({ dept, doctors, appointments, onToggle }: { dept: Department; doctors: Doctor[]; appointments: Appointment[]; onToggle: () => void }) {
  const deptDoctors = doctors.filter((d) => d.department === dept.name);
  const ids = new Set(deptDoctors.map((d) => d.id));
  const appts = appointments.filter((a) => ids.has(a.doctorId));
  return (
    <>
      <DialogHeader><DialogTitle>{dept.name}</DialogTitle></DialogHeader>
      <div className="space-y-3 text-sm">
        <p className="text-muted-foreground">{dept.description}</p>
        <div className="grid grid-cols-3 gap-3">
          <Stat label="Doctors" value={deptDoctors.length} />
          <Stat label="Appointments" value={appts.length} />
          <Stat label="Completed" value={appts.filter((a) => a.status === "completed").length} />
        </div>
        <div>
          <p className="mb-2 text-xs font-semibold uppercase text-muted-foreground">Doctors in this department</p>
          <ul className="space-y-1 text-sm">
            {deptDoctors.length === 0 ? <li className="text-muted-foreground">None assigned.</li> : deptDoctors.map((d) => (
              <li key={d.id} className="flex items-center justify-between rounded-md border border-border px-3 py-1.5"><span>{d.name}</span><span className="text-xs text-muted-foreground">{d.specialization}</span></li>
            ))}
          </ul>
        </div>
      </div>
      <DialogFooter><Button variant="outline" onClick={onToggle}>{dept.status === "active" ? "Deactivate" : "Activate"} department</Button></DialogFooter>
    </>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return <div className="rounded-lg border border-border p-3"><p className="text-xs text-muted-foreground">{label}</p><p className="font-display text-lg font-bold">{value}</p></div>;
}

function AddDepartmentDialog({ onClose }: { onClose: (v: Omit<Department, "id"> | null) => void }) {
  const [form, setForm] = useState({ name: "", code: "", description: "", status: "active" as AccountStatus });
  const submit = () => {
    if (!form.name || !form.code) { toast.error("Name and code are required"); return; }
    onClose({ ...form });
  };
  return (
    <DialogContent>
      <DialogHeader><DialogTitle>Add Department</DialogTitle></DialogHeader>
      <div className="grid gap-3">
        <div><Label>Name *</Label><Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="e.g. Nephrology" /></div>
        <div><Label>Code *</Label><Input value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value.toUpperCase() })} placeholder="e.g. NEPH" /></div>
        <div><Label>Description</Label><Textarea rows={3} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></div>
        <div><Label>Status</Label>
          <Select value={form.status} onValueChange={(v) => setForm({ ...form, status: v as AccountStatus })}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent><SelectItem value="active">Active</SelectItem><SelectItem value="inactive">Inactive</SelectItem></SelectContent>
          </Select>
        </div>
      </div>
      <DialogFooter><Button variant="ghost" onClick={() => onClose(null)}>Cancel</Button><Button onClick={submit}>Add department</Button></DialogFooter>
    </DialogContent>
  );
}
