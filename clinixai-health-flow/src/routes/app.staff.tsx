import { useMemo, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Search, Plus, Trash2, UserCog } from "lucide-react";
import { PageHeader } from "@/components/app-shell/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { EmptyState } from "@/components/dashboard/states";
import { useClinix } from "@/lib/store/clinix-store";
import type { Staff, AccountStatus } from "@/lib/mock/domain";
import { toast } from "sonner";
import { apiClient } from "@/lib/api-client";

export const Route = createFileRoute("/app/staff")({
  head: () => ({ meta: [{ title: "Hospital Staff — CliniXAI Admin" }, { name: "robots", content: "noindex" }] }),
  component: StaffPage,
});

function StaffPage() {
  const { staff, departments, addStaff, updateStaff, removeStaff } = useClinix();
  const [q, setQ] = useState("");
  const [dept, setDept] = useState("All");
  const [status, setStatus] = useState<"all" | AccountStatus>("all");
  const [openAdd, setOpenAdd] = useState(false);
  const [editing, setEditing] = useState<Staff | null>(null);

  const depts = ["All", ...Array.from(new Set(staff.map((s) => s.department)))];
  const filtered = useMemo(() => staff.filter((s) => {
    if (dept !== "All" && s.department !== dept) return false;
    if (status !== "all" && s.status !== status) return false;
    if (q && !`${s.firstName} ${s.lastName} ${s.id} ${s.email}`.toLowerCase().includes(q.toLowerCase())) return false;
    return true;
  }), [staff, dept, status, q]);

  const toggleStatus = (s: Staff) => {
    updateStaff(s.id, { status: s.status === "active" ? "inactive" : "active" });
    toast.success("Staff status updated");
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Hospital Staff"
        description="Manage reception, billing, and records staff accounts."
        actions={
          <Dialog open={openAdd} onOpenChange={setOpenAdd}>
            <DialogTrigger asChild><Button><Plus className="mr-1 h-4 w-4" /> Add staff</Button></DialogTrigger>
            <StaffFormDialog
              departments={departments.map((d) => d.name)}
              onCancel={() => setOpenAdd(false)}
              onSubmit={async (v) => {
                try {
                  await apiClient.staff.create({
                    email: v.email,
                    full_name: `${v.firstName} ${v.lastName}`.trim(),
                    first_name: v.firstName,
                    last_name: v.lastName || "Staff",
                    phone: v.mobile || undefined,
                    designation: v.department || "Receptionist",
                    department_id: v.department,
                  });
                  toast.success("Staff account provisioned!", {
                    description: `Invitation sent to ${v.email}`,
                  });
                  setOpenAdd(false);
                  window.location.reload();
                } catch (err: any) {
                  toast.error(err?.message || "Failed to provision staff");
                }
              }}
            />
          </Dialog>

        }
      />

      <Card><CardContent className="grid gap-3 p-4 sm:grid-cols-[1fr_180px_160px]">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input placeholder="Search by name, ID, email…" value={q} onChange={(e) => setQ(e.target.value)} className="pl-9" />
        </div>
        <Select value={dept} onValueChange={setDept}>
          <SelectTrigger><SelectValue placeholder="Department" /></SelectTrigger>
          <SelectContent>{depts.map((d) => <SelectItem key={d} value={d}>{d}</SelectItem>)}</SelectContent>
        </Select>
        <Select value={status} onValueChange={(v) => setStatus(v as never)}>
          <SelectTrigger><SelectValue placeholder="Status" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            <SelectItem value="active">Active</SelectItem>
            <SelectItem value="inactive">Inactive</SelectItem>
          </SelectContent>
        </Select>
      </CardContent></Card>

      {filtered.length === 0 ? (
        <EmptyState icon={UserCog} title="No staff match your filters" description="Try clearing filters or add a new staff member." />
      ) : (
        <Card><CardContent className="p-0">
          <ul className="divide-y divide-border">
            {filtered.map((s) => (
              <li key={s.id} className="grid grid-cols-1 gap-3 p-4 sm:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)_140px_130px_auto] sm:items-center">
                <div className="flex min-w-0 items-center gap-3">
                  <Avatar className="h-10 w-10 shrink-0"><AvatarFallback className="bg-primary/10 text-primary text-xs font-semibold">{s.photoInitial}</AvatarFallback></Avatar>
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold">{s.firstName} {s.lastName}</p>
                    <p className="truncate text-xs text-muted-foreground">{s.id} • {s.email}</p>
                  </div>
                </div>
                <div className="min-w-0 text-xs text-muted-foreground">
                  <p className="truncate">{s.department} · {s.desk}</p>
                  <p className="truncate">{s.mobile}</p>
                </div>
                <Badge variant="outline" className={s.status === "active" ? "bg-success/10 text-success border-success/20" : "bg-muted text-muted-foreground"}>
                  {s.status === "active" ? "Active" : "Inactive"}
                </Badge>
                <span className="text-xs text-muted-foreground">Last active {s.lastActive}</span>
                <div className="flex flex-wrap justify-end gap-2">
                  <ConfirmToggle staff={s} onConfirm={() => toggleStatus(s)} />
                  <Dialog open={editing?.id === s.id} onOpenChange={(o) => setEditing(o ? s : null)}>
                    <DialogTrigger asChild><Button size="sm" variant="ghost">Edit</Button></DialogTrigger>
                    <StaffFormDialog
                      departments={departments.map((d) => d.name)}
                      initial={s}
                      onCancel={() => setEditing(null)}
                      onSubmit={(v) => {
                        setEditing(null);
                        updateStaff(s.id, v);
                        toast.success("Staff updated");
                      }}
                    />
                  </Dialog>

                  <AlertDialog>
                    <AlertDialogTrigger asChild>
                      <Button size="sm" variant="ghost" aria-label={`Delete ${s.firstName} ${s.lastName}`} className="text-error hover:text-error"><Trash2 className="h-4 w-4" /></Button>
                    </AlertDialogTrigger>
                    <AlertDialogContent>
                      <AlertDialogHeader>
                        <AlertDialogTitle>Remove {s.firstName} {s.lastName}?</AlertDialogTitle>
                        <AlertDialogDescription>This will permanently remove the staff record. This action cannot be undone.</AlertDialogDescription>
                      </AlertDialogHeader>
                      <AlertDialogFooter>
                        <AlertDialogCancel>Cancel</AlertDialogCancel>
                        <AlertDialogAction onClick={() => { removeStaff(s.id); toast.success("Staff removed"); }}>Remove</AlertDialogAction>
                      </AlertDialogFooter>
                    </AlertDialogContent>
                  </AlertDialog>
                </div>
              </li>
            ))}
          </ul>
        </CardContent></Card>
      )}
    </div>
  );
}

