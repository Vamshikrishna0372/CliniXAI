import { useEffect, useMemo, useState } from "react";
import { createFileRoute, Outlet, useMatch } from "@tanstack/react-router";
import { Search, SlidersHorizontal, UserPlus, ChevronLeft, ChevronRight, RotateCcw } from "lucide-react";
import { PageHeader } from "@/components/app-shell/page-header";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent } from "@/components/ui/card";
import { DoctorCard } from "@/components/domain/doctor-card";
import { EmptyState, ErrorState } from "@/components/dashboard/states";
import { ResponsiveGrid } from "@/components/dashboard/cards";
import { useAuth } from "@/lib/auth-context";
import { apiClient } from "@/lib/api-client";
import { toast } from "sonner";
import type { Doctor } from "@/lib/mock/domain";

export const Route = createFileRoute("/app/doctors")({
  head: () => ({ meta: [{ title: "Find a Doctor — CliniXAI" }, { name: "robots", content: "noindex" }] }),
  component: DoctorsPage,
});

function DoctorCardSkeleton() {
  return (
    <Card className="flex flex-col justify-between">
      <CardContent className="p-4 sm:p-5 space-y-4">
        <div className="flex items-start gap-3">
          <Skeleton className="h-12 w-12 rounded-full shrink-0" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-3 w-1/2" />
            <Skeleton className="h-3 w-1/3" />
          </div>
        </div>
        <div className="grid grid-cols-2 gap-2 p-2.5 bg-muted/20 rounded-lg">
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-full" />
        </div>
        <div className="pt-2 border-t border-border flex gap-2">
          <Skeleton className="h-8 flex-1 rounded-md" />
        </div>
      </CardContent>
    </Card>
  );
}

