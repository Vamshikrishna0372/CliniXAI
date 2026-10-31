import { useEffect, useMemo, useState } from "react";
import { createFileRoute, Link, Outlet, useMatch } from "@tanstack/react-router";
import { Search, ChevronRight, ArrowUpDown } from "lucide-react";
import { PageHeader } from "@/components/app-shell/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { EmptyState } from "@/components/dashboard/states";
import { ageFromDob, fmtDate, DOCTORS } from "@/lib/mock/domain";
import { useClinix } from "@/lib/store/clinix-store";
import { useAuth } from "@/lib/auth-context";
import { apiClient } from "@/lib/api-client";

export const Route = createFileRoute("/app/patients")({
  head: () => ({ meta: [{ title: "Patients — CliniXAI" }, { name: "robots", content: "noindex" }] }),
  component: PatientsPage,
});

type SortKey = "name" | "recent";

function PatientsPage() {
  const isDetail = useMatch({ from: "/app/patients/$id", shouldThrow: false });

  const { user } = useAuth();
  const { patients, appointments, doctors } = useClinix();
  const [q, setQ] = useState("");
  const [sort, setSort] = useState<SortKey>("name");
  const [expanded, setExpanded] = useState<string | null>(null);
  const [livePatients, setLivePatients] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  const isDoctor = user?.role === "doctor";
  const doctor = doctors.find((d) => d.email === user?.email || d.id === user?.id);
  const currentDoctorId = doctor ? doctor.id : user?.id;

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    const params: any = { limit: 50 };
    if (q.trim()) params.search = q.trim();
    apiClient.patients
      .list(params)
      .then((res: any) => {
        if (!cancelled && res && res.data) {
          const list = Array.isArray(res.data) ? res.data : res.data.items || [];
          setLivePatients(list);
        }
      })
      .catch((err) => {
        console.warn("Could not load backend patients:", err);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [q]);

  const combinedPatients = useMemo(() => {
    if (livePatients.length > 0) {
      return livePatients.map((p: any) => ({
        id: p.patient_id || p.id,
        firstName: p.first_name || p.firstName,
        lastName: p.last_name || p.lastName,
        dob: p.date_of_birth || p.dob || "1990-01-01",
        gender: p.gender || "Unknown",
        mobile: p.phone || p.mobile || "—",
        email: p.email || "—",
        allergies: p.allergies || [],
        conditions: p.conditions || [],
        medications: p.medications || [],
        lastVisit: p.last_visit || p.lastVisit,
      }));
    }
    return patients;
  }, [livePatients, patients]);

  const scoped = useMemo(() => {
    if (!isDoctor) return combinedPatients;
    if (livePatients.length > 0) return combinedPatients;
    const ids = new Set(appointments.filter((a) => a.doctorId === currentDoctorId || a.doctorId === user?.id).map((a) => a.patientId));
    if (ids.size === 0) return combinedPatients;
    return combinedPatients.filter((p) => ids.has(p.id));
  }, [combinedPatients, appointments, isDoctor, currentDoctorId, user, livePatients]);

  const results = useMemo(() => {
    const filtered = scoped.filter((p) => !q || `${p.firstName} ${p.lastName} ${p.id} ${p.mobile}`.toLowerCase().includes(q.toLowerCase()));
    return [...filtered].sort((a, b) => {
      if (sort === "name") return `${a.firstName} ${a.lastName}`.localeCompare(`${b.firstName} ${b.lastName}`);
      return (b.lastVisit ?? "").localeCompare(a.lastVisit ?? "");
    });
  }, [scoped, q, sort]);

  if (isDetail) {
    return <Outlet />;
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title={isDoctor ? "My patients" : "Patients"}
        description={isDoctor ? "Patients you have seen through your appointments." : "Directory of registered patients."}
        actions={!isDoctor ? <Button asChild><Link to="/app/patient-registration">Register patient</Link></Button> : undefined}
      />
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search by name, ID, mobile…" className="pl-9" aria-label="Search patients" />
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => setSort((s) => (s === "name" ? "recent" : "name"))}
          aria-label="Toggle sort order"
        >
          <ArrowUpDown className="h-4 w-4" /> Sort: {sort === "name" ? "Name" : "Recent visit"}
        </Button>
      </div>
      {results.length === 0 ? <EmptyState title="No patients found" /> : (
        <Card><CardContent className="p-0"><ul className="divide-y divide-border">
            {results.map((p) => {
              const initialFirst = (p.firstName || "P").charAt(0).toUpperCase();
              const initialLast = (p.lastName || "").charAt(0).toUpperCase();

              return (
                <li key={p.id} className="flex flex-wrap items-center gap-3 p-4">
                  <Avatar className="h-10 w-10 shrink-0">
                    <AvatarFallback className="bg-primary/10 text-primary text-xs font-semibold">
                      {initialFirst}{initialLast}
                    </AvatarFallback>
                  </Avatar>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-semibold">
                      <Link to="/app/patients/$id" params={{ id: p.id }} className="hover:underline text-primary">
                        {p.firstName} {p.lastName}
                      </Link>
                    </p>
                    <p className="truncate text-xs text-muted-foreground">{p.id} • {ageFromDob(p.dob)} yrs • {p.gender} • {p.mobile}</p>
                  </div>
                  <div className="hidden text-right text-xs text-muted-foreground sm:block">{p.lastVisit ? `Last visit ${fmtDate(p.lastVisit)}` : "—"}</div>
                  <Button asChild size="sm" variant="outline" className="hidden sm:inline-flex">
                    <Link to="/app/patients/$id" params={{ id: p.id }}>Workspace</Link>
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => setExpanded((e) => (e === p.id ? null : p.id))} aria-expanded={expanded === p.id}>
                    {expanded === p.id ? "Hide" : "Details"} <ChevronRight className={`ml-1 h-4 w-4 transition-transform ${expanded === p.id ? "rotate-90" : ""}`} />
                  </Button>
                  {expanded === p.id && (
                    <div className="basis-full rounded-md border border-border bg-muted/30 p-3 text-xs sm:col-span-4">
                      <p><span className="text-muted-foreground">Conditions:</span> {Array.isArray(p.conditions) ? p.conditions.join(", ") : "None"}</p>
                      <p><span className="text-muted-foreground">Allergies:</span> {Array.isArray(p.allergies) ? p.allergies.join(", ") : "None"}</p>
                      <p><span className="text-muted-foreground">Medications:</span> {Array.isArray(p.medications) ? p.medications.join(", ") : "None"}</p>
                      <div className="mt-2 flex flex-wrap gap-2">
                        <Button asChild size="sm" variant="default">
                          <Link to="/app/patients/$id" params={{ id: p.id }}>Open Clinical Workspace</Link>
                        </Button>
                        <Button asChild size="sm" variant="outline"><Link to="/app/consultations">Open consultations</Link></Button>
                        <Button asChild size="sm" variant="outline"><Link to="/app/follow-ups">Follow-ups</Link></Button>
                      </div>
                    </div>
                  )}
                </li>
              );
            })}
        </ul></CardContent></Card>
      )}
    </div>
  );
}