function ConfirmToggle({ staff, onConfirm }: { staff: Staff; onConfirm: () => void }) {
  const [open, setOpen] = useState(false);
  const activate = staff.status !== "active";
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm" variant="outline">{activate ? "Activate" : "Deactivate"}</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader><DialogTitle>{activate ? "Activate" : "Deactivate"} {staff.firstName} {staff.lastName}?</DialogTitle></DialogHeader>
        <p className="text-sm text-muted-foreground">
          {activate
            ? "This account will regain access to the CliniXAI staff workspace."
            : "This account will lose access. Operational history will be preserved."}
        </p>
        <DialogFooter>
          <Button variant="ghost" onClick={() => setOpen(false)}>Cancel</Button>
          <Button onClick={() => { onConfirm(); setOpen(false); }}>Confirm</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

type StaffFormValues = Omit<Staff, "id" | "lastActive" | "photoInitial" | "status">;

function StaffFormDialog({ departments, initial, onCancel, onSubmit }: {
  departments: string[];
  initial?: Staff;
  onCancel: () => void;
  onSubmit: (values: StaffFormValues) => void;
}) {
  const [form, setForm] = useState<StaffFormValues>({
    firstName: initial?.firstName ?? "",
    lastName: initial?.lastName ?? "",
    email: initial?.email ?? "",
    mobile: initial?.mobile ?? "",
    gender: initial?.gender ?? ("Male" as Staff["gender"]),
    department: initial?.department ?? (departments[0] ?? "Reception"),
    desk: initial?.desk ?? "",
  });
  const submit = () => {
    if (!form.firstName || !form.email) { toast.error("Please fill required fields"); return; }
    onSubmit(form);
  };

  return (
    <DialogContent className="max-w-lg">
      <DialogHeader><DialogTitle>{initial ? "Edit Staff" : "Add Hospital Staff"}</DialogTitle></DialogHeader>
      <div className="grid gap-3 sm:grid-cols-2">
        <div><Label>First Name *</Label><Input value={form.firstName} onChange={(e) => setForm({ ...form, firstName: e.target.value })} /></div>
        <div><Label>Last Name</Label><Input value={form.lastName} onChange={(e) => setForm({ ...form, lastName: e.target.value })} /></div>
        <div className="sm:col-span-2"><Label>Email *</Label><Input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></div>
        <div><Label>Mobile</Label><Input value={form.mobile} onChange={(e) => setForm({ ...form, mobile: e.target.value })} /></div>
        <div><Label>Gender</Label>
          <Select value={form.gender} onValueChange={(v) => setForm({ ...form, gender: v as Staff["gender"] })}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent><SelectItem value="Male">Male</SelectItem><SelectItem value="Female">Female</SelectItem><SelectItem value="Other">Other</SelectItem></SelectContent>
          </Select>
        </div>
        <div><Label>Department</Label>
          <Select value={form.department} onValueChange={(v) => setForm({ ...form, department: v })}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              {Array.from(new Set(["Reception","Billing","Records","Pharmacy","Support",...departments])).map((d) => <SelectItem key={d} value={d}>{d}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <div><Label>Desk / Counter</Label><Input placeholder="e.g. Front Desk A" value={form.desk} onChange={(e) => setForm({ ...form, desk: e.target.value })} /></div>
      </div>
      <p className="text-xs text-muted-foreground">{initial ? "Updates apply immediately." : "The staff member will receive an email invitation to set up their password."}</p>
      <DialogFooter>
        <Button variant="ghost" onClick={onCancel}>Cancel</Button>
        <Button onClick={submit}>{initial ? "Save changes" : "Send invitation"}</Button>
      </DialogFooter>
    </DialogContent>
  );
}
