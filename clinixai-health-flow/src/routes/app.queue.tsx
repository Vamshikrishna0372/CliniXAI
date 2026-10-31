import { useCallback, useEffect, useState } from "react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { PhoneCall, SkipForward, RotateCcw, Eye, CheckCircle2, RefreshCw } from "lucide-react";
import { PageHeader } from "@/components/app-shell/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/dashboard/states";
import { toast } from "sonner";
import { useClinix } from "@/lib/store/clinix-store";
import { apiClient } from "@/lib/api-client";

export const Route = createFileRoute("/app/queue")({
  head: () => ({ meta: [{ title: "Queue — CliniXAI" }, { name: "robots", content: "noindex" }] }),
  component: QueuePage,
});

function QueuePage() {
  const { queue: mockQueue, patients, doctors, callNextPatient, setQueueStatus } = useClinix();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [liveQueue, setLiveQueue] = useState<any[]>([]);

  const fetchQueue = useCallback(async () => {
    try {
      setLoading(true);
      const res = await apiClient.appointments.getQueue();
      if (res && res.data) {
        const items = Array.isArray(res.data) ? res.data : res.data.items || [];
        setLiveQueue(items);
      }
    } catch (err) {
      console.warn("Could not load backend queue, relying on current store:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchQueue();
    const onFocus = () => fetchQueue();
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, [fetchQueue]);

  // Combine live backend queue items with mock store fallback
  const displayQueue = liveQueue.length > 0
    ? liveQueue.map((item: any) => ({
        appointmentId: item.appointment_id || item.id,
        token: item.queue?.token_number || item.token_number || item.token || "A-001",
        position: item.queue?.position || 1,
        status: (item.status || "in_queue").toLowerCase().replace("_", "-"),
        rawStatus: item.status,
        patientId: item.patient_id,
        patientName: item.patient_name || (item.patient ? `${item.patient.first_name} ${item.patient.last_name}` : null),
        doctorId: item.doctor_id,
        doctorName: item.doctor_name || (item.doctor ? item.doctor.full_name : null),
        checkInTime: item.check_in?.checked_in_at ? new Date(item.check_in.checked_in_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "Today",
        estWaitMin: Math.max(5, (item.queue?.position || 1) * 10),
      }))
    : mockQueue;

  const sorted = [...displayQueue].sort((a, b) => a.position - b.position);

  const callNext = async () => {
    const nextWaiting = sorted.find((e) => e.status === "in-queue" || e.status === "waiting" || e.status === "checked-in");
    if (!nextWaiting) {
      toast.info("No waiting patients in queue");
      return;
    }
    await callPatient(nextWaiting.appointmentId, nextWaiting.token);
  };

  const callPatient = async (appointmentId: string, token: string) => {
    try {
      await apiClient.appointments.callPatient(appointmentId);
      toast.success(`Called ${token} into consultation room`);
      await fetchQueue();
    } catch (err: any) {
      toast.error(err?.message || `Failed to call ${token} into consultation room.`);
    }
  };

  const completePatient = async (appointmentId: string, token: string) => {
    try {
      await apiClient.appointments.complete(appointmentId);
      toast.success(`${token} marked completed`);
      await fetchQueue();
    } catch (err: any) {
      toast.error(err?.message || `Failed to mark ${token} completed.`);
    }
  };

  const viewPatient = (patientId: string) => {
    void patientId;
    navigate({ to: "/app/patients" });
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Live Queue"
        description="Manage real-time patient flow and front-desk consultation coordination."
        actions={
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={fetchQueue} disabled={loading}>
              <RefreshCw className={`mr-1.5 h-4 w-4 ${loading ? "animate-spin" : ""}`} /> Refresh
            </Button>
            <Button onClick={callNext}>
              <PhoneCall className="mr-1 h-4 w-4" /> Call next
            </Button>
          </div>
        }
      />
      {sorted.length === 0 ? (
        <EmptyState title="Queue is empty" description="Checked-in patients will appear here immediately." />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {sorted.map((e: any, index: number) => {
            const p = patients.find((pt) => pt.id === e.patientId);
            const d = doctors.find((doc) => doc.id === e.doctorId);
            const patName = e.patientName || (p ? `${p.firstName} ${p.lastName}` : e.patientId);
            const docName = e.doctorName || d?.name || e.doctorId;

            return (
              <Card key={e.appointmentId || `${e.token}-${index}`} className="card-hover">
                <CardContent className="p-4">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <p className="text-xs text-muted-foreground">Queue Token</p>
                      <p className="font-display text-2xl font-bold text-primary">{e.token}</p>
                    </div>
                    <Badge variant={e.status === "in-consultation" || e.status === "called" ? "default" : "outline"} className="capitalize">
                      {e.status.replace("-", " ")}
                    </Badge>
                  </div>
                  <p className="mt-3 text-sm font-semibold">{patName}</p>
                  <p className="text-xs text-muted-foreground">{docName} • checked in {e.checkInTime}</p>
                  <p className="mt-1 text-xs text-muted-foreground">Position #{e.position} • ~{e.estWaitMin} min</p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={e.status === "called" || e.status === "in-consultation"}
                      onClick={() => callPatient(e.appointmentId, e.token)}
                    >
                      <PhoneCall className="mr-1 h-3.5 w-3.5" /> Call
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      disabled={e.status === "completed"}
                      onClick={() => completePatient(e.appointmentId, e.token)}
                    >
                      <CheckCircle2 className="mr-1 h-3.5 w-3.5" /> Done
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      aria-label={`View patient ${patName}`}
                      onClick={() => viewPatient(e.patientId)}
                    >
                      <Eye className="mr-1 h-3.5 w-3.5" /> Patient
                    </Button>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