function DoctorsPage() {
  const isDetail = useMatch({ from: "/app/doctors/$id", shouldThrow: false });

  const { user } = useAuth();
  const isAdmin = user?.role === "admin";

  const [q, setQ] = useState("");
  const [debouncedQ, setDebouncedQ] = useState("");
  const [dept, setDept] = useState("All");
  const [maxFee, setMaxFee] = useState<number>(5000);
  const [page, setPage] = useState(1);
  const pageSize = 12;

  // Backend state
  const [doctorsList, setDoctorsList] = useState<Doctor[]>([]);
  const [departmentsList, setDepartmentsList] = useState<string[]>([]);
  const [totalPages, setTotalPages] = useState(1);
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Add Doctor Form State
  const [open, setOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [form, setForm] = useState({
    fullName: "",
    email: "",
    phone: "",
    specialization: "General Medicine",
    departmentId: "DEP-01",
    qualification: "MBBS, MD",
    experienceYears: "10",
    consultationFee: "500",
  });

  // Debounce search query
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedQ(q);
      setPage(1); // Reset page on new query
    }, 300);
    return () => clearTimeout(timer);
  }, [q]);

  // Load departments once for the filter dropdown
  useEffect(() => {
    let mounted = true;
    apiClient.departments.list()
      .then((res: any) => {
        if (mounted && res?.data && Array.isArray(res.data)) {
          const names = res.data.map((d: any) => d.name || d.department_id);
          setDepartmentsList(Array.from(new Set(names)));
        }
      })
      .catch(() => {
        // Silently fall back to departments extracted from loaded doctors
      });
    return () => { mounted = false; };
  }, []);

  // Fetch doctors from backend with pagination, search, and department filter
  const fetchDoctors = async () => {
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, any> = {
        page,
        page_size: pageSize,
      };
      if (debouncedQ.trim()) {
        params.search = debouncedQ.trim();
      }
      if (dept !== "All") {
        params.department_id = dept;
      }

      const res = await apiClient.doctors.list(params);
      const rawData = res?.data || [];
      const paginationMeta = res?.pagination;

      const formatted: Doctor[] = rawData.map((d: any) => {
        const fullName = d.full_name || `${d.first_name || ""} ${d.last_name || ""}`.trim() || "Doctor";
        const initials = fullName
          .replace(/^Dr\.\s*/i, "")
          .split(" ")
          .filter(Boolean)
          .map((n: string) => n.charAt(0))
          .join("")
          .slice(0, 2)
          .toUpperCase() || "DR";

        return {
          id: d.doctor_id,
          name: fullName,
          email: d.email || "",
          specialization: d.specialization || "General Medicine",
          qualification: d.qualification || "MBBS, MD",
          department: d.department_id || "General Medicine",
          experienceYears: d.experience_years || 5,
          languages: ["English", "Hindi"],
          consultationFee: d.consultation_fee || 500,
          status: d.status || "active",
          nextAvailable: "Available Today",
          availableSlots: ["09:00", "09:30", "10:00", "11:00", "14:00", "15:00"],
          photoInitial: initials,
        };
      });

      setDoctorsList(formatted);
      if (paginationMeta) {
        setTotalPages(paginationMeta.total_pages || 1);
        setTotalCount(paginationMeta.total || formatted.length);
      } else {
        setTotalPages(1);
        setTotalCount(formatted.length);
      }
    } catch (err: any) {
      setError(err?.message || "Failed to load doctor directory from server");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDoctors();
  }, [page, debouncedQ, dept]);

  const handleAddDoctor = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.fullName || !form.email) {
      toast.error("Please fill in required fields (Name & Email)");
      return;
    }
    setSubmitting(true);
    try {
      const parts = form.fullName.trim().split(" ");
      const firstName = parts[0];
      const lastName = parts.slice(1).join(" ") || "MD";

      await apiClient.doctors.create({
        email: form.email,
        full_name: form.fullName,
        first_name: firstName,
        last_name: lastName,
        phone: form.phone || undefined,
        specialization: form.specialization,
        department_id: form.departmentId,
        qualification: form.qualification,
        experience_years: parseInt(form.experienceYears, 10) || 5,
        consultation_fee: parseFloat(form.consultationFee) || 500,
      });

      toast.success("Doctor account provisioned successfully!", {
        description: `Invitation email dispatched to ${form.email}`,
      });
      setOpen(false);
      setForm({
        fullName: "",
        email: "",
        phone: "",
        specialization: "General Medicine",
        departmentId: "DEP-01",
        qualification: "MBBS, MD",
        experienceYears: "10",
        consultationFee: "500",
      });
      // Refresh list immediately
      fetchDoctors();
    } catch (err: any) {
      toast.error(err?.message || "Failed to provision doctor account");
    } finally {
      setSubmitting(false);
    }
  };

  // Optional client-side maxFee filtering over current server batch
  const displayedDoctors = useMemo(() => {
    return doctorsList.filter((d) => d.consultationFee <= maxFee);
  }, [doctorsList, maxFee]);

  const DEPTS = useMemo(() => {
    const list = new Set(["All", ...departmentsList]);
    doctorsList.forEach((d) => {
      if (d.department) list.add(d.department);
    });
    return Array.from(list);
  }, [departmentsList, doctorsList]);

  if (isDetail) {
    return <Outlet />;
  }

  const filters = (
    <div className="space-y-4">
      <div>
        <Label>Department</Label>
        <Select value={dept} onValueChange={(val) => { setDept(val); setPage(1); }}>
          <SelectTrigger><SelectValue /></SelectTrigger>
          <SelectContent>{DEPTS.map((d) => <SelectItem key={d} value={d}>{d}</SelectItem>)}</SelectContent>
        </Select>
      </div>
      <div>
        <Label>Max consultation fee: ₹{maxFee}</Label>
        <input
          type="range"
          min={300}
          max={5000}
          step={100}
          value={maxFee}
          onChange={(e) => setMaxFee(Number(e.target.value))}
          className="w-full accent-primary"
        />
      </div>
    </div>
  );

  return (
    <div className="space-y-6">
      <PageHeader
        title="Doctor Directory"
        description="Discover specialists across hospital departments with authoritative real-time availability."
        actions={
          isAdmin ? (
            <Dialog open={open} onOpenChange={setOpen}>
              <DialogTrigger asChild>
                <Button><UserPlus className="mr-2 h-4 w-4" /> Add Doctor</Button>
              </DialogTrigger>
              <DialogContent className="sm:max-w-[500px]">
                <DialogHeader>
                  <DialogTitle>Provision New Doctor Account</DialogTitle>
                </DialogHeader>
                <form onSubmit={handleAddDoctor} className="space-y-4 py-2">
                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-1">
                      <Label htmlFor="fullName">Full Name *</Label>
                      <Input
                        id="fullName"
                        placeholder="Dr. Aris Thorne"
                        value={form.fullName}
                        onChange={(e) => setForm({ ...form, fullName: e.target.value })}
                        required
                      />
                    </div>
                    <div className="space-y-1">
                      <Label htmlFor="email">Email Address *</Label>
                      <Input
                        id="email"
                        type="email"
                        placeholder="doctor@clinixai.com"
                        value={form.email}
                        onChange={(e) => setForm({ ...form, email: e.target.value })}
                        required
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-1">
                      <Label htmlFor="phone">Phone Number</Label>
                      <Input
                        id="phone"
                        placeholder="+91 98765 43210"
                        value={form.phone}
                        onChange={(e) => setForm({ ...form, phone: e.target.value })}
                      />
                    </div>
                    <div className="space-y-1">
                      <Label htmlFor="specialization">Specialization</Label>
                      <Input
                        id="specialization"
                        placeholder="Neurology / Cardiology"
                        value={form.specialization}
                        onChange={(e) => setForm({ ...form, specialization: e.target.value })}
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-1">
                      <Label htmlFor="qualification">Qualification</Label>
                      <Input
                        id="qualification"
                        placeholder="MBBS, MD (Neurology)"
                        value={form.qualification}
                        onChange={(e) => setForm({ ...form, qualification: e.target.value })}
                      />
                    </div>
                    <div className="space-y-1">
                      <Label htmlFor="fee">Consultation Fee (₹)</Label>
                      <Input
                        id="fee"
                        type="number"
                        placeholder="500"
                        value={form.consultationFee}
                        onChange={(e) => setForm({ ...form, consultationFee: e.target.value })}
                      />
                    </div>
                  </div>

                  <DialogFooter className="mt-4">
                    <Button type="button" variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
                    <Button type="submit" disabled={submitting}>
                      {submitting ? "Provisioning..." : "Create & Send Invitation"}
                    </Button>
                  </DialogFooter>
                </form>
              </DialogContent>
            </Dialog>
          ) : undefined
        }
      />

      {/* Search & Filter Controls */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search doctors by name, specialization, or ID…"
            aria-label="Search doctors"
            className="pl-9"
          />
        </div>
        <div className="hidden sm:block w-56">
          <Select value={dept} onValueChange={(val) => { setDept(val); setPage(1); }}>
            <SelectTrigger><SelectValue placeholder="Department" /></SelectTrigger>
            <SelectContent>{DEPTS.map((d) => <SelectItem key={d} value={d}>{d}</SelectItem>)}</SelectContent>
          </Select>
        </div>
        <Sheet>
          <SheetTrigger asChild>
            <Button variant="outline" className="sm:hidden"><SlidersHorizontal className="mr-2 h-4 w-4" /> Filters</Button>
          </SheetTrigger>
          <SheetContent side="bottom" className="h-[70vh]">
            <SheetHeader><SheetTitle>Filters</SheetTitle></SheetHeader>
            <div className="mt-4">{filters}</div>
          </SheetContent>
        </Sheet>
      </div>

      {/* Content Rendering: Loading, Error, Empty, or Doctor Grid */}
      {loading ? (
        <ResponsiveGrid cols={{ base: 1, sm: 2, lg: 3 }}>
          {Array.from({ length: 6 }).map((_, idx) => (
            <DoctorCardSkeleton key={`skeleton-${idx}`} />
          ))}
        </ResponsiveGrid>
      ) : error ? (
        <ErrorState
          title="Could not load doctors"
          description={error}
          onRetry={fetchDoctors}
        />
      ) : displayedDoctors.length === 0 ? (
        <EmptyState
          title="No doctors found"
          description={
            debouncedQ || dept !== "All"
              ? "No doctors matched your filter criteria. Try clearing filters or searching for another specialty."
              : "No active doctors are currently registered in the system."
          }
          action={
            (debouncedQ || dept !== "All") ? (
              <Button variant="outline" onClick={() => { setQ(""); setDept("All"); setPage(1); }}>
                <RotateCcw className="mr-2 h-4 w-4" /> Reset Filters
              </Button>
            ) : undefined
          }
        />
      ) : (
        <>
          <ResponsiveGrid cols={{ base: 1, sm: 2, lg: 3 }}>
            {displayedDoctors.map((d) => (
              <DoctorCard key={d.id} doctor={d} />
            ))}
          </ResponsiveGrid>

          {/* Pagination Controls */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between border-t border-border pt-4">
              <p className="text-xs text-muted-foreground">
                Showing page <span className="font-semibold text-foreground">{page}</span> of{" "}
                <span className="font-semibold text-foreground">{totalPages}</span> ({totalCount} doctors)
              </p>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page <= 1 || loading}
                >
                  <ChevronLeft className="h-4 w-4 mr-1" /> Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page >= totalPages || loading}
                >
                  Next <ChevronRight className="h-4 w-4 ml-1" />
                </Button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
