import { useEffect, useState } from "react";
import { createFileRoute, Link, useParams } from "@tanstack/react-router";
import { Calendar, Clock, IndianRupee, GraduationCap, Languages, ArrowLeft, RotateCcw, ChevronRight } from "lucide-react";
import { PageHeader } from "@/components/app-shell/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { EmptyState, ErrorState } from "@/components/dashboard/states";
import { useAuth } from "@/lib/auth-context";
import { apiClient } from "@/lib/api-client";
import type { Doctor } from "@/lib/mock/domain";

export const Route = createFileRoute("/app/doctors/$id")({
  head: () => ({ meta: [{ title: "Doctor Profile — CliniXAI" }, { name: "robots", content: "noindex" }] }),
  component: DoctorProfilePage,
});

function DoctorProfileSkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-9 w-32" />
      <div className="space-y-2">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-4 w-48" />
      </div>
      <Card>
        <CardContent className="p-4 sm:p-6">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start">
            <Skeleton className="h-20 w-20 rounded-full shrink-0" />
            <div className="flex-1 space-y-3">
              <div className="grid gap-2 sm:grid-cols-2">
                <Skeleton className="h-5 w-40" />
                <Skeleton className="h-5 w-40" />
                <Skeleton className="h-5 w-40" />
                <Skeleton className="h-5 w-40" />
              </div>
              <Skeleton className="h-8 w-48" />
            </div>
            <Skeleton className="h-10 w-44 rounded-md" />
          </div>
        </CardContent>
      </Card>
      <Card>
        <CardContent className="p-4 sm:p-6 space-y-3">
          <Skeleton className="h-5 w-36" />
          <div className="grid grid-cols-3 gap-2 sm:grid-cols-6">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-12 w-full rounded-lg" />
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function DoctorProfilePage() {
  const { id } = useParams({ from: "/app/doctors/$id" });
  const { user } = useAuth();
  const isPatient = user?.role === "patient";

  const [doctor, setDoctor] = useState<Doctor | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Phase 6: Live Dynamic Date Availability
  const todayStr = new Date().toISOString().split("T")[0];
  const [selectedDate, setSelectedDate] = useState<string>(todayStr);
  const [liveSlots, setLiveSlots] = useState<string[]>([]);
  const [slotsLoading, setSlotsLoading] = useState(false);
  const [slotsError, setSlotsError] = useState<string | null>(null);

  const fetchDoctor = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiClient.doctors.getDetail(id);
      const d = res?.data;
      if (!d) {
        setDoctor(null);
        return;
      }

      const fullName = d.full_name || `${d.first_name || ""} ${d.last_name || ""}`.trim() || "Doctor";
      const initials = fullName
        .replace(/^Dr\.\s*/i, "")
        .split(" ")
        .filter(Boolean)
        .map((n: string) => n.charAt(0))
        .join("")
        .slice(0, 2)
        .toUpperCase() || "DR";

      const formatted: Doctor = {
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
        availableSlots: [],
        photoInitial: initials,
      };

      setDoctor(formatted);
    } catch (err: any) {
      if (err?.status === 404 || err?.statusCode === 404) {
        setDoctor(null);
      } else {
        setError(err?.message || "Failed to load doctor profile");
      }
    } finally {
      setLoading(false);
    }
  };

  const fetchLiveSlots = async (targetDate: string) => {
    if (!id || !targetDate) return;
    setSlotsLoading(true);
    setSlotsError(null);
    try {
      const res = await apiClient.doctors.getAvailability(id, targetDate);
      const rawSlots = res?.data?.available_slots || [];
      const times: string[] = rawSlots.map((s: any) => s.start_time || s);
      setLiveSlots(times);
    } catch (err: any) {
      setSlotsError(err?.message || "Failed to load available slots for this date");
      setLiveSlots([]);
    } finally {
      setSlotsLoading(false);
    }
  };

  useEffect(() => {
    fetchDoctor();
  }, [id]);

  useEffect(() => {
    if (id && selectedDate) {
      fetchLiveSlots(selectedDate);
    }
  }, [id, selectedDate]);

  if (loading) {
    return <DoctorProfileSkeleton />;
  }

  if (error) {
    return (
      <div className="space-y-4">
        <Button asChild variant="ghost" size="sm" className="mb-2">
          <Link to="/app/doctors"><ArrowLeft className="mr-1 h-4 w-4" /> All doctors</Link>
        </Button>
        <ErrorState
          title="Could not load doctor profile"
          description={error}
          onRetry={fetchDoctor}
        />
      </div>
    );
  }

  if (!doctor) {
    return (
      <EmptyState
        title="Doctor not found"
        description={`No active doctor profile matches the requested ID (${id}).`}
        action={
          <Button asChild>
            <Link to="/app/doctors"><ArrowLeft className="mr-1 h-4 w-4" /> Back to doctors</Link>
          </Button>
        }
      />
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <Button asChild variant="ghost" size="sm" className="mb-2">
          <Link to="/app/doctors"><ArrowLeft className="mr-1 h-4 w-4" /> All doctors</Link>
        </Button>
        <PageHeader title={doctor.name} description={`${doctor.specialization} • ${doctor.department}`} />
      </div>

      <Card>
        <CardContent className="p-4 sm:p-6">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start">
            <Avatar className="h-20 w-20 shrink-0">
              <AvatarFallback className="bg-primary/10 text-primary text-xl font-bold">
                {doctor.photoInitial}
              </AvatarFallback>
            </Avatar>
            <div className="min-w-0 flex-1 space-y-3">
              <div className="grid gap-2 text-sm text-muted-foreground sm:grid-cols-2">
                <span className="flex items-center gap-2">
                  <GraduationCap className="h-4 w-4 text-primary" /> {doctor.qualification}
                </span>
                <span className="flex items-center gap-2">
                  <Clock className="h-4 w-4 text-primary" /> {doctor.experienceYears} years experience
                </span>
                <span className="flex items-center gap-2">
                  <IndianRupee className="h-4 w-4 text-primary" /> Consultation ₹{doctor.consultationFee}
                </span>
                <span className="flex items-center gap-2">
                  <Languages className="h-4 w-4 text-primary" /> {doctor.languages.join(", ")}
                </span>
              </div>
              <div>
                <p className="text-xs uppercase tracking-wide text-muted-foreground">Status</p>
                <p className="text-sm font-medium text-foreground capitalize">{doctor.status || "active"}</p>
              </div>
            </div>
            {isPatient ? (
              <Button asChild size="lg" className="w-full sm:w-auto">
                <Link to="/app/book" search={{ doctorId: doctor.id, step: 1 }}>
                  Book Appointment
                </Link>
              </Button>
            ) : (
              <Button asChild size="lg" variant="outline" className="w-full sm:w-auto">
                <Link to="/app/appointments">
                  View Doctor Appointments
                </Link>
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Phase 6: Live Doctor Availability Section */}
      <Card>
        <CardContent className="p-4 sm:p-6 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-border pb-3">
            <div>
              <p className="text-sm font-semibold text-foreground">Doctor Availability Schedule</p>
              <p className="text-xs text-muted-foreground">Authoritative available slots calculated from doctor schedule</p>
            </div>
            <div className="flex items-center gap-2">
              <Label htmlFor="avail-date" className="text-xs font-medium shrink-0">Date:</Label>
              <Input
                id="avail-date"
                type="date"
                min={todayStr}
                value={selectedDate}
                onChange={(e) => setSelectedDate(e.target.value)}
                className="w-40 text-xs"
              />
            </div>
          </div>

          {slotsLoading ? (
            <div className="grid grid-cols-3 gap-2 sm:grid-cols-6 pt-2">
              {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-11 w-full rounded-lg" />
              ))}
            </div>
          ) : slotsError ? (
            <div className="rounded-lg border border-error/20 bg-error/5 p-4 text-center">
              <p className="text-xs text-error font-medium">{slotsError}</p>
              <Button
                variant="outline"
                size="sm"
                onClick={() => fetchLiveSlots(selectedDate)}
                className="mt-2 text-xs"
              >
                <RotateCcw className="mr-1 h-3.5 w-3.5" /> Try Again
              </Button>
            </div>
          ) : liveSlots.length === 0 ? (
            <div className="rounded-lg border border-dashed border-border p-6 text-center">
              <p className="text-sm font-medium text-foreground">No available slots on this date</p>
              <p className="text-xs text-muted-foreground mt-1">
                The doctor may not be scheduled or all appointment slots have already been filled.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-3 gap-2 sm:grid-cols-6 pt-2">
              {liveSlots.map((s) => (
                isPatient ? (
                  <Link
                    key={s}
                    to="/app/book"
                    search={{ doctorId: doctor.id, step: 1 }}
                    className="rounded-lg border border-border p-2 text-center text-sm font-medium hover:border-primary hover:bg-primary/5 transition-colors"
                  >
                    <Calendar className="mx-auto mb-1 h-3.5 w-3.5 text-muted-foreground" />
                    {s}
                  </Link>
                ) : (
                  <div key={s} className="rounded-lg border border-border p-2 text-center text-sm font-medium bg-muted/20">
                    <Calendar className="mx-auto mb-1 h-3.5 w-3.5 text-muted-foreground" />
                    {s}
                  </div>
                )
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
