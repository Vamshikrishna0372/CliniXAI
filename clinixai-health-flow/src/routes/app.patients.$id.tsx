import { useEffect, useState, useMemo } from "react";
import { createFileRoute, Link, useParams, useSearch } from "@tanstack/react-router";
import {
  User, Calendar, Clock, FileText, Activity, AlertTriangle, Pill,
  ArrowLeft, Brain, Stethoscope, HeartPulse, ShieldAlert, Download,
  ExternalLink, Sparkles, RefreshCw, Eye, CheckCircle2, ChevronRight,
  FolderOpen, ImageIcon, History, ClipboardList, Check, X, ImageOff, Loader2
} from "lucide-react";
import { PageHeader } from "@/components/app-shell/page-header";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { EmptyState } from "@/components/dashboard/states";
import { AppointmentBadge } from "@/components/domain/status-badge";
import { apiClient, getApiBaseUrl } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/app/patients/$id")({
  head: () => ({
    meta: [
      { title: "Patient Clinical Workspace — CliniXAI" },
      { name: "robots", content: "noindex" },
    ],
  }),
  component: PatientClinicalWorkspacePage,
});

function isBrainMri(doc: any): boolean {
  if (!doc) return false;
  const cat = String(doc.category || "").toLowerCase();
  const title = String(doc.title || "").toLowerCase();
  const fname = String(doc.original_file_name || doc.file_name || doc.filename || "").toLowerCase();
  return (
    cat.includes("mri") ||
    title.includes("brain") ||
    title.includes("mri") ||
    fname.includes("brain") ||
    fname.includes("mri")
  );
}

function AuthenticatedDocImage({
  documentId,
  alt,
  className,
}: {
  documentId: string;
  alt: string;
  className?: string;
}) {
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(false);

    apiClient.documents
      .getFileBlob(documentId)
      .then((blob) => {
        if (!active) return;
        const url = URL.createObjectURL(blob);
        setBlobUrl(url);
        setLoading(false);
      })
      .catch(() => {
        if (!active) return;
        setLoading(false);
        setError(true);
      });

    return () => {
      active = false;
      if (blobUrl) {
        URL.revokeObjectURL(blobUrl);
      }
    };
  }, [documentId]);

  if (loading) {
    return (
      <div className="flex h-full w-full items-center justify-center bg-muted/30 animate-pulse">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error || !blobUrl) {
    return (
      <div className="flex flex-col h-full w-full items-center justify-center bg-muted/20 text-muted-foreground p-2 text-center">
        <ImageOff className="h-6 w-6 mb-1 opacity-40" />
        <span className="text-[10px]">Preview unavailable</span>
      </div>
    );
  }

  return (
    <img
      src={blobUrl}
      alt={alt}
      className={className || "h-full w-full object-cover"}
      loading="lazy"
    />
  );
}

