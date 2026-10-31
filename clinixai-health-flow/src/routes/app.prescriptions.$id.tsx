import { useEffect, useState } from "react";
import { createFileRoute, Link, useParams } from "@tanstack/react-router";
import {
  ArrowLeft, Download, Printer, RefreshCw, AlertCircle, CheckCircle2,
  XCircle, Ban, Stethoscope, User, Calendar, ShieldCheck, Clock
} from "lucide-react";
import { PageHeader } from "@/components/app-shell/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { BrandMark } from "@/components/brand-mark";
import { EmptyState } from "@/components/dashboard/states";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription,
  AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { useAuth } from "@/lib/auth-context";
import { apiClient } from "@/lib/api-client";
import { toast } from "sonner";

export const Route = createFileRoute("/app/prescriptions/$id")({
  head: () => ({ meta: [{ title: "Prescription — CliniXAI" }, { name: "robots", content: "noindex" }] }),
  component: PrescriptionDetailPage,
});

interface MedicationItem {
  name: string;
  generic_name?: string;
  strength?: string;
  dosage: string;
  frequency: string;
  route?: string;
  duration: string;
  timing?: string;
  instructions?: string;
}

interface PrescriptionDoc {
  prescription_id: string;
  consultation_id: string;
  appointment_id?: string;
  patient_id?: string;
  doctor_id: string;
  medical_record_id?: string;
  medications: MedicationItem[];
  instructions?: string;
  notes?: string;
  status: "active" | "issued" | "cancelled" | "draft";
  prescription_date?: string;
  issued_at?: string;
  issued_by?: string;
  created_at: string;
  updated_at?: string;
  cancelled_at?: string;
  cancelled_by?: string;
  cancellation_reason?: string;
}

