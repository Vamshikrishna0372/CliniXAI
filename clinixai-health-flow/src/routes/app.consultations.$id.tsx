import { useEffect, useState, useMemo } from "react";
import { createFileRoute, Link, useParams, useNavigate } from "@tanstack/react-router";
import {
  Activity, AlertTriangle, AlertCircle, Brain, ClipboardList, FileText, CheckCircle2,
  Plus, X, ArrowLeft, RefreshCw, Save, Lock, Stethoscope, Clock, ShieldCheck,
  HeartPulse, Sparkles, Pill, Trash2, XCircle, Ban, User
} from "lucide-react";
import { PageHeader } from "@/components/app-shell/page-header";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription,
  AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { AppointmentBadge } from "@/components/domain/status-badge";
import { toast } from "sonner";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";

export const Route = createFileRoute("/app/consultations/$id")({
  head: () => ({ meta: [{ title: "Consultation Workspace — CliniXAI" }, { name: "robots", content: "noindex" }] }),
  component: ConsultationWorkspace,
});

interface Symptom {
  name: string;
  duration?: string;
  severity: "mild" | "moderate" | "severe";
  notes?: string;
}

interface Diagnosis {
  name: string;
  type: "primary" | "secondary";
  code?: string;
  notes?: string;
}

function ConsultationWorkspace() {
  const { id } = useParams({ from: "/app/consultations/$id" });
  const navigate = useNavigate();
  const { user } = useAuth();

  const [consultation, setConsultation] = useState<any>(null);
  const [patientContext, setPatientContext] = useState<any>(null);
  const [patientRecords, setPatientRecords] = useState<any[]>([]);
  const [patientAIAnalyses, setPatientAIAnalyses] = useState<any[]>([]);

  const [loading, setLoading] = useState(true);
  const [savingState, setSavingState] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [completing, setCompleting] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [versionConflict, setVersionConflict] = useState(false);

  // Form Fields
  const [complaint, setComplaint] = useState("");
  const [complaintDur, setComplaintDur] = useState("");
  const [complaintDesc, setComplaintDesc] = useState("");
  const [symptoms, setSymptoms] = useState<Symptom[]>([]);
  const [vitals, setVitals] = useState<Record<string, any>>({
    bp_systolic: "",
    bp_diastolic: "",
    heart_rate_bpm: "",
    temperature_c: "",
    spo2_percent: "",
    respiratory_rate: "",
    weight_kg: "",
    height_cm: "",
  });
  const [clinicalNotes, setClinicalNotes] = useState("");
  const [assessmentSummary, setAssessmentSummary] = useState("");
  const [riskLevel, setRiskLevel] = useState<"low" | "moderate" | "high" | "critical">("low");
  const [diagnoses, setDiagnoses] = useState<Diagnosis[]>([]);
  const [carePlan, setCarePlan] = useState("");
  const [followUpRequired, setFollowUpRequired] = useState(false);
  const [followUpDate, setFollowUpDate] = useState("");
  const [doctorInstructions, setDoctorInstructions] = useState<string[]>([]);

  // Prescription State
  const [prescription, setPrescription] = useState<any>(null);
  const [rxMeds, setRxMeds] = useState<Array<{
    name: string;
    dosage: string;
    frequency: string;
    duration: string;
    route: string;
    timing: string;
    instructions: string;
  }>>([
    { name: "", dosage: "", frequency: "Once daily", duration: "5 days", route: "Oral", timing: "After food", instructions: "" }
  ]);
  const [rxInstructions, setRxInstructions] = useState("");
  const [rxNotes, setRxNotes] = useState("");
  const [rxIssuing, setRxIssuing] = useState(false);
  const [rxComposerOpen, setRxComposerOpen] = useState(false);
  const [cancelRxOpen, setCancelRxOpen] = useState(false);
  const [cancelRxReason, setCancelRxReason] = useState("");
  const [cancellingRx, setCancellingRx] = useState(false);

  // Load Real Consultation & Clinical Context
  const loadData = async () => {
    setLoading(true);
    try {
      let consultData: any = null;
      if (user?.role === "patient" || id.startsWith("CNS-")) {
        const res = await apiClient.consultations.getDetail(id);
        consultData = res?.data || res;
      } else {
        try {
          const res = await apiClient.consultations.start(id);
          consultData = res?.data || res;
        } catch (startErr: any) {
          const res = await apiClient.consultations.getDetail(id);
          consultData = res?.data || res;
        }
      }

      setConsultation(consultData);

      // Populate Form Fields
      if (consultData) {
        setComplaint(consultData.chief_complaint?.complaint || "");
        setComplaintDur(consultData.chief_complaint?.duration || "");
        setComplaintDesc(consultData.chief_complaint?.description || "");
        setSymptoms(consultData.symptoms || []);
        if (consultData.vitals) {
          setVitals({
            bp_systolic: consultData.vitals.bp_systolic ?? "",
            bp_diastolic: consultData.vitals.bp_diastolic ?? "",
            heart_rate_bpm: consultData.vitals.heart_rate_bpm ?? "",
            temperature_c: consultData.vitals.temperature_c ?? "",
            spo2_percent: consultData.vitals.spo2_percent ?? "",
            respiratory_rate: consultData.vitals.respiratory_rate ?? "",
            weight_kg: consultData.vitals.weight_kg ?? "",
            height_cm: consultData.vitals.height_cm ?? "",
          });
        }
        setClinicalNotes(consultData.clinical_notes || "");
        setAssessmentSummary(consultData.clinical_assessment?.summary || "");
        setRiskLevel(consultData.clinical_assessment?.risk_level || "low");
        setDiagnoses(consultData.diagnoses || []);
        setCarePlan(consultData.care_plan || "");
        setFollowUpRequired(!!consultData.follow_up_required);
        setFollowUpDate(consultData.follow_up_date || "");
        setDoctorInstructions(consultData.doctor_instructions || []);

        const patId = consultData.patient_id;
        if (patId) {
          // Fetch context, records, and AI in parallel
          Promise.allSettled([
            apiClient.consultations.getPatientContext(patId).then((r) => setPatientContext(r?.data || r)),
            apiClient.medicalRecords.list({ patient_id: patId }).then((r: any) => {
              const recs = Array.isArray(r?.items) ? r.items : Array.isArray(r?.data) ? r.data : Array.isArray(r) ? r : [];
              setPatientRecords(recs);
            }),
            apiClient.ai.listAnalyses({ patient_id: patId }).then((r: any) => {
              const ais = Array.isArray(r?.items) ? r.items : Array.isArray(r?.data) ? r.data : Array.isArray(r) ? r : [];
              setPatientAIAnalyses(ais);
            }),
            apiClient.prescriptions.getByConsultation(id).then((r: any) => {
              const p = r?.data ?? r;
              setPrescription(p && p.prescription_id ? p : null);
            }).catch(() => {
              setPrescription(null);
            }),
          ]);
        }
      }
    } catch (err: any) {
      toast.error(err?.message || "Failed to load consultation encounter.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [id, user?.role]);

  const isCompleted = consultation?.status === "completed";
  const isDoctor = user?.role === "doctor" || user?.role === "admin";
  const isPatient = user?.role === "patient";

  // Calculate BMI dynamically
  const computedBmi = useMemo(() => {
    const w = parseFloat(vitals.weight_kg);
    const h = parseFloat(vitals.height_cm);
    if (w > 0 && h > 0) {
      return (w / ((h / 100) * (h / 100))).toFixed(1);
    }
    return null;
  }, [vitals.weight_kg, vitals.height_cm]);

  // Save Notes & Clinical Documentation
  const saveAllNotes = async () => {
    if (!consultation?.consultation_id || isCompleted) return;
    setSavingState("saving");
    setSaveMessage("Saving clinical documentation to database…");

    try {
      const cId = consultation.consultation_id;

      // 1. Save Chief Complaint
      if (complaint.trim()) {
        await apiClient.consultations.updateChiefComplaint(cId, {
          chief_complaint: {
            complaint: complaint.trim(),
            duration: complaintDur.trim() || undefined,
            description: complaintDesc.trim() || undefined,
          },
        });
      }

      // 2. Save Symptoms
      if (symptoms.length > 0) {
        await apiClient.consultations.updateSymptoms(cId, {
          symptoms: symptoms.filter((s) => s.name.trim()),
        });
      }

      // 3. Save Vitals
      const cleanVitals: Record<string, any> = {};
      if (vitals.bp_systolic) cleanVitals.bp_systolic = parseInt(vitals.bp_systolic, 10);
      if (vitals.bp_diastolic) cleanVitals.bp_diastolic = parseInt(vitals.bp_diastolic, 10);
      if (vitals.heart_rate_bpm) cleanVitals.heart_rate_bpm = parseInt(vitals.heart_rate_bpm, 10);
      if (vitals.temperature_c) cleanVitals.temperature_c = parseFloat(vitals.temperature_c);
      if (vitals.spo2_percent) cleanVitals.spo2_percent = parseFloat(vitals.spo2_percent);
      if (vitals.respiratory_rate) cleanVitals.respiratory_rate = parseInt(vitals.respiratory_rate, 10);
      if (vitals.weight_kg) cleanVitals.weight_kg = parseFloat(vitals.weight_kg);
      if (vitals.height_cm) cleanVitals.height_cm = parseFloat(vitals.height_cm);

      if (Object.keys(cleanVitals).length > 0) {
        await apiClient.consultations.updateVitals(cId, { vitals: cleanVitals });
      }

      // 4. Save Clinical Notes with expected_version concurrency check
      if (clinicalNotes.trim()) {
        await apiClient.consultations.updateClinicalNotes(cId, {
          notes: clinicalNotes.trim(),
          expected_version: consultation.version,
        });
      }

      // 5. Save Assessment
      if (assessmentSummary.trim()) {
        await apiClient.consultations.updateAssessment(cId, {
          assessment: {
            summary: assessmentSummary.trim(),
            risk_level: riskLevel,
          },
        });
      }

      // 6. Save Diagnoses
      if (diagnoses.length > 0) {
        await apiClient.consultations.updateDiagnoses(cId, {
          diagnoses: diagnoses.filter((d) => d.name.trim()),
        });
      }

      // 7. Save Care Plan
      if (carePlan.trim()) {
        await apiClient.consultations.updateCarePlan(cId, {
          care_plan: carePlan.trim(),
          follow_up_required: followUpRequired,
          follow_up_date: followUpDate || undefined,
        });
      }

      // Re-fetch latest authoritative document
      const refreshed = await apiClient.consultations.getDetail(cId);
      const updatedDoc = refreshed?.data || refreshed;
      setConsultation(updatedDoc);
      setVersionConflict(false);

      setSavingState("saved");
      const timeStr = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
      setSaveMessage(`Saved to MongoDB at ${timeStr}`);
      toast.success("Clinical notes persisted successfully.");
    } catch (err: any) {
      if (err?.status === 409) {
        setVersionConflict(true);
        setSavingState("error");
        setSaveMessage("Version conflict: another session updated this consultation. Unsaved edits preserved.");
        toast.error("Stale version conflict detected. Please review changes before overwriting.");
      } else {
        setSavingState("error");
        setSaveMessage(err?.message || "Failed to save clinical notes.");
        toast.error(err?.message || "Failed to save clinical notes.");
      }
    }
  };

  // Link AI Analysis
  const handleLinkAI = async (analysisId: string) => {
    if (!consultation?.consultation_id || isCompleted) return;
    try {
      const res = await apiClient.consultations.linkAIAnalysis(consultation.consultation_id, analysisId);
      const updated = res?.data || res;
      setConsultation(updated);
      toast.success(`AI Analysis ${analysisId} linked to this encounter.`);
    } catch (err: any) {
      toast.error(err?.message || "Failed to link AI analysis.");
    }
  };

  // Link Medical Record
  const handleLinkRecord = async (recordId: string) => {
    if (!consultation?.consultation_id || isCompleted) return;
    try {
      const res = await apiClient.consultations.linkMedicalRecord(consultation.consultation_id, recordId);
      const updated = res?.data || res;
      setConsultation(updated);
      toast.success(`Medical Record ${recordId} linked to this encounter.`);
    } catch (err: any) {
      toast.error(err?.message || "Failed to link medical record.");
    }
  };

  // Complete Consultation
  const handleComplete = async () => {
    if (!consultation?.consultation_id) return;

    if (!assessmentSummary.trim()) {
      toast.error("Doctor Clinical Assessment summary is required before completion.");
      setConfirmOpen(false);
      return;
    }
    if (diagnoses.length === 0 || !diagnoses.some((d) => d.name.trim())) {
      toast.error("At least one primary diagnosis is required before completing.");
      setConfirmOpen(false);
      return;
    }

    setCompleting(true);
    try {
      // Ensure all pending changes are saved first
      await saveAllNotes();

      const res = await apiClient.consultations.complete(consultation.consultation_id);
      const completedDoc = res?.data || res;
      setConsultation(completedDoc);
      setConfirmOpen(false);
      toast.success("Consultation successfully completed and clinically finalized.");
    } catch (err: any) {
      toast.error(err?.message || "Could not complete consultation.");
    } finally {
      setCompleting(false);
    }
  };

  // Prescription Handlers
  const handleAddRxMed = () => {
    setRxMeds([...rxMeds, { name: "", dosage: "", frequency: "Once daily", duration: "5 days", route: "Oral", timing: "After food", instructions: "" }]);
  };

  const handleRemoveRxMed = (idx: number) => {
    if (rxMeds.length <= 1) return;
    setRxMeds(rxMeds.filter((_, i) => i !== idx));
  };

  const handleUpdateRxMed = (idx: number, field: string, value: string) => {
    const updated = [...rxMeds];
    (updated[idx] as any)[field] = value;
    setRxMeds(updated);
  };

  const handleIssuePrescription = async () => {
    if (!consultation?.consultation_id) return;
    const validMeds = rxMeds.filter((m) => m.name.trim());
    if (validMeds.length === 0) {
      toast.error("Please add at least one medication with a valid medicine name.");
      return;
    }
    for (const m of validMeds) {
      if (!m.dosage.trim()) {
        toast.error(`Please enter dosage for ${m.name}`);
        return;
      }
      if (!m.duration.trim()) {
        toast.error(`Please enter duration for ${m.name}`);
        return;
      }
    }
    setRxIssuing(true);
    try {
      const payload = {
        consultation_id: consultation.consultation_id,
        medications: validMeds,
        instructions: rxInstructions.trim() || undefined,
        notes: rxNotes.trim() || undefined,
      };
      const res = await apiClient.prescriptions.create(payload, consultation.consultation_id);
      const data = res?.data || res;
      setPrescription(data);
      setRxComposerOpen(false);
      toast.success(`Prescription ${data.prescription_id} issued successfully.`);
    } catch (err: any) {
      toast.error(err?.message || "Failed to issue prescription.");
    } finally {
      setRxIssuing(false);
    }
  };

  const handleCancelPrescription = async () => {
    if (!prescription?.prescription_id) return;
    if (!cancelRxReason.trim()) {
      toast.error("Please provide a clinical cancellation reason.");
      return;
    }
    setCancellingRx(true);
    try {
      const res = await apiClient.prescriptions.cancel(prescription.prescription_id, {
        cancellation_reason: cancelRxReason.trim(),
      });
      const updated = res?.data || res;
      setPrescription(updated);
      setCancelRxOpen(false);
      toast.success("Prescription cancelled successfully.");
    } catch (err: any) {
      toast.error(err?.message || "Failed to cancel prescription.");
    } finally {
      setCancellingRx(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <Button asChild variant="ghost" size="sm">
          <Link to="/app/consultations">
            <ArrowLeft className="h-4 w-4 mr-1" /> Back to Consultations
          </Link>
        </Button>
        <Card className="border-border/60">
          <CardContent className="p-16 text-center text-muted-foreground flex flex-col items-center justify-center gap-3">
            <RefreshCw className="h-8 w-8 animate-spin text-primary" />
            <p className="text-base font-semibold text-foreground">Initializing Doctor Clinical Workspace…</p>
            <p className="text-xs text-muted-foreground">Connecting to MongoDB consultation repository and care boundaries</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!consultation) {
    return (
      <div className="space-y-4">
        <Button asChild variant="ghost" size="sm">
          <Link to="/app/consultations">
            <ArrowLeft className="h-4 w-4 mr-1" /> Back
          </Link>
        </Button>
        <Card>
          <CardContent className="p-12 text-center text-muted-foreground">
            Consultation encounter not found or unauthorized for this user.
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Button asChild variant="ghost" size="sm" className="gap-1.5">
          <Link to="/app/consultations">
            <ArrowLeft className="h-4 w-4" /> Consultations
          </Link>
        </Button>

        <div className="flex flex-wrap items-center gap-2">
          {isCompleted && (
            <Badge variant="outline" className="border-success/40 bg-success/10 text-success gap-1 px-3 py-1">
              <Lock className="h-3.5 w-3.5" /> Encounter Clinically Finalized & Locked
            </Badge>
          )}

          {!isCompleted && isDoctor && (
            <>
              <Button
                variant="outline"
                size="sm"
                onClick={saveAllNotes}
                disabled={savingState === "saving"}
                className="gap-1.5"
              >
                <Save className={`h-4 w-4 ${savingState === "saving" ? "animate-spin" : ""}`} />
                {savingState === "saving" ? "Saving…" : "Save Notes"}
              </Button>

              <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
                <AlertDialogTrigger asChild>
                  <Button size="sm" className="gap-1.5 bg-primary hover:bg-primary/90 text-primary-foreground shadow-sm">
                    <CheckCircle2 className="h-4 w-4" /> Complete Consultation
                  </Button>
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>Finalize & Complete Consultation?</AlertDialogTitle>
                    <AlertDialogDescription asChild>
                      <div className="text-sm text-muted-foreground space-y-2">
                        <p>
                          Completing this consultation will permanently finalize the clinical encounter, update the appointment
                          to Completed, and generate a linked Medical Record summary.
                        </p>
                        <p className="font-semibold text-foreground">
                          Required: Doctor Clinical Assessment and at least one Diagnosis.
                        </p>
                      </div>
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel>Keep Editing</AlertDialogCancel>
                    <AlertDialogAction onClick={handleComplete} disabled={completing} className="bg-primary">
                      {completing ? "Finalizing…" : "Confirm & Complete"}
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
            </>
          )}
        </div>
      </div>

      <PageHeader
        title={`Clinical Encounter: ${consultation.consultation_id}`}
        description={`Appointment ${consultation.appointment_id} · Patient ${consultation.patient_id} · Doctor ${consultation.doctor_id}`}
        status={{
          label: consultation.status === "completed" ? "Completed" : "In Progress",
          tone: consultation.status === "completed" ? "success" : "warning",
        }}
      />

      {versionConflict && (
        <Alert variant="destructive" className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
          <div className="flex items-start gap-2">
            <AlertCircle className="h-5 w-5 mt-0.5 shrink-0" />
            <div>
              <AlertTitle className="font-semibold">Consultation Version Conflict (Stale Version)</AlertTitle>
              <AlertDescription className="text-xs">
                Another session or attending doctor has updated this consultation in MongoDB. Your unsaved notes have been preserved in the form below. Reload to view the latest server version.
              </AlertDescription>
            </div>
          </div>
          <Button
            variant="outline"
            size="sm"
            className="shrink-0 bg-background hover:bg-muted text-foreground"
            onClick={async () => {
              await loadData();
              setVersionConflict(false);
              toast.info("Consultation encounter reloaded with latest server data.");
            }}
          >
            <RefreshCw className="mr-1.5 h-3.5 w-3.5" /> Reload Latest Version
          </Button>
        </Alert>
      )}

      {saveMessage && (
        <div
          className={`text-xs px-3 py-1.5 rounded-md flex items-center gap-1.5 ${
            savingState === "error"
              ? "bg-destructive/10 text-destructive border border-destructive/20"
              : savingState === "saved"
              ? "bg-success/10 text-success border border-success/20"
              : "bg-muted text-muted-foreground"
          }`}
        >
          <Clock className="h-3 w-3" />
          <span>{saveMessage}</span>
        </div>
      )}

      {/* Patient Profile Summary Card */}
      <Card className="border-border/60 bg-gradient-to-r from-background via-muted/20 to-background shadow-sm">
        <CardContent className="grid gap-4 p-5 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Patient Details</p>
            <p className="text-sm font-bold text-foreground mt-0.5">
              {patientContext ? `${patientContext.first_name} ${patientContext.last_name}` : consultation.patient_id}
            </p>
            <p className="text-xs text-muted-foreground">ID: {consultation.patient_id}</p>
            {consultation.patient_id && isDoctor && (
              <Button asChild size="sm" variant="outline" className="h-6 text-[11px] px-2 mt-1.5 gap-1">
                <Link to="/app/patients/$id" params={{ id: consultation.patient_id }}>
                  <User className="h-3 w-3" /> Clinical Workspace
                </Link>
              </Button>
            )}
          </div>
          <div>
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Demographics</p>
            <p className="text-sm font-medium mt-0.5">
              {patientContext?.gender ? `${patientContext.gender.toUpperCase()} · ` : ""}
              {patientContext?.date_of_birth ? `DOB: ${patientContext.date_of_birth}` : "—"}
            </p>
            <p className="text-xs text-muted-foreground">Blood: {patientContext?.blood_group || "—"}</p>
          </div>
          <div>
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Attending Doctor</p>
            <p className="text-sm font-semibold mt-0.5 text-primary">{consultation.doctor_id}</p>
            <p className="text-xs text-muted-foreground">Dept: {consultation.department_id || "General Medicine"}</p>
          </div>
          <div>
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Allergies & Alerts</p>
            <div className="flex flex-wrap gap-1 mt-1">
              {patientContext?.allergies && patientContext.allergies.length > 0 ? (
                patientContext.allergies.map((a: string) => (
                  <Badge key={a} variant="outline" className="border-destructive/40 bg-destructive/10 text-destructive text-xs">
                    <AlertTriangle className="h-3 w-3 mr-1" /> {a}
                  </Badge>
                ))
              ) : (
                <span className="text-xs text-muted-foreground">No known drug allergies reported</span>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-6 lg:grid-cols-[1fr_340px]">
        {/* Main Clinical Editor Section */}
        <div className="space-y-6 min-w-0">
          {/* Chief Complaint */}
          <Card className="border-border/60">
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <Stethoscope className="h-4 w-4 text-primary" /> Chief Complaint
              </CardTitle>
            </CardHeader>
            <CardContent className="grid gap-3 sm:grid-cols-2">
              <div className="sm:col-span-2">
                <Label htmlFor="complaint">Primary Complaint</Label>
                <Input
                  id="complaint"
                  value={complaint}
                  onChange={(e) => setComplaint(e.target.value)}
                  disabled={isCompleted || isPatient}
                  placeholder="e.g. Sharp chest tightness on exertion, intermittent shortness of breath"
                  className="mt-1"
                />
              </div>
              <div>
                <Label htmlFor="complaintDur">Duration</Label>
                <Input
                  id="complaintDur"
                  value={complaintDur}
                  onChange={(e) => setComplaintDur(e.target.value)}
                  disabled={isCompleted || isPatient}
                  placeholder="e.g. 4 days, 2 weeks"
                  className="mt-1"
                />
              </div>
              <div>
                <Label htmlFor="complaintDesc">Clinical Context / Onset</Label>
                <Input
                  id="complaintDesc"
                  value={complaintDesc}
                  onChange={(e) => setComplaintDesc(e.target.value)}
                  disabled={isCompleted || isPatient}
                  placeholder="e.g. Gradual onset during morning walking"
                  className="mt-1"
                />
              </div>
            </CardContent>
          </Card>

          {/* Symptoms List */}
          <Card className="border-border/60">
            <CardHeader className="flex flex-row items-center justify-between pb-3">
              <div>
                <CardTitle className="text-base flex items-center gap-2">
                  <Activity className="h-4 w-4 text-primary" /> Presenting Symptoms
                </CardTitle>
                <CardDescription>Structured symptoms documented during encounter</CardDescription>
              </div>
              {!isCompleted && isDoctor && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setSymptoms([...symptoms, { name: "", severity: "moderate", duration: "" }])}
                  className="gap-1"
                >
                  <Plus className="h-3.5 w-3.5" /> Add Symptom
                </Button>
              )}
            </CardHeader>
            <CardContent className="space-y-3">
              {symptoms.length === 0 ? (
                <p className="text-xs text-muted-foreground italic">No symptoms structured yet.</p>
              ) : (
                symptoms.map((s, idx) => (
                  <div key={idx} className="grid gap-2 p-2.5 rounded-lg border border-border/60 bg-muted/20 sm:grid-cols-[1fr_120px_130px_auto] items-center">
                    <Input
                      value={s.name}
                      onChange={(e) => {
                        const updated = [...symptoms];
                        updated[idx].name = e.target.value;
                        setSymptoms(updated);
                      }}
                      disabled={isCompleted || isPatient}
                      placeholder="Symptom name (e.g. Palpitations)"
                    />
                    <Input
                      value={s.duration || ""}
                      onChange={(e) => {
                        const updated = [...symptoms];
                        updated[idx].duration = e.target.value;
                        setSymptoms(updated);
                      }}
                      disabled={isCompleted || isPatient}
                      placeholder="Duration"
                    />
                    <select
                      className="h-9 rounded-md border border-input bg-background px-2 text-sm"
                      value={s.severity}
                      onChange={(e) => {
                        const updated = [...symptoms];
                        updated[idx].severity = e.target.value as any;
                        setSymptoms(updated);
                      }}
                      disabled={isCompleted || isPatient}
                    >
                      <option value="mild">Mild</option>
                      <option value="moderate">Moderate</option>
                      <option value="severe">Severe</option>
                    </select>
                    {!isCompleted && isDoctor && (
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => setSymptoms(symptoms.filter((_, i) => i !== idx))}
                        className="h-8 w-8 text-muted-foreground hover:text-destructive"
                      >
                        <X className="h-4 w-4" />
                      </Button>
                    )}
                  </div>
                ))
              )}
            </CardContent>
          </Card>

          {/* Vitals */}
          <Card className="border-border/60">
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <HeartPulse className="h-4 w-4 text-primary" /> Physiological Vitals
              </CardTitle>
            </CardHeader>
            <CardContent className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <div>
                <Label htmlFor="bp_sys">BP Systolic (mmHg)</Label>
                <Input
                  id="bp_sys"
                  type="number"
                  value={vitals.bp_systolic}
                  onChange={(e) => setVitals({ ...vitals, bp_systolic: e.target.value })}
                  disabled={isCompleted || isPatient}
                  placeholder="120"
                  className="mt-1"
                />
              </div>
              <div>
                <Label htmlFor="bp_dia">BP Diastolic (mmHg)</Label>
                <Input
                  id="bp_dia"
                  type="number"
                  value={vitals.bp_diastolic}
                  onChange={(e) => setVitals({ ...vitals, bp_diastolic: e.target.value })}
                  disabled={isCompleted || isPatient}
                  placeholder="80"
                  className="mt-1"
                />
              </div>
              <div>
                <Label htmlFor="hr">Heart Rate (bpm)</Label>
                <Input
                  id="hr"
                  type="number"
                  value={vitals.heart_rate_bpm}
                  onChange={(e) => setVitals({ ...vitals, heart_rate_bpm: e.target.value })}
                  disabled={isCompleted || isPatient}
                  placeholder="72"
                  className="mt-1"
                />
              </div>
              <div>
                <Label htmlFor="spo2">SpO₂ (%)</Label>
                <Input
                  id="spo2"
                  type="number"
                  value={vitals.spo2_percent}
                  onChange={(e) => setVitals({ ...vitals, spo2_percent: e.target.value })}
                  disabled={isCompleted || isPatient}
                  placeholder="98"
                  className="mt-1"
                />
              </div>
              <div>
                <Label htmlFor="temp">Temperature (°C)</Label>
                <Input
                  id="temp"
                  type="number"
                  step="0.1"
                  value={vitals.temperature_c}
                  onChange={(e) => setVitals({ ...vitals, temperature_c: e.target.value })}
                  disabled={isCompleted || isPatient}
                  placeholder="36.8"
                  className="mt-1"
                />
              </div>
              <div>
                <Label htmlFor="weight">Weight (kg)</Label>
                <Input
                  id="weight"
                  type="number"
                  step="0.1"
                  value={vitals.weight_kg}
                  onChange={(e) => setVitals({ ...vitals, weight_kg: e.target.value })}
                  disabled={isCompleted || isPatient}
                  placeholder="70"
                  className="mt-1"
                />
              </div>
              <div>
                <Label htmlFor="height">Height (cm)</Label>
                <Input
                  id="height"
                  type="number"
                  value={vitals.height_cm}
                  onChange={(e) => setVitals({ ...vitals, height_cm: e.target.value })}
                  disabled={isCompleted || isPatient}
                  placeholder="175"
                  className="mt-1"
                />
              </div>
              <div>
                <Label>Calculated BMI</Label>
                <div className="mt-1 h-9 px-3 rounded-md border border-input bg-muted/40 flex items-center text-sm font-semibold">
                  {computedBmi ? `${computedBmi} kg/m²` : "—"}
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Doctor Confidential Clinical Notes (Doctor Only) */}
          {!isPatient && (
            <Card className="border-border/60">
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center justify-between">
                  <span className="flex items-center gap-2">
                    <ClipboardList className="h-4 w-4 text-primary" /> Confidential Doctor Notes
                  </span>
                  <Badge variant="outline" className="text-xs border-primary/20 text-muted-foreground">
                    Physician Confidential
                  </Badge>
                </CardTitle>
                <CardDescription>
                  Detailed examination findings, observations, and clinical differential notes. Strictly hidden from patient view.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Textarea
                  rows={4}
                  value={clinicalNotes}
                  onChange={(e) => setClinicalNotes(e.target.value)}
                  disabled={isCompleted}
                  placeholder="Enter objective physical examination findings, cardiovascular auscultation, respiratory sounds, or internal physician notes…"
                  className="font-sans text-sm leading-relaxed"
                />
              </CardContent>
            </Card>
          )}

          {/* Clinical Assessment (Mandatory for Completion) */}
          <Card className="border-primary/40 bg-gradient-to-br from-primary/5 via-background to-background">
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <ShieldCheck className="h-4 w-4 text-primary" /> Doctor Clinical Assessment
                <span className="text-destructive">*</span>
              </CardTitle>
              <CardDescription>
                Authoritative synthesis of clinical encounter. Required before consultation completion.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label htmlFor="assessment">Assessment Summary</Label>
                <Textarea
                  id="assessment"
                  rows={3}
                  value={assessmentSummary}
                  onChange={(e) => setAssessmentSummary(e.target.value)}
                  disabled={isCompleted || isPatient}
                  placeholder="Document clinical synthesis, response to current interventions, diagnostic evaluation…"
                  className="mt-1 font-sans text-sm"
                  required
                />
              </div>
              <div className="sm:w-64">
                <Label htmlFor="riskLevel">Risk Assessment Level</Label>
                <select
                  id="riskLevel"
                  className="mt-1 h-9 w-full rounded-md border border-input bg-background px-3 text-sm capitalize"
                  value={riskLevel}
                  onChange={(e) => setRiskLevel(e.target.value as any)}
                  disabled={isCompleted || isPatient}
                >
                  <option value="low">Low Risk</option>
                  <option value="moderate">Moderate Risk</option>
                  <option value="high">High Risk</option>
                  <option value="critical">Critical Risk</option>
                </select>
              </div>
            </CardContent>
          </Card>

          {/* Diagnoses List (Mandatory for Completion) */}
          <Card className="border-border/60">
            <CardHeader className="flex flex-row items-center justify-between pb-3">
              <div>
                <CardTitle className="text-base flex items-center gap-2">
                  <FileText className="h-4 w-4 text-primary" /> Confirmed Diagnoses
                  <span className="text-destructive">*</span>
                </CardTitle>
                <CardDescription>Primary and secondary diagnostic classifications</CardDescription>
              </div>
              {!isCompleted && isDoctor && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setDiagnoses([...diagnoses, { name: "", type: diagnoses.length === 0 ? "primary" : "secondary" }])}
                  className="gap-1"
                >
                  <Plus className="h-3.5 w-3.5" /> Add Diagnosis
                </Button>
              )}
            </CardHeader>
            <CardContent className="space-y-3">
              {diagnoses.length === 0 ? (
                <p className="text-xs text-muted-foreground italic">No diagnoses entered yet.</p>
              ) : (
                diagnoses.map((d, idx) => (
                  <div key={idx} className="grid gap-2 p-2.5 rounded-lg border border-border/60 bg-muted/20 sm:grid-cols-[1fr_120px_140px_auto] items-center">
                    <Input
                      value={d.name}
                      onChange={(e) => {
                        const updated = [...diagnoses];
                        updated[idx].name = e.target.value;
                        setDiagnoses(updated);
                      }}
                      disabled={isCompleted || isPatient}
                      placeholder="Diagnosis (e.g. Essential Hypertension)"
                    />
                    <Input
                      value={d.code || ""}
                      onChange={(e) => {
                        const updated = [...diagnoses];
                        updated[idx].code = e.target.value;
                        setDiagnoses(updated);
                      }}
                      disabled={isCompleted || isPatient}
                      placeholder="ICD Code"
                    />
                    <select
                      className="h-9 rounded-md border border-input bg-background px-2 text-sm capitalize"
                      value={d.type}
                      onChange={(e) => {
                        const updated = [...diagnoses];
                        updated[idx].type = e.target.value as any;
                        setDiagnoses(updated);
                      }}
                      disabled={isCompleted || isPatient}
                    >
                      <option value="primary">Primary</option>
                      <option value="secondary">Secondary</option>
                    </select>
                    {!isCompleted && isDoctor && (
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => setDiagnoses(diagnoses.filter((_, i) => i !== idx))}
                        className="h-8 w-8 text-muted-foreground hover:text-destructive"
                      >
                        <X className="h-4 w-4" />
                      </Button>
                    )}
                  </div>
                ))
              )}
            </CardContent>
          </Card>

          {/* Care Plan & Follow-up Instructions */}
          <Card className="border-border/60">
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4 text-primary" /> Care Plan & Follow-Up Directions
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label htmlFor="carePlan">Treatment & Care Plan</Label>
                <Textarea
                  id="carePlan"
                  rows={3}
                  value={carePlan}
                  onChange={(e) => setCarePlan(e.target.value)}
                  disabled={isCompleted || isPatient}
                  placeholder="Dietary modifications, lifestyle advice, scheduled diagnostic testing, patient recommendations…"
                  className="mt-1 font-sans text-sm"
                />
              </div>
              <div className="grid gap-3 sm:grid-cols-2 items-center p-3 rounded-lg border border-border/60 bg-muted/10">
                <label className="flex items-center gap-2 text-sm font-medium cursor-pointer">
                  <input
                    type="checkbox"
                    checked={followUpRequired}
                    onChange={(e) => setFollowUpRequired(e.target.checked)}
                    disabled={isCompleted || isPatient}
                    className="rounded border-input text-primary h-4 w-4"
                  />
                  <span>Follow-Up Appointment Required</span>
                </label>
                {followUpRequired && (
                  <div>
                    <Label htmlFor="fuDate" className="text-xs">Recommended Date</Label>
                    <Input
                      id="fuDate"
                      type="date"
                      value={followUpDate}
                      onChange={(e) => setFollowUpDate(e.target.value)}
                      disabled={isCompleted || isPatient}
                      className="mt-1 h-9"
                    />
                  </div>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Clinical Prescription Section */}
          <Card className="border-border/60">
            <CardHeader className="flex flex-row items-center justify-between pb-3">
              <div>
                <CardTitle className="text-base flex items-center gap-2">
                  <Pill className="h-4 w-4 text-primary" /> Clinical Prescription
                </CardTitle>
                <CardDescription>Prescribed medications, dosing regimen, and clinical administration directions</CardDescription>
              </div>

              {prescription ? (
                <div className="flex items-center gap-2">
                  <Badge
                    variant="outline"
                    className={
                      prescription.status === "active" || prescription.status === "issued"
                        ? "border-success/40 bg-success/10 text-success text-[10px] uppercase font-semibold"
                        : "border-destructive/40 bg-destructive/10 text-destructive text-[10px] uppercase font-semibold"
                    }
                  >
                    {prescription.status === "active" || prescription.status === "issued" ? (
                      <span className="flex items-center gap-1">
                        <CheckCircle2 className="h-3 w-3" /> Active
                      </span>
                    ) : (
                      <span className="flex items-center gap-1">
                        <XCircle className="h-3 w-3" /> Cancelled
                      </span>
                    )}
                  </Badge>
                  <Button asChild size="sm" variant="outline" className="h-8 text-xs gap-1">
                    <Link to="/app/prescriptions/$id" params={{ id: prescription.prescription_id }}>
                      View Details
                    </Link>
                  </Button>
                </div>
              ) : (
                !isPatient && !rxComposerOpen && (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => setRxComposerOpen(true)}
                    className="gap-1.5 h-8 text-xs"
                  >
                    <Plus className="h-3.5 w-3.5" /> Author Prescription
                  </Button>
                )
              )}
            </CardHeader>

            <CardContent className="space-y-4">
              {prescription ? (
                /* Existing Prescription View */
                <div className="space-y-3">
                  <div className="flex items-center justify-between p-3 rounded-lg bg-muted/20 border border-border/60 text-xs">
                    <div>
                      <span className="font-semibold text-foreground">RX ID: {prescription.prescription_id}</span>
                      <span className="text-muted-foreground ml-2">
                        • Issued: {prescription.prescription_date || (prescription.created_at ? new Date(prescription.created_at).toLocaleDateString() : "—")}
                      </span>
                    </div>
                    {isDoctor && (prescription.status === "active" || prescription.status === "issued") && (
                      <AlertDialog open={cancelRxOpen} onOpenChange={setCancelRxOpen}>
                        <AlertDialogTrigger asChild>
                          <Button size="sm" variant="ghost" className="h-7 text-xs text-destructive hover:bg-destructive/10 gap-1">
                            <Ban className="h-3.5 w-3.5" /> Cancel Prescription
                          </Button>
                        </AlertDialogTrigger>
                        <AlertDialogContent>
                          <AlertDialogHeader>
                            <AlertDialogTitle>Cancel Prescription {prescription.prescription_id}?</AlertDialogTitle>
                            <AlertDialogDescription asChild>
                              <div className="text-sm text-muted-foreground space-y-2">
                                <p>This will cancel the active prescription for this encounter.</p>
                                <div className="pt-2">
                                  <Label htmlFor="cancelRxReason" className="text-foreground">Clinical Cancellation Reason</Label>
                                  <Textarea
                                    id="cancelRxReason"
                                    rows={3}
                                    value={cancelRxReason}
                                    onChange={(e) => setCancelRxReason(e.target.value)}
                                    placeholder="e.g. Changed therapy, adverse reaction…"
                                    className="mt-1"
                                  />
                                </div>
                              </div>
                            </AlertDialogDescription>
                          </AlertDialogHeader>
                          <AlertDialogFooter>
                            <AlertDialogCancel disabled={cancellingRx}>Close</AlertDialogCancel>
                            <AlertDialogAction
                              onClick={handleCancelPrescription}
                              disabled={cancellingRx || !cancelRxReason.trim()}
                              className="bg-destructive hover:bg-destructive/90 text-destructive-foreground"
                            >
                              {cancellingRx ? "Cancelling…" : "Confirm Cancel"}
                            </AlertDialogAction>
                          </AlertDialogFooter>
                        </AlertDialogContent>
                      </AlertDialog>
                    )}
                  </div>

                  <div className="overflow-x-auto rounded-lg border border-border/70">
                    <table className="w-full text-xs">
                      <thead className="bg-muted/40 uppercase font-semibold text-muted-foreground">
                        <tr>
                          <th className="px-3 py-2 text-left">Medication</th>
                          <th className="px-3 py-2 text-left">Dosage</th>
                          <th className="px-3 py-2 text-left">Frequency</th>
                          <th className="px-3 py-2 text-left">Duration</th>
                          <th className="px-3 py-2 text-left">Route</th>
                          <th className="px-3 py-2 text-left">Instructions</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border/60">
                        {prescription.medications?.map((m: any, idx: number) => (
                          <tr key={idx} className="hover:bg-muted/10">
                            <td className="px-3 py-2 font-medium text-foreground">{m.name}</td>
                            <td className="px-3 py-2">{m.dosage}</td>
                            <td className="px-3 py-2">{m.frequency}</td>
                            <td className="px-3 py-2">{m.duration}</td>
                            <td className="px-3 py-2 text-muted-foreground">{m.route || "Oral"}</td>
                            <td className="px-3 py-2 text-muted-foreground">{m.instructions || m.timing || "—"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  {prescription.instructions && (
                    <div className="p-3 rounded-lg bg-muted/10 border border-border/50 text-xs">
                      <p className="font-semibold text-muted-foreground uppercase text-[10px]">Patient Instructions</p>
                      <p className="mt-0.5 text-foreground">{prescription.instructions}</p>
                    </div>
                  )}

                  {prescription.notes && isDoctor && (
                    <div className="p-3 rounded-lg bg-primary/5 border border-primary/20 text-xs">
                      <p className="font-semibold text-primary uppercase text-[10px] flex items-center gap-1">
                        <ShieldCheck className="h-3 w-3" /> Doctor Private Notes
                      </p>
                      <p className="mt-0.5 text-foreground">{prescription.notes}</p>
                    </div>
                  )}
                </div>
              ) : rxComposerOpen ? (
                /* Doctor Prescription Composer */
                <div className="space-y-4 p-4 rounded-xl border border-primary/30 bg-primary/5">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-semibold text-foreground">New Prescription Order</p>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => setRxComposerOpen(false)}
                      className="h-7 text-xs text-muted-foreground"
                    >
                      Cancel
                    </Button>
                  </div>

                  {/* Medications List */}
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <Label className="text-xs uppercase tracking-wider text-muted-foreground font-semibold">
                        Medications ({rxMeds.length}) <span className="text-destructive">*</span>
                      </Label>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={handleAddRxMed}
                        className="h-7 text-xs gap-1"
                      >
                        <Plus className="h-3 w-3" /> Add Item
                      </Button>
                    </div>

                    {rxMeds.map((med, idx) => (
                      <div key={idx} className="p-3 rounded-lg border border-border/70 bg-card space-y-2.5 text-xs">
                        <div className="grid gap-2 sm:grid-cols-[1fr_130px_130px_auto] items-center">
                          <div>
                            <Input
                              placeholder="Medication Name (e.g. Amoxicillin 500mg)"
                              value={med.name}
                              onChange={(e) => handleUpdateRxMed(idx, "name", e.target.value)}
                              className="h-8 text-xs font-medium"
                            />
                          </div>
                          <div>
                            <Input
                              placeholder="Dosage (e.g. 1 capsule)"
                              value={med.dosage}
                              onChange={(e) => handleUpdateRxMed(idx, "dosage", e.target.value)}
                              className="h-8 text-xs"
                            />
                          </div>
                          <div>
                            <Input
                              placeholder="Duration (e.g. 7 days)"
                              value={med.duration}
                              onChange={(e) => handleUpdateRxMed(idx, "duration", e.target.value)}
                              className="h-8 text-xs"
                            />
                          </div>
                          <div>
                            {rxMeds.length > 1 && (
                              <Button
                                size="icon"
                                variant="ghost"
                                onClick={() => handleRemoveRxMed(idx)}
                                className="h-8 w-8 text-muted-foreground hover:text-destructive"
                              >
                                <Trash2 className="h-3.5 w-3.5" />
                              </Button>
                            )}
                          </div>
                        </div>

                        <div className="grid gap-2 sm:grid-cols-3">
                          <div>
                            <select
                              className="h-8 w-full rounded-md border border-input bg-background px-2 text-xs"
                              value={med.frequency}
                              onChange={(e) => handleUpdateRxMed(idx, "frequency", e.target.value)}
                            >
                              <option value="Once daily">Once daily</option>
                              <option value="Twice daily">Twice daily</option>
                              <option value="Thrice daily">Thrice daily</option>
                              <option value="Every 8 hours">Every 8 hours</option>
                              <option value="Every 12 hours">Every 12 hours</option>
                              <option value="As needed">As needed (PRN)</option>
                            </select>
                          </div>
                          <div>
                            <select
                              className="h-8 w-full rounded-md border border-input bg-background px-2 text-xs"
                              value={med.route}
                              onChange={(e) => handleUpdateRxMed(idx, "route", e.target.value)}
                            >
                              <option value="Oral">Oral</option>
                              <option value="Topical">Topical</option>
                              <option value="Inhalation">Inhalation</option>
                              <option value="Subcutaneous">Subcutaneous</option>
                              <option value="Intramuscular">Intramuscular</option>
                              <option value="Intravenous">Intravenous</option>
                              <option value="Other">Other</option>
                            </select>
                          </div>
                          <div>
                            <Input
                              placeholder="Timing / Food (e.g. After meals)"
                              value={med.timing}
                              onChange={(e) => handleUpdateRxMed(idx, "timing", e.target.value)}
                              className="h-8 text-xs"
                            />
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>

                  <div className="space-y-3 pt-2">
                    <div>
                      <Label htmlFor="rxInstructions" className="text-xs">Patient Instructions</Label>
                      <Textarea
                        id="rxInstructions"
                        rows={2}
                        value={rxInstructions}
                        onChange={(e) => setRxInstructions(e.target.value)}
                        placeholder="e.g. Take with a full glass of water. Complete full antibiotic course."
                        className="mt-1 text-xs"
                      />
                    </div>
                    <div>
                      <Label htmlFor="rxNotes" className="text-xs">Doctor Confidential Clinical Notes (Private)</Label>
                      <Textarea
                        id="rxNotes"
                        rows={2}
                        value={rxNotes}
                        onChange={(e) => setRxNotes(e.target.value)}
                        placeholder="Internal notes on medication rationale (not visible to patient)…"
                        className="mt-1 text-xs"
                      />
                    </div>
                  </div>

                  <div className="flex items-center justify-end gap-2 pt-2">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => setRxComposerOpen(false)}
                      disabled={rxIssuing}
                    >
                      Cancel
                    </Button>
                    <Button
                      size="sm"
                      onClick={handleIssuePrescription}
                      disabled={rxIssuing}
                      className="gap-1.5 bg-primary text-primary-foreground"
                    >
                      <CheckCircle2 className={`h-4 w-4 ${rxIssuing ? "animate-spin" : ""}`} />
                      {rxIssuing ? "Issuing Prescription…" : "Issue Prescription"}
                    </Button>
                  </div>
                </div>
              ) : (
                /* Empty state when no prescription issued yet */
                <p className="text-xs text-muted-foreground italic">
                  {isPatient
                    ? "No prescription has been issued for this consultation encounter."
                    : "No prescription has been authored for this encounter yet. Click 'Author Prescription' above to create one."}
                </p>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Sidebar Context Panel: AI Support & Medical Records */}
        <aside className="space-y-5">
          {/* AI Clinical Decision Support Integration */}
          <Card className="border-primary/30 shadow-sm">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm flex items-center justify-between">
                <span className="flex items-center gap-1.5 text-primary">
                  <Brain className="h-4 w-4" /> AI Decision Support
                </span>
                <Sparkles className="h-3.5 w-3.5 text-primary/70" />
              </CardTitle>
              <CardDescription className="text-xs">
                Deep learning clinical prediction models (ResNet50 / Grad-CAM)
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {patientAIAnalyses.length === 0 ? (
                <p className="text-xs text-muted-foreground italic">No AI analyses recorded for this patient.</p>
              ) : (
                patientAIAnalyses.map((ai) => {
                  const isLinked =
                    consultation.linked_ai_analysis_ids?.includes(ai.analysis_id) ||
                    consultation.ai_analysis_references?.includes(ai.analysis_id);

                  return (
                    <div key={ai.analysis_id} className="p-3 rounded-lg border border-border/70 bg-card space-y-2 text-xs">
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-foreground truncate">{ai.module_id || "Medical Scan"}</span>
                        {isLinked ? (
                          <Badge variant="outline" className="border-primary/40 bg-primary/10 text-primary text-[10px]">
                            Linked
                          </Badge>
                        ) : (
                          !isCompleted && isDoctor && (
                            <Button size="sm" variant="ghost" className="h-6 text-[10px] px-2" onClick={() => handleLinkAI(ai.analysis_id)}>
                              Link
                            </Button>
                          )
                        )}
                      </div>
                      <div className="text-muted-foreground">
                        <p>Class: <span className="font-medium text-foreground">{ai.prediction?.predicted_class || "Processing"}</span></p>
                        <p>Confidence: <span className="font-medium text-foreground">{ai.prediction?.confidence ? `${(ai.prediction.confidence * 100).toFixed(1)}%` : "—"}</span></p>
                      </div>
                      <div className="flex items-center gap-2 pt-1 border-t border-border/40">
                        <Button asChild size="sm" variant="link" className="p-0 h-auto text-xs text-primary">
                          <Link to="/app/ai-analysis/$id" params={{ id: ai.analysis_id }}>
                            Inspect Grad-CAM
                          </Link>
                        </Button>
                      </div>
                    </div>
                  );
                })
              )}
              <div className="p-2.5 rounded-md bg-info/10 text-info border border-info/20 text-[11px] leading-tight">
                <strong>Clinical Disclaimer:</strong> AI findings are decision-support only and must be interpreted in conjunction with patient clinical presentation.
              </div>
            </CardContent>
          </Card>

          {/* Medical Records Integration */}
          <Card className="border-border/60 shadow-sm">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm flex items-center gap-1.5">
                <FileText className="h-4 w-4 text-muted-foreground" /> Medical Records
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-xs">
              {patientRecords.length === 0 ? (
                <p className="text-muted-foreground italic">No medical records on file.</p>
              ) : (
                patientRecords.slice(0, 5).map((rec) => {
                  const isLinked =
                    consultation.linked_medical_record_ids?.includes(rec.record_id) ||
                    consultation.medical_record_references?.includes(rec.record_id);

                  return (
                    <div key={rec.record_id} className="p-2 rounded-md border border-border/50 bg-muted/20 flex items-center justify-between">
                      <div className="min-w-0 pr-2">
                        <p className="font-medium truncate text-foreground">{rec.title || rec.record_id}</p>
                        <p className="text-[10px] text-muted-foreground">{rec.record_type || "Document"} · {rec.clinical_date || ""}</p>
                      </div>
                      {isLinked ? (
                        <Badge variant="outline" className="text-[10px] border-primary/30 text-primary">
                          Linked
                        </Badge>
                      ) : (
                        !isCompleted && isDoctor && (
                          <Button size="sm" variant="ghost" className="h-6 text-[10px] px-2" onClick={() => handleLinkRecord(rec.record_id)}>
                            Link
                          </Button>
                        )
                      )}
                    </div>
                  );
                })
              )}
            </CardContent>
          </Card>
        </aside>
      </div>
    </div>
  );
}