function PatientClinicalWorkspacePage() {
  const { id } = useParams({ from: "/app/patients/$id" });
  const search: any = useSearch({ strict: false });
  const { user } = useAuth();

  const [activeTab, setActiveTab] = useState<string>(search?.tab || "records");
  const [patient, setPatient] = useState<any | null>(null);
  const [clinicalContext, setClinicalContext] = useState<any | null>(null);
  const [medicalRecords, setMedicalRecords] = useState<any[]>([]);
  const [documents, setDocuments] = useState<any[]>([]);
  const [consultations, setConsultations] = useState<any[]>([]);
  const [prescriptions, setPrescriptions] = useState<any[]>([]);
  const [appointments, setAppointments] = useState<any[]>([]);
  const [timeline, setTimeline] = useState<any[]>([]);

  const [loading, setLoading] = useState(true);
  const [errorStatus, setErrorStatus] = useState<number | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [docCategoryFilter, setDocCategoryFilter] = useState<string>("all");
  const [selectedDocument, setSelectedDocument] = useState<any | null>(null);
  const [viewingDoc, setViewingDoc] = useState<any | null>(null);
  const [downloadingDocId, setDownloadingDocId] = useState<string | null>(null);

  const loadAllPatientData = async () => {
    setLoading(true);
    setErrorStatus(null);
    setErrorMessage(null);

    try {
      // 1. Fetch Patient profile
      const patRes = await apiClient.patients.getDetail(id);
      const patData = patRes?.data || patRes;
      setPatient(patData);

      // 2. Fetch parallel clinical context
      const [
        ctxResult,
        recsResult,
        docsResult,
        cnsResult,
        rxResult,
        aptResult,
        timelineResult,
      ] = await Promise.allSettled([
        apiClient.consultations.getPatientContext(id),
        apiClient.medicalRecords.list({ patient_id: id }),
        apiClient.documents.list({ patient_id: id }),
        apiClient.consultations.list({ patient_id: id }),
        apiClient.prescriptions.list({ patient_id: id }),
        apiClient.appointments.list({ patient_id: id }),
        apiClient.patients.getTimeline(id),
      ]);

      if (ctxResult.status === "fulfilled") {
        setClinicalContext(ctxResult.value?.data || ctxResult.value);
      }
      if (recsResult.status === "fulfilled") {
        const val = recsResult.value;
        const recList = Array.isArray(val?.items) ? val.items : Array.isArray(val?.data) ? val.data : Array.isArray(val) ? val : [];
        setMedicalRecords(recList);
      }
      if (docsResult.status === "fulfilled") {
        const val = docsResult.value;
        const docList = Array.isArray(val?.items) ? val.items : Array.isArray(val?.data) ? val.data : Array.isArray(val) ? val : [];
        setDocuments(docList);
      }
      if (cnsResult.status === "fulfilled") {
        const val = cnsResult.value;
        const cnsList = Array.isArray(val?.items) ? val.items : Array.isArray(val?.data) ? val.data : Array.isArray(val) ? val : [];
        setConsultations(cnsList);
      }
      if (rxResult.status === "fulfilled") {
        const val = rxResult.value;
        const rxList = Array.isArray(val?.items) ? val.items : Array.isArray(val?.data) ? val.data : Array.isArray(val) ? val : [];
        setPrescriptions(rxList);
      }
      if (aptResult.status === "fulfilled") {
        const val = aptResult.value;
        const aptList = Array.isArray(val?.items) ? val.items : Array.isArray(val?.data) ? val.data : Array.isArray(val) ? val : [];
        setAppointments(aptList);
      }
      if (timelineResult.status === "fulfilled") {
        const val = timelineResult.value;
        const events = Array.isArray(val?.data?.timeline) ? val.data.timeline : Array.isArray(val?.timeline) ? val.timeline : Array.isArray(val) ? val : [];
        setTimeline(events);
      }
    } catch (err: any) {
      console.warn("Error loading patient clinical workspace:", err);
      const status = err?.status || (err?.message?.includes("authorized") ? 403 : 500);
      setErrorStatus(status);
      setErrorMessage(err?.message || "Could not load clinical workspace.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    setSelectedDocument(null);
    setViewingDoc(null);
    setPatient(null);
    setErrorStatus(null);
    setErrorMessage(null);
    loadAllPatientData();
  }, [id]);

  useEffect(() => {
    if (search.tab) {
      setActiveTab(search.tab);
    }
  }, [search.tab]);

  const handleRefresh = () => {
    setRefreshing(true);
    loadAllPatientData();
  };

  const handleSelectDocument = (doc: any) => {
    const docId = doc.document_id || doc.id;
    if (selectedDocument?.document_id === docId) {
      setSelectedDocument(null);
      toast.info(`Deselected ${doc.title || docId}`);
    } else {
      const selected = {
        document_id: docId,
        patient_id: doc.patient_id || id,
        title: doc.title || doc.original_file_name || "Medical Scan",
        category: doc.category || "MRI",
        mime_type: doc.mime_type || "image/jpeg",
        original_file_name: doc.original_file_name || doc.file_name || doc.filename || "scan.jpg",
        file_size_bytes: doc.file_size_bytes || doc.file_size || doc.size_bytes,
        storage_path: doc.storage_path,
        appointment_id: doc.appointment_id,
        medical_record_id: doc.medical_record_id,
        created_at: doc.created_at,
        is_mri: isBrainMri(doc),
      };
      setSelectedDocument(selected);
      toast.success(`Selected ${selected.title} (${selected.category})`);
    }
  };

  const downloadAuthenticatedDoc = async (doc: any) => {
    const docId = doc?.document_id || doc?.id;
    if (!docId) return;
    setDownloadingDocId(docId);
    try {
      const blob = await apiClient.documents.getFileBlob(docId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = doc.original_file_name || doc.file_name || doc.filename || "medical_document.bin";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      toast.success("Document downloaded securely.");
    } catch (err: any) {
      toast.error("Download failed: " + (err?.message || "Unauthorized access."));
    } finally {
      setDownloadingDocId(null);
    }
  };

  // Find latest active encounter / appointment
  const currentEncounter = useMemo(() => {
    if (!appointments || appointments.length === 0) return null;
    const active = appointments.find((a: any) =>
      ["in_consultation", "in-consultation", "checked_in", "checked-in", "in_queue", "in-queue", "confirmed", "scheduled"].includes(
        (a.status || "").toLowerCase().replace(/_/g, "-")
      )
    );
    return active || appointments[0];
  }, [appointments]);

  // Filtered documents
  const filteredDocuments = useMemo(() => {
    if (docCategoryFilter === "all") return documents;
    const target = docCategoryFilter.toLowerCase().replace(/[\s-_]/g, "");
    return documents.filter((d: any) => {
      const cat = (d.category || "").toLowerCase().replace(/[\s-_]/g, "");
      const title = (d.title || "").toLowerCase();
      const fname = (d.original_file_name || d.file_name || d.filename || "").toLowerCase();
      if (target === "mri") {
        return isBrainMri(d);
      }
      if (target === "xray") {
        return cat === "xray" || cat === "chestxray" || cat.includes("xray") || cat.includes("cxr") || title.includes("xray") || title.includes("x-ray") || fname.includes("xray") || fname.includes("x-ray");
      }
      return cat === target || (d.category || "").toLowerCase().includes(target);
    });
  }, [documents, docCategoryFilter]);

  if (errorStatus === 403) {
    return (
      <EmptyState
        title="Clinical Access Restricted"
        description="You do not have an established care relationship with this patient or are not authorized to view this clinical workspace."
        action={
          <Button asChild>
            <Link to="/app/appointments">Back to My Appointments</Link>
          </Button>
        }
      />
    );
  }

  if (errorStatus === 404) {
    return (
      <EmptyState
        title="Patient Record Not Found"
        description={`No registered patient profile found matching identifier '${id}'.`}
        action={
          <Button asChild>
            <Link to="/app/appointments">Back to Appointments</Link>
          </Button>
        }
      />
    );
  }

  if (loading && !patient) {
    return (
      <Card className="p-16 text-center">
        <RefreshCw className="mx-auto mb-3 h-6 w-6 animate-spin text-primary" />
        <p className="text-sm font-medium text-foreground">Loading Patient Clinical Workspace…</p>
        <p className="text-xs text-muted-foreground mt-1">Aggregating records, imaging, history, and active encounters</p>
      </Card>
    );
  }

  const patientName = patient?.full_name || `${patient?.first_name || ""} ${patient?.last_name || ""}`.trim() || "Patient";
  const allergies = patient?.allergies || clinicalContext?.allergies || [];
  const chronicConditions = patient?.chronic_conditions || patient?.conditions || [];

  return (
    <div className="space-y-6">
      {/* Top Breadcrumb & Action Header */}
      <div>
        <Button asChild variant="ghost" size="sm" className="mb-2">
          <Link to="/app/appointments">
            <ArrowLeft className="mr-1 h-4 w-4" /> Back to Appointments
          </Link>
        </Button>
        <PageHeader
          title={`Clinical Workspace — ${patientName}`}
          description={`Patient Identifier: ${patient?.patient_id || id} • Confidential Medical Encounter`}
          actions={
            <div className="flex items-center gap-2">
              <Button size="sm" variant="outline" onClick={handleRefresh} disabled={refreshing}>
                <RefreshCw className={`mr-1.5 h-3.5 w-3.5 ${refreshing ? "animate-spin" : ""}`} />
                {refreshing ? "Refreshing…" : "Refresh Record"}
              </Button>
              {currentEncounter && (
                <Button asChild size="sm" variant="default">
                  <Link to="/app/consultations/$id" params={{ id: currentEncounter.appointment_id || currentEncounter.id }}>
                    <Stethoscope className="mr-1.5 h-4 w-4" />
                    {currentEncounter.status === "in_consultation" ? "Open Consultation" : "Launch Consultation"}
                  </Link>
                </Button>
              )}
            </div>
          }
        />
      </div>

      {/* Patient Clinical Profile Header Card */}
      <Card className="border-primary/20 bg-card/60 backdrop-blur-sm">
        <CardContent className="p-5 sm:p-6 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-4 border-b border-border/60 pb-4">
            <div className="flex items-center gap-3">
              <div className="grid h-12 w-12 place-items-center rounded-2xl bg-primary/10 text-primary font-bold text-lg">
                {(patient?.first_name || "P").charAt(0).toUpperCase()}
                {(patient?.last_name || "").charAt(0).toUpperCase()}
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-xl font-bold tracking-tight text-foreground">{patientName}</h2>
                  <Badge variant="outline" className="font-mono text-xs">
                    {patient?.patient_id || id}
                  </Badge>
                </div>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {patient?.gender ? `${patient.gender.toUpperCase()} • ` : ""}
                  {patient?.date_of_birth ? `DOB: ${patient.date_of_birth} • ` : ""}
                  Blood Group: <span className="font-semibold text-foreground">{patient?.blood_group || "Unknown"}</span>
                </p>
              </div>
            </div>

            {/* Critical Allergies Badge Banner */}
            {allergies.length > 0 ? (
              <div className="flex items-center gap-2 rounded-xl border border-destructive/30 bg-destructive/10 px-3.5 py-2 text-xs font-semibold text-destructive">
                <ShieldAlert className="h-4 w-4 shrink-0" />
                <span>Allergies: {allergies.join(", ")}</span>
              </div>
            ) : (
              <div className="flex items-center gap-1.5 rounded-xl border border-success/30 bg-success/10 px-3 py-1.5 text-xs text-success font-medium">
                <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />
                <span>No Known Drug Allergies</span>
              </div>
            )}
          </div>

          {/* Quick Metrics Grid */}
          <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-4 text-xs">
            <div className="rounded-lg bg-muted/40 p-3">
              <p className="text-muted-foreground uppercase tracking-wider text-[10px] font-semibold">Contact & Phone</p>
              <p className="font-medium text-foreground mt-0.5">{patient?.phone_number || patient?.phone || "—"}</p>
            </div>
            <div className="rounded-lg bg-muted/40 p-3">
              <p className="text-muted-foreground uppercase tracking-wider text-[10px] font-semibold">Emergency Contact</p>
              <p className="font-medium text-foreground mt-0.5">
                {patient?.emergency_contact?.name ? `${patient.emergency_contact.name} (${patient.emergency_contact.relationship || "Contact"})` : "—"}
              </p>
            </div>
            <div className="rounded-lg bg-muted/40 p-3">
              <p className="text-muted-foreground uppercase tracking-wider text-[10px] font-semibold">Chronic Conditions</p>
              <p className="font-medium text-foreground mt-0.5">
                {chronicConditions.length > 0 ? chronicConditions.join(", ") : "None documented"}
              </p>
            </div>
            <div className="rounded-lg bg-muted/40 p-3">
              <p className="text-muted-foreground uppercase tracking-wider text-[10px] font-semibold">Care Encounters</p>
              <p className="font-medium text-foreground mt-0.5">
                {appointments.length} Appointments • {consultations.length} Consultations
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Current Active Encounter Card */}
      {currentEncounter && (
        <Card className="border-primary/40 bg-primary/5">
          <CardHeader className="py-3 px-5 border-b border-primary/20">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Activity className="h-4 w-4 text-primary" />
                <CardTitle className="text-sm font-semibold text-primary">Active Clinical Encounter</CardTitle>
                <Badge variant="outline" className="text-xs font-mono">{currentEncounter.appointment_id || currentEncounter.id}</Badge>
              </div>
              <AppointmentBadge status={(currentEncounter.status || "scheduled").toLowerCase().replace(/_/g, "-")} />
            </div>
          </CardHeader>
          <CardContent className="p-4 sm:p-5 flex flex-wrap items-center justify-between gap-4">
            <div className="grid gap-4 sm:grid-cols-3 text-xs flex-1">
              <div>
                <p className="text-muted-foreground font-medium">Scheduled Time</p>
                <p className="font-semibold text-foreground text-sm mt-0.5">
                  {currentEncounter.appointment_date || "—"} at {currentEncounter.start_time || currentEncounter.time || "—"}
                </p>
              </div>
              <div>
                <p className="text-muted-foreground font-medium">Chief Reason for Visit</p>
                <p className="font-semibold text-foreground text-sm mt-0.5">
                  {currentEncounter.reason || "General Consultation"}
                </p>
              </div>
              <div>
                <p className="text-muted-foreground font-medium">Assigned Department</p>
                <p className="font-semibold text-foreground text-sm mt-0.5">
                  {currentEncounter.department_id || "General Medicine"}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Button asChild size="sm" variant="default">
                <Link to="/app/consultations/$id" params={{ id: currentEncounter.appointment_id || currentEncounter.id }}>
                  <Stethoscope className="mr-1.5 h-3.5 w-3.5" />
                  Proceed to Consultation
                </Link>
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Main Clinical Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
        <TabsList className="grid w-full grid-cols-2 md:grid-cols-5 h-auto p-1 bg-muted/60">
          <TabsTrigger value="records" className="text-xs py-2">
            <FileText className="mr-1.5 h-3.5 w-3.5" />
            Medical Records ({medicalRecords.length})
          </TabsTrigger>
          <TabsTrigger value="documents" className="text-xs py-2">
            <ImageIcon className="mr-1.5 h-3.5 w-3.5" />
            Imaging & Docs ({documents.length})
          </TabsTrigger>
          <TabsTrigger value="consultations" className="text-xs py-2">
            <ClipboardList className="mr-1.5 h-3.5 w-3.5" />
            Consultations ({consultations.length})
          </TabsTrigger>
          <TabsTrigger value="prescriptions" className="text-xs py-2">
            <Pill className="mr-1.5 h-3.5 w-3.5" />
            Prescriptions ({prescriptions.length})
          </TabsTrigger>
          <TabsTrigger value="timeline" className="text-xs py-2">
            <History className="mr-1.5 h-3.5 w-3.5" />
            Timeline ({timeline.length})
          </TabsTrigger>
        </TabsList>

        {/* 1. MEDICAL RECORDS TAB */}
        <TabsContent value="records" className="space-y-4">
          <Card>
            <CardHeader className="py-4 px-6 flex flex-row items-center justify-between border-b border-border/50">
              <div>
                <CardTitle className="text-base font-semibold">Authoritative Medical Records</CardTitle>
                <CardDescription className="text-xs">Clinical summaries, diagnoses, and care plans for {patientName}</CardDescription>
              </div>
              <Badge variant="secondary" className="text-xs">{medicalRecords.length} Records</Badge>
            </CardHeader>
            <CardContent className="p-4 sm:p-6">
              {medicalRecords.length === 0 ? (
                <EmptyState
                  title="No Medical Records Found"
                  description={`No medical records have been documented for ${patientName} yet.`}
                />
              ) : (
                <div className="space-y-3">
                  {medicalRecords.map((r: any) => (
                    <div key={r.record_id || r.id} className="rounded-xl border border-border bg-card p-4 card-hover space-y-2">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <FileText className="h-4 w-4 text-primary shrink-0" />
                          <span className="font-semibold text-sm text-foreground">{r.title || "Clinical Record"}</span>
                          <Badge variant="outline" className="text-[10px] font-mono">{r.record_id}</Badge>
                          <Badge variant="secondary" className="text-[10px] uppercase">{r.record_type || "clinical"}</Badge>
                        </div>
                        <span className="text-xs text-muted-foreground">{r.clinical_date || r.created_at?.slice(0, 10)}</span>
                      </div>

                      {r.diagnosis && (
                        <div className="text-xs">
                          <span className="font-semibold text-foreground">Diagnosis: </span>
                          <span className="text-muted-foreground">{r.diagnosis}</span>
                        </div>
                      )}
                      {r.clinical_notes && (
                        <div className="text-xs bg-muted/30 p-2.5 rounded-lg text-foreground/90">
                          <span className="font-medium text-muted-foreground block text-[11px] mb-0.5">Clinical Notes:</span>
                          {r.clinical_notes}
                        </div>
                      )}
                      {r.treatment_plan && (
                        <div className="text-xs text-muted-foreground">
                          <span className="font-medium text-foreground">Treatment Plan: </span>
                          {r.treatment_plan}
                        </div>
                      )}

                      <div className="flex items-center justify-between pt-2 border-t border-border/40 text-[11px] text-muted-foreground">
                        <span>Patient ID: <span className="font-mono text-foreground">{r.patient_id}</span></span>
                        {r.doctor_id && <span>Doctor: <span className="font-mono text-foreground">{r.doctor_id}</span></span>}
                        {r.file && (
                          <Button asChild size="sm" variant="ghost" className="h-7 text-xs">
                            <a href={`/api/v1/medical-records/${r.record_id}/file`} target="_blank" rel="noreferrer">
                              <Download className="mr-1 h-3 w-3" /> Download Attachment
                            </a>
                          </Button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* 2. DOCUMENTS & IMAGING TAB */}
        <TabsContent value="documents" className="space-y-4">
          {/* Authoritative Selected Document Banner */}
          {selectedDocument && (
            <Card data-testid="selected-doc-banner" className="border-primary/50 bg-primary/5 shadow-sm ring-1 ring-primary/25">
              <CardContent className="p-4 flex flex-wrap items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                  <div className="grid h-10 w-10 place-items-center rounded-xl bg-primary text-primary-foreground shrink-0 shadow-sm">
                    <CheckCircle2 className="h-5 w-5" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-xs font-semibold uppercase tracking-wider text-primary">
                        Authoritative Selected Document
                      </span>
                      <Badge variant="outline" className="text-[10px] font-mono border-primary/30">
                        {selectedDocument.document_id}
                      </Badge>
                      <Badge className="bg-primary/20 text-primary border-primary/30 text-[10px]">
                        {selectedDocument.category}
                      </Badge>
                      {selectedDocument.is_mri && (
                        <Badge className="bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border-emerald-500/30 text-[10px] flex items-center gap-1 font-semibold">
                          <Brain className="h-3 w-3" /> Brain MRI Confirmed
                        </Badge>
                      )}
                    </div>
                    <p className="font-bold text-sm text-foreground mt-0.5">
                      {selectedDocument.title}
                    </p>
                    <p className="text-xs text-muted-foreground mt-0.5 font-mono">
                      Patient: {patientName} ({selectedDocument.patient_id}) • File: {selectedDocument.original_file_name}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  {(selectedDocument.is_mri || selectedDocument.mime_type?.startsWith("image/") || ["mri", "xray", "ct", "dermoscopy", "fundus"].includes(String(selectedDocument.category || "").toLowerCase())) && (
                    <Button
                      asChild
                      size="sm"
                      variant="default"
                      className="text-xs h-8 bg-primary text-primary-foreground font-semibold shadow-sm hover:bg-primary/90"
                      data-testid="analyze-with-ai-btn"
                    >
                      <Link
                        to="/app/ai-analysis"
                        search={{
                          patient_id: selectedDocument.patient_id,
                          document_id: selectedDocument.document_id,
                          appointment_id: selectedDocument.appointment_id || undefined,
                          medical_record_id: selectedDocument.medical_record_id || undefined,
                          modality: isBrainMri(selectedDocument) ? "BRAIN_MRI" : undefined,
                        }}
                      >
                        <Sparkles className="mr-1.5 h-3.5 w-3.5" /> Analyze with AI
                      </Link>
                    </Button>
                  )}
                  <Button
                    size="sm"
                    variant="outline"
                    className="text-xs h-8"
                    onClick={() => setViewingDoc(selectedDocument)}
                  >
                    <Eye className="mr-1.5 h-3.5 w-3.5" /> View Scan
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="text-xs h-8 text-muted-foreground hover:text-foreground"
                    onClick={() => setSelectedDocument(null)}
                  >
                    <X className="mr-1 h-3.5 w-3.5" /> Deselect
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader className="py-4 px-6 flex flex-wrap items-center justify-between gap-3 border-b border-border/50">
              <div>
                <CardTitle className="text-base font-semibold">Medical Documents & Imaging</CardTitle>
                <CardDescription className="text-xs">Authoritative patient imaging (MRI, X-Ray, CT) and clinical records from MongoDB</CardDescription>
              </div>
              <div className="flex items-center gap-1.5 flex-wrap">
                {["all", "mri", "xray", "ct", "dermoscopy", "lab_report", "prescription"].map((cat) => (
                  <Button
                    key={cat}
                    size="sm"
                    variant={docCategoryFilter === cat ? "default" : "outline"}
                    className="h-7 text-[11px] capitalize"
                    onClick={() => setDocCategoryFilter(cat)}
                  >
                    {cat.replace("_", " ")}
                  </Button>
                ))}
              </div>
            </CardHeader>
            <CardContent className="p-4 sm:p-6">
              {filteredDocuments.length === 0 ? (
                <EmptyState
                  title="No Documents or Imaging Found"
                  description={`No uploaded files match the category '${docCategoryFilter}' for ${patientName}.`}
                />
              ) : (
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {filteredDocuments.map((doc: any) => {
                    const docId = doc.document_id || doc.id;
                    const isSelected = selectedDocument?.document_id === docId;
                    const isMri = isBrainMri(doc);

                    return (
                      <div
                        key={docId}
                        data-testid={`doc-card-${docId}`}
                        className={cn(
                          "rounded-xl border bg-card p-4 space-y-3 card-hover flex flex-col justify-between transition-all",
                          isSelected
                            ? "border-primary ring-2 ring-primary/40 bg-primary/[0.03]"
                            : "border-border"
                        )}
                      >
                        <div className="space-y-2">
                          <div className="flex items-start justify-between gap-2">
                            <span className="grid h-8 w-8 place-items-center rounded-lg bg-primary/10 text-primary shrink-0">
                              {isMri ? <Brain className="h-4 w-4" /> : <ImageIcon className="h-4 w-4" />}
                            </span>
                            <div className="flex items-center gap-1.5">
                              {isMri && (
                                <Badge className="bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/30 text-[10px] font-semibold flex items-center gap-1">
                                  <Brain className="h-2.5 w-2.5" /> Brain MRI
                                </Badge>
                              )}
                              <Badge variant="outline" className="text-[10px] uppercase font-semibold">
                                {doc.category || "document"}
                              </Badge>
                            </div>
                          </div>
                          <div>
                            <p className="font-semibold text-sm text-foreground line-clamp-1">{doc.title || doc.original_file_name}</p>
                            <p className="text-[11px] text-muted-foreground mt-0.5 line-clamp-1">
                              {doc.original_file_name || doc.filename || "file"}
                            </p>
                          </div>
                          {doc.mime_type?.startsWith("image/") && (
                            <div className="relative aspect-video w-full overflow-hidden rounded-lg bg-black/5 dark:bg-black/40 border border-border/40 flex items-center justify-center">
                              <AuthenticatedDocImage
                                documentId={docId}
                                alt={doc.title || "Medical scan"}
                              />
                            </div>
                          )}
                          <div className="text-[11px] text-muted-foreground space-y-0.5 border-t border-border/40 pt-2">
                            <p>Document ID: <span className="font-mono text-foreground">{docId}</span></p>
                            <p>Patient: <span className="font-medium text-foreground">{patientName}</span> (<span className="font-mono">{doc.patient_id}</span>)</p>
                            <p>Uploaded: <span>{doc.created_at?.slice(0, 10) || "—"}</span></p>
                            {(doc.file_size_bytes || doc.file_size || doc.size_bytes) && (
                              <p>Size: <span>{(((doc.file_size_bytes || doc.file_size || doc.size_bytes)) / 1024).toFixed(1)} KB</span></p>
                            )}
                          </div>
                        </div>

                        <div className="pt-2 flex flex-col gap-2 border-t border-border/40">
                          <div className="flex items-center gap-2">
                            <Button
                              size="sm"
                              variant="outline"
                              data-testid={`view-doc-${docId}`}
                              className="flex-1 text-xs h-8"
                              onClick={() => setViewingDoc(doc)}
                            >
                              <Eye className="mr-1.5 h-3.5 w-3.5" /> View Scan
                            </Button>
                            <Button
                              size="sm"
                              variant={isSelected ? "default" : "secondary"}
                              data-testid={`select-doc-${docId}`}
                              className="flex-1 text-xs h-8"
                              onClick={() => handleSelectDocument(doc)}
                            >
                              {isSelected ? (
                                <>
                                  <CheckCircle2 className="mr-1.5 h-3.5 w-3.5" /> Selected
                                </>
                              ) : (
                                <>
                                  <Check className="mr-1.5 h-3.5 w-3.5" /> Select Scan
                                </>
                              )}
                            </Button>
                          </div>
                          {(doc.mime_type?.startsWith("image/") || ["mri", "xray", "ct", "dermoscopy", "fundus"].includes(String(doc.category || "").toLowerCase())) && (
                            <Button asChild size="sm" variant="ghost" data-testid={`analyze-doc-${docId}`} className="w-full text-xs h-7 text-primary hover:text-primary hover:bg-primary/5">
                              <Link
                                to="/app/ai-analysis"
                                search={{
                                  document_id: docId,
                                  patient_id: doc.patient_id,
                                  appointment_id: doc.appointment_id || undefined,
                                  medical_record_id: doc.medical_record_id || undefined,
                                  modality: isBrainMri(doc) ? "BRAIN_MRI" : undefined,
                                }}
                              >
                                <Sparkles className="mr-1.5 h-3.5 w-3.5" /> Open in AI Analysis
                              </Link>
                            </Button>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* 3. CONSULTATIONS TAB */}
        <TabsContent value="consultations" className="space-y-4">
          <Card>
            <CardHeader className="py-4 px-6 flex flex-row items-center justify-between border-b border-border/50">
              <div>
                <CardTitle className="text-base font-semibold">Past Consultations</CardTitle>
                <CardDescription className="text-xs">Clinical encounter notes, assessments, and diagnostic findings</CardDescription>
              </div>
              <Badge variant="secondary" className="text-xs">{consultations.length} Consultations</Badge>
            </CardHeader>
            <CardContent className="p-4 sm:p-6">
              {consultations.length === 0 ? (
                <EmptyState
                  title="No Consultations Found"
                  description={`No clinical consultations have been recorded for ${patientName}.`}
                />
              ) : (
                <div className="space-y-3">
                  {consultations.map((c: any) => (
                    <div key={c.consultation_id || c.id} className="rounded-xl border border-border bg-card p-4 space-y-3 card-hover">
                      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border/40 pb-2">
                        <div className="flex items-center gap-2">
                          <Stethoscope className="h-4 w-4 text-primary" />
                          <span className="font-semibold text-sm text-foreground">Consultation {c.consultation_id}</span>
                          <Badge variant="outline" className="text-[10px] uppercase">{c.status || "completed"}</Badge>
                        </div>
                        <span className="text-xs text-muted-foreground">{c.created_at?.slice(0, 10) || "—"}</span>
                      </div>

                      {c.chief_complaint?.complaint && (
                        <div className="text-xs">
                          <span className="font-semibold text-foreground">Chief Complaint: </span>
                          <span className="text-muted-foreground">{c.chief_complaint.complaint}</span>
                        </div>
                      )}

                      {c.diagnoses && c.diagnoses.length > 0 && (
                        <div className="text-xs space-y-1">
                          <span className="font-semibold text-foreground">Diagnoses: </span>
                          <div className="flex flex-wrap gap-1.5 mt-1">
                            {c.diagnoses.map((d: any, idx: number) => (
                              <Badge key={idx} variant="secondary" className="text-[11px]">
                                {d.name || d.diagnosis} {d.type ? `(${d.type})` : ""}
                              </Badge>
                            ))}
                          </div>
                        </div>
                      )}

                      {c.clinical_assessment?.summary && (
                        <div className="text-xs bg-muted/30 p-2.5 rounded-lg text-foreground/90">
                          <span className="font-medium text-muted-foreground block text-[11px] mb-0.5">Clinical Assessment:</span>
                          {c.clinical_assessment.summary}
                        </div>
                      )}

                      <div className="flex items-center justify-between pt-2 border-t border-border/40 text-[11px]">
                        <span className="text-muted-foreground">Appointment: <span className="font-mono text-foreground">{c.appointment_id}</span></span>
                        <Button asChild size="sm" variant="ghost" className="h-7 text-xs">
                          <Link to="/app/consultations/$id" params={{ id: c.consultation_id }}>
                            View Full Consultation <ChevronRight className="ml-1 h-3 w-3" />
                          </Link>
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* 4. PRESCRIPTIONS TAB */}
        <TabsContent value="prescriptions" className="space-y-4">
          <Card>
            <CardHeader className="py-4 px-6 flex flex-row items-center justify-between border-b border-border/50">
              <div>
                <CardTitle className="text-base font-semibold">Prescriptions & Regimens</CardTitle>
                <CardDescription className="text-xs">Active and historical medication orders for {patientName}</CardDescription>
              </div>
              <Badge variant="secondary" className="text-xs">{prescriptions.length} Prescriptions</Badge>
            </CardHeader>
            <CardContent className="p-4 sm:p-6">
              {prescriptions.length === 0 ? (
                <EmptyState
                  title="No Prescriptions Found"
                  description={`No prescriptions have been issued for ${patientName}.`}
                />
              ) : (
                <div className="space-y-3">
                  {prescriptions.map((rx: any) => (
                    <div key={rx.prescription_id || rx.id} className="rounded-xl border border-border bg-card p-4 space-y-3 card-hover">
                      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border/40 pb-2">
                        <div className="flex items-center gap-2">
                          <Pill className="h-4 w-4 text-primary" />
                          <span className="font-semibold text-sm text-foreground">Prescription {rx.prescription_id}</span>
                          <Badge variant="outline" className="text-[10px] uppercase font-mono">{rx.status || "active"}</Badge>
                        </div>
                        <span className="text-xs text-muted-foreground">{rx.created_at?.slice(0, 10) || "—"}</span>
                      </div>

                      {/* Medication Items List */}
                      {Array.isArray(rx.medications) && rx.medications.length > 0 && (
                        <div className="space-y-2">
                          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Prescribed Medications</p>
                          <div className="grid gap-2 sm:grid-cols-2">
                            {rx.medications.map((m: any, idx: number) => (
                              <div key={idx} className="rounded-lg bg-muted/40 p-2.5 text-xs space-y-0.5">
                                <p className="font-semibold text-foreground text-sm">{m.name}</p>
                                <p className="text-muted-foreground">{m.dosage} • {m.frequency} • {m.duration}</p>
                                {m.instructions && <p className="text-[11px] text-muted-foreground italic">"{m.instructions}"</p>}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      <div className="flex items-center justify-between pt-2 border-t border-border/40 text-[11px]">
                        <span className="text-muted-foreground">Consultation: <span className="font-mono text-foreground">{rx.consultation_id}</span></span>
                        <Button asChild size="sm" variant="ghost" className="h-7 text-xs">
                          <Link to="/app/prescriptions/$id" params={{ id: rx.prescription_id }}>
                            View Prescription Details <ChevronRight className="ml-1 h-3 w-3" />
                          </Link>
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* 5. CLINICAL TIMELINE TAB */}
        <TabsContent value="timeline" className="space-y-4">
          <Card>
            <CardHeader className="py-4 px-6 border-b border-border/50">
              <CardTitle className="text-base font-semibold">Aggregated Clinical Timeline</CardTitle>
              <CardDescription className="text-xs">Chronological historical care log for {patientName}</CardDescription>
            </CardHeader>
            <CardContent className="p-4 sm:p-6">
              {timeline.length === 0 ? (
                <EmptyState
                  title="No Timeline Events"
                  description={`No historical clinical events found for ${patientName}.`}
                />
              ) : (
                <div className="relative pl-6 space-y-6 before:absolute before:left-2.5 before:top-2 before:bottom-2 before:w-0.5 before:bg-border">
                  {timeline.map((ev: any, idx: number) => (
                    <div key={idx} className="relative space-y-1">
                      <span className="absolute -left-6 top-1 grid h-4 w-4 place-items-center rounded-full bg-primary ring-4 ring-background" />
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-semibold text-foreground">{ev.title || ev.event_type || "Clinical Event"}</span>
                        <Badge variant="outline" className="text-[10px] uppercase">{ev.type || ev.category || "log"}</Badge>
                        <span className="text-[11px] text-muted-foreground ml-auto">{ev.timestamp?.slice(0, 10) || ev.date || "—"}</span>
                      </div>
                      <p className="text-xs text-muted-foreground">{ev.description || ev.summary || ev.details || "Encounter event recorded."}</p>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Secure High-Res Scan Viewer Dialog */}
      <Dialog open={!!viewingDoc} onOpenChange={(open) => !open && setViewingDoc(null)}>
        <DialogContent className="max-w-2xl sm:max-w-3xl">
          <DialogHeader>
            <div className="flex items-center gap-2">
              <Badge variant="outline" className="uppercase font-semibold">
                {viewingDoc?.category || "Medical Scan"}
              </Badge>
              {isBrainMri(viewingDoc) && (
                <Badge className="bg-emerald-500/10 text-emerald-600 border-emerald-500/30 flex items-center gap-1 font-semibold">
                  <Brain className="h-3 w-3" /> Brain MRI
                </Badge>
              )}
            </div>
            <DialogTitle className="text-lg font-bold">
              {viewingDoc?.title || viewingDoc?.original_file_name}
            </DialogTitle>
            <DialogDescription className="text-xs text-muted-foreground">
              Patient: {patientName} ({viewingDoc?.patient_id}) • Uploaded: {viewingDoc?.created_at?.slice(0, 10)}
            </DialogDescription>
          </DialogHeader>

          <div className="relative aspect-video max-h-[460px] w-full overflow-hidden rounded-lg bg-black/90 border border-border flex items-center justify-center">
            {viewingDoc?.mime_type?.startsWith("image/") ? (
              <AuthenticatedDocImage
                documentId={viewingDoc.document_id || viewingDoc.id}
                alt={viewingDoc.title || "Scan"}
                className="h-full w-full object-contain"
              />
            ) : (
              <div className="text-center p-8 text-muted-foreground">
                <FileText className="h-16 w-16 mx-auto mb-2 opacity-50" />
                <p className="text-sm font-medium">{viewingDoc?.original_file_name}</p>
              </div>
            )}
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs bg-muted/30 p-3 rounded-lg border border-border/50">
            <div>
              <span className="text-muted-foreground block text-[10px]">Document ID</span>
              <span className="font-mono font-medium text-foreground">{viewingDoc?.document_id || viewingDoc?.id}</span>
            </div>
            <div>
              <span className="text-muted-foreground block text-[10px]">MIME Type</span>
              <span className="font-mono text-foreground">{viewingDoc?.mime_type}</span>
            </div>
            <div>
              <span className="text-muted-foreground block text-[10px]">Size</span>
              <span className="text-foreground">
                {viewingDoc?.file_size_bytes || viewingDoc?.size_bytes ? `${(((viewingDoc.file_size_bytes || viewingDoc.size_bytes)) / 1024).toFixed(1)} KB` : "—"}
              </span>
            </div>
            <div>
              <span className="text-muted-foreground block text-[10px]">Linked Encounter</span>
              <span className="font-mono text-foreground">{viewingDoc?.appointment_id || viewingDoc?.medical_record_id || "None"}</span>
            </div>
          </div>

          <DialogFooter className="flex flex-row items-center justify-between sm:justify-between w-full pt-2">
            <Button
              variant="outline"
              size="sm"
              disabled={downloadingDocId === (viewingDoc?.document_id || viewingDoc?.id)}
              onClick={() => downloadAuthenticatedDoc(viewingDoc)}
            >
              {downloadingDocId === (viewingDoc?.document_id || viewingDoc?.id) ? (
                <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
              ) : (
                <Download className="mr-1.5 h-3.5 w-3.5" />
              )}
              Download Scan
            </Button>

            <Button
              variant={selectedDocument?.document_id === (viewingDoc?.document_id || viewingDoc?.id) ? "default" : "secondary"}
              size="sm"
              onClick={() => {
                handleSelectDocument(viewingDoc);
                setViewingDoc(null);
              }}
            >
              {selectedDocument?.document_id === (viewingDoc?.document_id || viewingDoc?.id) ? (
                <>
                  <CheckCircle2 className="mr-1.5 h-3.5 w-3.5" /> Selected
                </>
              ) : (
                <>
                  <Check className="mr-1.5 h-3.5 w-3.5" /> Select This Scan
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