function PrescriptionDetailPage() {
  const { id } = useParams({ from: "/app/prescriptions/$id" });
  const { user } = useAuth();
  const [rx, setRx] = useState<PrescriptionDoc | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Cancellation State
  const [cancelOpen, setCancelOpen] = useState(false);
  const [cancelReason, setCancelReason] = useState("");
  const [cancelling, setCancelling] = useState(false);

  const fetchPrescription = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiClient.prescriptions.getDetail(id);
      const data = res?.data || res;
      setRx(data);
    } catch (err: any) {
      const msg = err?.message || "Failed to load prescription.";
      setError(msg);
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPrescription();
  }, [id]);

  const handleCancelPrescription = async () => {
    if (!cancelReason.trim()) {
      toast.error("Please enter a clinical reason for cancelling this prescription.");
      return;
    }
    setCancelling(true);
    try {
      const res = await apiClient.prescriptions.cancel(id, { cancellation_reason: cancelReason.trim() });
      const updated = res?.data || res;
      setRx(updated);
      setCancelOpen(false);
      toast.success("Prescription successfully cancelled.");
    } catch (err: any) {
      toast.error(err?.message || "Failed to cancel prescription.");
    } finally {
      setCancelling(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <Button asChild variant="ghost" size="sm">
          <Link to="/app/prescriptions">
            <ArrowLeft className="h-4 w-4 mr-1" /> Back to Prescriptions
          </Link>
        </Button>
        <Card className="border-border/60">
          <CardContent className="p-16 text-center text-muted-foreground flex flex-col items-center justify-center gap-3">
            <RefreshCw className="h-7 w-7 animate-spin text-primary" />
            <p className="text-sm font-medium text-foreground">Retrieving clinical prescription record…</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (error || !rx) {
    return (
      <div className="space-y-6">
        <Button asChild variant="ghost" size="sm">
          <Link to="/app/prescriptions">
            <ArrowLeft className="h-4 w-4 mr-1" /> Back to Prescriptions
          </Link>
        </Button>
        <EmptyState
          icon={AlertCircle}
          title="Prescription not found"
          description={error || "The requested prescription record does not exist or access was denied."}
          action={
            <Button asChild variant="outline">
              <Link to="/app/prescriptions">View All Prescriptions</Link>
            </Button>
          }
        />
      </div>
    );
  }

  const isActive = rx.status === "active" || rx.status === "issued";
  const isDoctor = user?.role === "doctor" || user?.role === "admin";
  const dateFormatted = rx.prescription_date || (rx.created_at ? new Date(rx.created_at).toLocaleDateString() : "—");

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Button asChild variant="ghost" size="sm">
          <Link to="/app/prescriptions">
            <ArrowLeft className="mr-1 h-4 w-4" /> All prescriptions
          </Link>
        </Button>
        <div className="flex flex-wrap items-center gap-2 print:hidden">
          {isActive && isDoctor && (
            <AlertDialog open={cancelOpen} onOpenChange={setCancelOpen}>
              <AlertDialogTrigger asChild>
                <Button size="sm" variant="destructive" className="gap-1.5 shadow-sm">
                  <Ban className="h-3.5 w-3.5" /> Cancel Prescription
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Cancel Prescription {rx.prescription_id}?</AlertDialogTitle>
                  <AlertDialogDescription asChild>
                    <div className="text-sm text-muted-foreground space-y-2">
                      <p>
                        Cancelling this prescription will mark it as inactive and permanently document the cancellation in the
                        patient's electronic medical record and audit log.
                      </p>
                      <div className="pt-2">
                        <Label htmlFor="cancelReason" className="text-foreground font-medium">
                          Clinical Reason for Cancellation <span className="text-destructive">*</span>
                        </Label>
                        <Textarea
                          id="cancelReason"
                          rows={3}
                          value={cancelReason}
                          onChange={(e) => setCancelReason(e.target.value)}
                          placeholder="e.g. Patient allergic reaction, medication adjustment needed, duplicate order…"
                          className="mt-1 font-sans text-sm"
                        />
                      </div>
                    </div>
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel disabled={cancelling}>Back</AlertDialogCancel>
                  <AlertDialogAction
                    onClick={handleCancelPrescription}
                    disabled={cancelling || !cancelReason.trim()}
                    className="bg-destructive hover:bg-destructive/90 text-destructive-foreground"
                  >
                    {cancelling ? "Cancelling…" : "Confirm Cancellation"}
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          )}

          <Button size="sm" variant="outline" onClick={() => window.print()} className="gap-1.5 shadow-sm">
            <Printer className="h-3.5 w-3.5" /> Print
          </Button>
        </div>
      </div>

      <Card className="border-border/80 shadow-sm print:border-none print:shadow-none">
        <CardContent className="p-6 sm:p-8 space-y-6">
          {/* Header */}
          <div className="flex flex-wrap items-start justify-between gap-4 border-b border-border pb-6">
            <div>
              <BrandMark size="sm" />
              <p className="mt-2 text-xs text-muted-foreground">
                CliniXAI Clinical Health Network<br />
                Multi-Specialty Medical Centre
              </p>
            </div>
            <div className="text-right">
              <div className="flex items-center justify-end gap-2">
                <span className="text-xs uppercase tracking-wide text-muted-foreground font-semibold">
                  Prescription
                </span>
                <Badge
                  variant="outline"
                  className={
                    isActive
                      ? "border-success/40 bg-success/10 text-success text-xs font-semibold"
                      : "border-destructive/40 bg-destructive/10 text-destructive text-xs font-semibold"
                  }
                >
                  {isActive ? (
                    <span className="flex items-center gap-1">
                      <CheckCircle2 className="h-3 w-3" /> Active
                    </span>
                  ) : (
                    <span className="flex items-center gap-1">
                      <XCircle className="h-3 w-3" /> Cancelled
                    </span>
                  )}
                </Badge>
              </div>
              <p className="font-display text-xl font-bold tracking-tight text-foreground mt-1">
                {rx.prescription_id}
              </p>
              <p className="text-xs text-muted-foreground">{dateFormatted}</p>
            </div>
          </div>

          {/* Encounter & Parties Metadata */}
          <div className="grid gap-4 sm:grid-cols-3 p-4 rounded-xl bg-muted/20 border border-border/60 text-xs">
            <div>
              <p className="font-semibold uppercase tracking-wider text-muted-foreground">Prescribing Physician</p>
              <p className="text-sm font-bold text-foreground mt-0.5">{rx.issued_by || rx.doctor_id}</p>
              <p className="text-muted-foreground">Doctor ID: {rx.doctor_id}</p>
            </div>
            <div>
              <p className="font-semibold uppercase tracking-wider text-muted-foreground">Patient</p>
              <p className="text-sm font-bold text-foreground mt-0.5">{rx.patient_id || "Registered Patient"}</p>
              <p className="text-muted-foreground">Patient ID: {rx.patient_id || "—"}</p>
              {rx.patient_id && isDoctor && (
                <Button asChild size="sm" variant="outline" className="h-6 text-[11px] px-2 mt-1.5 gap-1">
                  <Link to="/app/patients/$id" params={{ id: rx.patient_id }}>
                    <User className="h-3 w-3" /> Clinical Workspace
                  </Link>
                </Button>
              )}
            </div>
            <div>
              <p className="font-semibold uppercase tracking-wider text-muted-foreground">Clinical Encounter</p>
              <p className="text-sm font-bold text-primary mt-0.5">
                <Link to="/app/consultations/$id" params={{ id: rx.consultation_id }} className="hover:underline">
                  {rx.consultation_id}
                </Link>
              </p>
              {rx.appointment_id && <p className="text-muted-foreground">Appointment: {rx.appointment_id}</p>}
            </div>
          </div>

          {/* Cancellation Notice Banner */}
          {!isActive && (
            <div className="p-4 rounded-xl border border-destructive/40 bg-destructive/5 space-y-1 text-xs">
              <p className="font-bold text-destructive flex items-center gap-1.5 text-sm">
                <Ban className="h-4 w-4" /> This prescription was cancelled by the prescribing physician.
              </p>
              <p className="text-muted-foreground">
                <strong className="text-foreground">Cancellation Reason:</strong> {rx.cancellation_reason || "Not specified"}
              </p>
              {rx.cancelled_at && (
                <p className="text-muted-foreground">
                  <strong>Date:</strong> {new Date(rx.cancelled_at).toLocaleString()}
                </p>
              )}
            </div>
          )}

          {/* Medications Table */}
          <div className="space-y-2">
            <h3 className="text-sm font-bold uppercase tracking-wider text-muted-foreground">
              Prescribed Medications ({rx.medications.length})
            </h3>
            <div className="overflow-x-auto rounded-xl border border-border">
              <table className="w-full text-sm">
                <thead className="bg-muted/40 text-xs uppercase text-muted-foreground font-semibold">
                  <tr>
                    <th className="px-4 py-3 text-left">Medication</th>
                    <th className="px-4 py-3 text-left">Dosage</th>
                    <th className="px-4 py-3 text-left">Route</th>
                    <th className="px-4 py-3 text-left">Frequency</th>
                    <th className="px-4 py-3 text-left">Duration</th>
                    <th className="px-4 py-3 text-left">Instructions / Timing</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {rx.medications.map((m, idx) => (
                    <tr key={idx} className="hover:bg-muted/10 transition-colors">
                      <td className="px-4 py-3 font-semibold text-foreground">
                        {m.name}
                        {m.generic_name && (
                          <span className="block text-xs font-normal text-muted-foreground">
                            Generic: {m.generic_name}
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 font-medium text-foreground">{m.dosage}</td>
                      <td className="px-4 py-3 text-muted-foreground">{m.route || "Oral"}</td>
                      <td className="px-4 py-3 text-foreground">{m.frequency}</td>
                      <td className="px-4 py-3 text-foreground font-medium">{m.duration}</td>
                      <td className="px-4 py-3 text-xs text-muted-foreground">
                        {m.timing && <span className="font-medium text-foreground block">{m.timing}</span>}
                        {m.instructions || "As directed"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* General Patient Instructions */}
          {rx.instructions && (
            <div className="p-4 rounded-xl border border-border/70 bg-muted/10 space-y-1">
              <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Patient Instructions</p>
              <p className="text-sm text-foreground whitespace-pre-line leading-relaxed">{rx.instructions}</p>
            </div>
          )}

          {/* Confidential Doctor Notes (Only visible to doctor/admin) */}
          {rx.notes && isDoctor && (
            <div className="p-4 rounded-xl border border-primary/20 bg-primary/5 space-y-1">
              <p className="text-xs font-bold uppercase tracking-wider text-primary flex items-center gap-1">
                <ShieldCheck className="h-3.5 w-3.5" /> Doctor Confidential Notes (Private)
              </p>
              <p className="text-sm text-foreground whitespace-pre-line leading-relaxed">{rx.notes}</p>
            </div>
          )}

          {/* Footer Clinical Disclaimer */}
          <div className="pt-6 border-t border-border/60 text-[11px] text-muted-foreground flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
            <p>Digitally signed and generated via CliniXAI Certified Healthcare Platform.</p>
            <p>Consult your physician if adverse symptoms or allergic reactions occur.</p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

