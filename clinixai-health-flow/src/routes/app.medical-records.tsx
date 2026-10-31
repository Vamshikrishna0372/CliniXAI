import { useEffect, useMemo, useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import {
  Download, Eye, Search, Trash2, Plus, FileText, AlertCircle,
  Calendar, User, Stethoscope, Clock, CheckCircle2, Archive, Loader2, Brain
} from "lucide-react";
import { PageHeader } from "@/components/app-shell/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from "@/components/ui/dialog";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/dashboard/states";
import { FileUpload } from "@/components/dashboard/file-upload";
import { useClinix } from "@/lib/store/clinix-store";
import { useAuth } from "@/lib/auth-context";
import { apiClient } from "@/lib/api-client";
import { toast } from "sonner";

export const Route = createFileRoute("/app/medical-records")({
  head: () => ({ meta: [{ title: "Medical Records — CliniXAI" }, { name: "robots", content: "noindex" }] }),
  validateSearch: (search: Record<string, unknown>) => ({
    patient_id: typeof search.patient_id === "string" ? search.patient_id : typeof search.patientId === "string" ? search.patientId : undefined,
  }),
  component: MedicalRecordsPage,
});

export interface MedicalRecordItem {
  record_id: string;
  patient_id: string;
  appointment_id?: string | null;
  consultation_id?: string | null;
  doctor_id?: string | null;
  record_type: string;
  title: string;
  clinical_date?: string | null;
  diagnosis?: string | null;
  clinical_notes?: string | null;
  treatment_plan?: string | null;
  symptoms?: string[] | null;
  content_type?: string;
  size_bytes?: number;
  status: string;
  created_at: string;
  source?: string;
  file?: {
    original_filename: string;
    content_type: string;
    size_bytes: number;
  } | null;
}

const RECORD_TYPES = [
  { value: "all", label: "All Types" },
  { value: "clinical_document", label: "Clinical Document" },
  { value: "diagnosis", label: "Diagnosis" },
  { value: "clinical_note", label: "Clinical Note" },
  { value: "consultation", label: "Consultation" },
  { value: "lab_result", label: "Lab Result" },
  { value: "follow_up", label: "Follow-up" },
  { value: "other", label: "Other" },
];

function MedicalRecordsPage() {
  const { user } = useAuth();
  const { patients, appointments } = useClinix();
  const search = Route.useSearch();
  const searchPatId = search.patient_id;

  const isDoctor = user?.role === "doctor";
  const isStaff = user?.role === "staff";
  const isAdmin = user?.role === "admin";
  const canManageRecords = isDoctor || isStaff || isAdmin;

  // Authorized patients for doctors (derived from appointments or full patient list for staff/admin)
  const availablePatients = useMemo(() => {
    if (!canManageRecords) return [];
    if (isDoctor) {
      const aptPats = new Set(appointments.map((a) => a.patientId));
      if (searchPatId) aptPats.add(searchPatId);
      return patients.filter((p) => aptPats.has(p.id) || p.id === searchPatId);
    }
    return patients;
  }, [patients, appointments, canManageRecords, isDoctor, searchPatId]);

  // Selected patient for doctor / staff / admin view
  const myPatient = patients.find((p) => p.email === user?.email || p.id === user?.patientId || p.id === user?.id);
  const myPatId = (user?.patientId && user.patientId.startsWith("PAT-"))
    ? user.patientId
    : (myPatient?.id && myPatient.id.startsWith("PAT-"))
      ? myPatient.id
      : (user?.id || "");

  const initialPatientId = searchPatId
    ? searchPatId
    : canManageRecords
      ? (availablePatients[0]?.id || "")
      : myPatId;

  const [selectedPatientId, setSelectedPatientId] = useState<string>(initialPatientId);

  useEffect(() => {
    if (searchPatId && searchPatId !== selectedPatientId) {
      setSelectedPatientId(searchPatId);
    }
  }, [searchPatId]);
  const [records, setRecords] = useState<MedicalRecordItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedType, setSelectedType] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");

  // Detail dialog state
  const [detailRecord, setDetailRecord] = useState<MedicalRecordItem | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  // Create record modal state
  const [createOpen, setCreateOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newDiagnosis, setNewDiagnosis] = useState("");
  const [newRecordType, setNewRecordType] = useState("clinical_document");
  const [newClinicalDate, setNewClinicalDate] = useState(new Date().toISOString().split("T")[0]);
  const [newClinicalNotes, setNewClinicalNotes] = useState("");
  const [newTreatmentPlan, setNewTreatmentPlan] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [imagePreviewOpen, setImagePreviewOpen] = useState(false);
  const [previewImageUrl, setPreviewImageUrl] = useState<string | null>(null);
  const [loadingPreviewImage, setLoadingPreviewImage] = useState(false);

  useEffect(() => {
    let active = true;
    let url: string | null = null;
    if (imagePreviewOpen && detailRecord?.record_id) {
      setLoadingPreviewImage(true);
      apiClient.medicalRecords
        .getFileBlob(detailRecord.record_id)
        .then((blob) => {
          if (!active) return;
          url = URL.createObjectURL(blob);
          setPreviewImageUrl(url);
          setLoadingPreviewImage(false);
        })
        .catch(() => {
          if (!active) return;
          setLoadingPreviewImage(false);
        });
    } else {
      setPreviewImageUrl(null);
    }
    return () => {
      active = false;
      if (url) {
        URL.revokeObjectURL(url);
      }
    };
  }, [imagePreviewOpen, detailRecord?.record_id]);

  // Sync selectedPatientId when availablePatients changes
  useEffect(() => {
    if (canManageRecords && !selectedPatientId && availablePatients.length > 0) {
      setSelectedPatientId(availablePatients[0].id);
    }
  }, [canManageRecords, selectedPatientId, availablePatients]);

  const fetchRecords = async () => {
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, any> = { page_size: 100 };
      if (canManageRecords && selectedPatientId) {
        params.patient_id = selectedPatientId;
      }
      if (selectedType !== "all") {
        params.record_type = selectedType;
      }
      if (searchQuery.trim()) {
        params.search = searchQuery.trim();
      }

      const res = await apiClient.medicalRecords.list(params);
      const items = res?.data || res?.items || [];
      setRecords(items);
    } catch (err: any) {
      console.error("Failed to load medical records:", err);
      setError(err?.message || "Failed to load medical records from server.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRecords();
  }, [selectedPatientId, selectedType, searchQuery]);

  const handleOpenDetail = async (rec: MedicalRecordItem) => {
    setLoadingDetail(true);
    setDetailRecord(rec);
    try {
      const full = await apiClient.medicalRecords.getDetail(rec.record_id);
      if (full?.data) {
        setDetailRecord(full.data);
      }
    } catch (err: any) {
      console.error("Failed to load record details:", err);
    } finally {
      setLoadingDetail(false);
    }
  };

  const handleCreateRecord = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTitle.trim()) {
      toast.error("Please enter a record title.");
      return;
    }

    const targetPatId = canManageRecords ? selectedPatientId : undefined;
    if (canManageRecords && !targetPatId) {
      toast.error("Please select a target patient.");
      return;
    }

    setCreating(true);
    try {
      const validDate = newClinicalDate && /^\d{4}-\d{2}-\d{2}$/.test(newClinicalDate)
        ? newClinicalDate
        : new Date().toISOString().split("T")[0];

      if (selectedFile) {
        const fd = new FormData();
        fd.append("title", newTitle.trim());
        fd.append("record_type", newRecordType);
        fd.append("clinical_date", validDate);
        if (targetPatId) fd.append("patient_id", targetPatId);
        if (newDiagnosis.trim() && canManageRecords) fd.append("diagnosis", newDiagnosis.trim());
        if (newClinicalNotes.trim()) fd.append("clinical_notes", newClinicalNotes.trim());
        if (newTreatmentPlan.trim() && canManageRecords) fd.append("treatment_plan", newTreatmentPlan.trim());
        fd.append("file", selectedFile);

        await apiClient.medicalRecords.upload(fd);
      } else {
        await apiClient.medicalRecords.create({
          title: newTitle.trim(),
          diagnosis: newDiagnosis.trim() || undefined,
          record_type: newRecordType,
          clinical_date: validDate,
          clinical_notes: newClinicalNotes.trim() || undefined,
          treatment_plan: newTreatmentPlan.trim() || undefined,
          patient_id: targetPatId,
        });
      }

      toast.success("Medical record created successfully.");
      setCreateOpen(false);
      // Reset form
      setNewTitle("");
      setNewDiagnosis("");
      setNewClinicalNotes("");
      setNewTreatmentPlan("");
      setSelectedFile(null);
      // Refetch
      fetchRecords();
    } catch (err: any) {
      toast.error(`Creation failed: ${err?.message || "Server error"}`);
    } finally {
      setCreating(false);
    }
  };

  const handleDeleteRecord = async (recordId: string) => {
    try {
      await apiClient.medicalRecords.delete(recordId);
      toast.success("Medical record removed.");
      fetchRecords();
    } catch (err: any) {
      toast.error(`Delete failed: ${err?.message || "Server error"}`);
    }
  };

  const handleArchiveRecord = async (recordId: string) => {
    try {
      await apiClient.medicalRecords.archive(recordId);
      toast.success("Medical record archived.");
      fetchRecords();
    } catch (err: any) {
      toast.error(`Archive failed: ${err?.message || "Server error"}`);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Medical Records"
        description="Authoritative, role-aware clinical records, consultations, and health documentation."
        actions={
          <Dialog open={createOpen} onOpenChange={(open) => { setCreateOpen(open); if (!open) setSelectedFile(null); }}>
            <DialogTrigger asChild>
              <Button>
                <Plus className="mr-1.5 h-4 w-4" /> {canManageRecords ? "Add Clinical Record" : "Upload Medical Document"}
              </Button>
            </DialogTrigger>
            <DialogContent className="max-h-[85vh] max-w-lg overflow-y-auto">
              <DialogHeader>
                <DialogTitle>{canManageRecords ? "Add Clinical Medical Record" : "Upload Medical Document / Scan"}</DialogTitle>
              </DialogHeader>
              <form onSubmit={handleCreateRecord} className="space-y-4 pt-2">
                {canManageRecords && (
                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-muted-foreground">Target Patient</label>
                    <Select value={selectedPatientId} onValueChange={setSelectedPatientId}>
                      <SelectTrigger>
                        <SelectValue placeholder="Select patient" />
                      </SelectTrigger>
                      <SelectContent>
                        {availablePatients.map((p) => (
                          <SelectItem key={p.id} value={p.id}>
                            {p.firstName} {p.lastName} ({p.id})
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                )}

                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-muted-foreground">Record Title *</label>
                  <Input
                    placeholder={canManageRecords ? "e.g. Annual Cardiovascular Review" : "e.g. Chest X-Ray Screening"}
                    value={newTitle}
                    onChange={(e) => setNewTitle(e.target.value)}
                    required
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-muted-foreground">Record Type</label>
                    <Select value={newRecordType} onValueChange={setNewRecordType}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {RECORD_TYPES.filter((t) => t.value !== "all").map((t) => (
                          <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-muted-foreground">Clinical Date</label>
                    <Input
                      type="date"
                      value={newClinicalDate}
                      onChange={(e) => setNewClinicalDate(e.target.value)}
                    />
                  </div>
                </div>

                {canManageRecords && (
                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-muted-foreground">Primary Diagnosis</label>
                    <Input
                      placeholder="e.g. Essential Hypertension (I10)"
                      value={newDiagnosis}
                      onChange={(e) => setNewDiagnosis(e.target.value)}
                    />
                  </div>
                )}

                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-muted-foreground">
                    {canManageRecords ? "Clinical Notes / Findings" : "Description / Notes (Optional)"}
                  </label>
                  <textarea
                    className="w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring min-h-[70px]"
                    placeholder={canManageRecords ? "Enter clinical assessment or examination findings..." : "Notes about this report or image..."}
                    value={newClinicalNotes}
                    onChange={(e) => setNewClinicalNotes(e.target.value)}
                  />
                </div>

                {canManageRecords && (
                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-muted-foreground">Treatment Plan</label>
                    <textarea
                      className="w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring min-h-[60px]"
                      placeholder="Prescriptions, lifestyle recommendations, follow-up instructions..."
                      value={newTreatmentPlan}
                      onChange={(e) => setNewTreatmentPlan(e.target.value)}
                    />
                  </div>
                )}

                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-muted-foreground">Attach Medical Document / Image (Optional)</label>
                  <FileUpload
                    onFileSelect={(f) => setSelectedFile(f)}
                    label="Attach medical scan, image, or report"
                    hint="JPEG, PNG, WEBP, PDF up to 10 MB"
                  />
                </div>

                <DialogFooter className="pt-2">
                  <Button type="button" variant="outline" onClick={() => { setCreateOpen(false); setSelectedFile(null); }}>
                    Cancel
                  </Button>
                  <Button type="submit" disabled={creating}>
                    {creating ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                    {selectedFile ? "Upload & Save" : "Save Record"}
                  </Button>
                </DialogFooter>
              </form>
            </DialogContent>
          </Dialog>
        }
      />

      {/* Patient Selector Bar for Doctors / Staff / Admin */}
      {canManageRecords && availablePatients.length > 0 && (
        <Card className="border-border/60 bg-muted/20">
          <CardContent className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <User className="h-4 w-4 text-primary" />
              <span className="text-sm font-medium">Viewing Records For Patient:</span>
            </div>
            <div className="w-full sm:w-72">
              <Select value={selectedPatientId} onValueChange={setSelectedPatientId}>
                <SelectTrigger className="bg-background">
                  <SelectValue placeholder="Select patient" />
                </SelectTrigger>
                <SelectContent>
                  {availablePatients.map((p) => (
                    <SelectItem key={p.id} value={p.id}>
                      {p.firstName} {p.lastName} • {p.id}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Filter and Search Bar */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <Tabs
          value={selectedType}
          onValueChange={setSelectedType}
          className="w-full min-w-0 flex-1 overflow-x-auto"
        >
          <TabsList className="w-max">
            {RECORD_TYPES.map((t) => (
              <TabsTrigger key={t.value} value={t.value}>{t.label}</TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
        <div className="relative w-full shrink-0 sm:w-64">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search diagnosis, title…"
            className="pl-9"
          />
        </div>
      </div>

      {/* State Handlers: Loading, Error, Empty, Success */}
      {loading ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center p-12 text-center">
            <Loader2 className="h-8 w-8 animate-spin text-primary mb-3" />
            <p className="text-sm font-medium">Loading medical records…</p>
            <p className="text-xs text-muted-foreground">Authoritative clinical records from MongoDB</p>
          </CardContent>
        </Card>
      ) : error ? (
        <Card className="border-destructive/40 bg-destructive/5">
          <CardContent className="flex flex-col items-center justify-center p-8 text-center space-y-3">
            <AlertCircle className="h-8 w-8 text-destructive" />
            <p className="text-sm font-semibold text-destructive">{error}</p>
            <Button variant="outline" size="sm" onClick={fetchRecords}>
              Retry
            </Button>
          </CardContent>
        </Card>
      ) : records.length === 0 ? (
        <EmptyState
          title="No medical records available."
          description="Clinical consultation summaries, doctor diagnoses, and reports will appear here."
        />
      ) : (
        <Card>
          <CardContent className="p-0">
            <ul className="divide-y divide-border">
              {records.map((rec) => (
                <RecordRow
                  key={rec.record_id}
                  record={rec}
                  onView={() => handleOpenDetail(rec)}
                  onArchive={() => handleArchiveRecord(rec.record_id)}
                  onDelete={() => handleDeleteRecord(rec.record_id)}
                  canManage={canManageRecords}
                />
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {/* Record Detail Dialog */}
      <Dialog open={!!detailRecord} onOpenChange={(o) => !o && setDetailRecord(null)}>
        <DialogContent className="max-h-[85vh] max-w-lg overflow-y-auto">
          <DialogHeader>
            <div className="flex items-center gap-2">
              <Badge variant="outline" className="text-xs uppercase font-mono">
                {detailRecord?.record_type.replace(/_/g, " ")}
              </Badge>
              <Badge variant={detailRecord?.status === "active" ? "default" : "secondary"}>
                {detailRecord?.status}
              </Badge>
            </div>
            <DialogTitle className="text-lg font-bold pt-1">{detailRecord?.title}</DialogTitle>
          </DialogHeader>

          {loadingDetail ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-primary" />
            </div>
          ) : detailRecord ? (
            <div className="space-y-4 text-sm pt-2">
              <div className="grid grid-cols-2 gap-3 bg-muted/40 p-3 rounded-lg text-xs">
                <div>
                  <span className="text-muted-foreground block">Record ID:</span>
                  <span className="font-mono font-medium">{detailRecord.record_id}</span>
                </div>
                <div>
                  <span className="text-muted-foreground block">Clinical Date:</span>
                  <span className="font-medium">{detailRecord.clinical_date || "N/A"}</span>
                </div>
                <div>
                  <span className="text-muted-foreground block">Patient ID:</span>
                  <span className="font-mono font-medium">{detailRecord.patient_id}</span>
                </div>
                <div>
                  <span className="text-muted-foreground block">Attending Doctor:</span>
                  <span className="font-medium">{detailRecord.doctor_id || "Hospital System"}</span>
                </div>
              </div>

              {detailRecord.diagnosis && (
                <div className="rounded-lg border border-primary/20 bg-primary/5 p-3">
                  <span className="text-xs font-semibold text-primary block mb-1">Diagnosis</span>
                  <p className="font-medium">{detailRecord.diagnosis}</p>
                </div>
              )}

              {detailRecord.clinical_notes && (
                <div>
                  <span className="text-xs font-semibold text-muted-foreground block mb-1">Clinical Notes & Assessment</span>
                  <p className="whitespace-pre-wrap text-muted-foreground leading-relaxed bg-muted/20 p-3 rounded-md border border-border">
                    {detailRecord.clinical_notes}
                  </p>
                </div>
              )}

              {detailRecord.treatment_plan && (
                <div>
                  <span className="text-xs font-semibold text-muted-foreground block mb-1">Treatment Plan</span>
                  <p className="whitespace-pre-wrap text-muted-foreground leading-relaxed bg-muted/20 p-3 rounded-md border border-border">
                    {detailRecord.treatment_plan}
                  </p>
                </div>
              )}

              {detailRecord.file && (
                <div className="space-y-3 rounded-lg border border-border p-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2.5">
                      <FileText className="h-5 w-5 text-primary" />
                      <div>
                        <p className="font-medium text-xs truncate max-w-[200px]">{detailRecord.file.original_filename}</p>
                        <p className="text-[11px] text-muted-foreground">{(detailRecord.file.size_bytes / 1024).toFixed(1)} KB • {detailRecord.file.content_type}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {detailRecord.file.content_type?.startsWith("image/") && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => setImagePreviewOpen(true)}
                        >
                          <Eye className="mr-1.5 h-3.5 w-3.5" /> Preview
                        </Button>
                      )}
                      {(detailRecord.record_type === "mri" || detailRecord.record_type === "medical_image" || detailRecord.file.content_type?.startsWith("image/")) && (
                        <Button
                          asChild
                          size="sm"
                          variant="outline"
                          className="border-primary/40 text-primary hover:bg-primary/5"
                        >
                          <Link to="/app/ai-analysis" search={{ recordId: detailRecord.record_id }}>
                            <Brain className="mr-1.5 h-3.5 w-3.5" /> AI Analysis
                          </Link>
                        </Button>
                      )}
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={async () => {
                          try {
                            const blob = await apiClient.medicalRecords.getFileBlob(detailRecord.record_id);
                            const url = URL.createObjectURL(blob);
                            const a = document.createElement("a");
                            a.href = url;
                            a.download = detailRecord.file?.original_filename || `record-${detailRecord.record_id}`;
                            document.body.appendChild(a);
                            a.click();
                            document.body.removeChild(a);
                            URL.revokeObjectURL(url);
                          } catch (err: any) {
                            toast.error("Download failed", { description: err.message || "Failed to download record file" });
                          }
                        }}
                      >
                        <Download className="mr-1.5 h-3.5 w-3.5" /> Download
                      </Button>
                    </div>
                  </div>
                </div>
              )}

              <div className="text-[11px] text-muted-foreground pt-2 border-t border-border flex justify-between">
                <span>Recorded: {new Date(detailRecord.created_at).toLocaleString()}</span>
                <span>Source: {detailRecord.source || "clinical"}</span>
              </div>
            </div>
          ) : null}
        </DialogContent>
      </Dialog>

      {/* Image Preview Modal */}
      <Dialog open={imagePreviewOpen} onOpenChange={setImagePreviewOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>{detailRecord?.file?.original_filename || "Medical Image Preview"}</DialogTitle>
          </DialogHeader>
          <div className="flex items-center justify-center p-3 bg-muted/20 rounded-lg min-h-[300px] overflow-hidden">
            {loadingPreviewImage ? (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" /> Loading image...
              </div>
            ) : previewImageUrl ? (
              <img
                src={previewImageUrl}
                alt={detailRecord?.file?.original_filename || "Medical Image"}
                className="max-h-[60vh] max-w-full object-contain rounded shadow-sm"
              />
            ) : (
              <div className="text-sm text-muted-foreground">No preview available</div>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function RecordRow({
  record,
  onView,
  onArchive,
  onDelete,
  canManage,
}: {
  record: MedicalRecordItem;
  onView: () => void;
  onArchive: () => void;
  onDelete: () => void;
  canManage: boolean;
}) {
  return (
    <li className="grid grid-cols-1 gap-2 p-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,180px)_minmax(0,130px)_minmax(0,100px)_auto] lg:items-center [&>*]:min-w-0 hover:bg-muted/10 transition-colors">
      <div className="min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          <p className="truncate text-sm font-semibold">{record.title}</p>
          <Badge variant="outline" className="text-[10px] uppercase font-mono px-1.5 py-0">
            {record.record_type.replace(/_/g, " ")}
          </Badge>
        </div>
        {record.diagnosis ? (
          <p className="text-xs text-primary font-medium truncate">Diagnosis: {record.diagnosis}</p>
        ) : (
          <p className="text-xs text-muted-foreground truncate">{record.record_id} • Patient {record.patient_id}</p>
        )}
      </div>

      <div className="text-xs text-muted-foreground flex items-center gap-1.5">
        <Stethoscope className="h-3.5 w-3.5 shrink-0" />
        <span className="truncate">{record.doctor_id ? `Dr. Ref: ${record.doctor_id}` : "Clinical Staff"}</span>
      </div>

      <div className="text-xs text-muted-foreground flex items-center gap-1.5">
        <Calendar className="h-3.5 w-3.5 shrink-0" />
        <span>{record.clinical_date || new Date(record.created_at).toLocaleDateString()}</span>
      </div>

      <div>
        <Badge variant={record.status === "active" ? "default" : "secondary"} className="text-[11px] capitalize">
          {record.status}
        </Badge>
      </div>

      <div className="flex flex-wrap items-center gap-2 sm:justify-end">
        <Button size="sm" variant="outline" onClick={onView}>
          <Eye className="mr-1.5 h-3.5 w-3.5" /> Details
        </Button>

        {record.file && (
          <Button
            size="sm"
            variant="outline"
            onClick={async () => {
              try {
                const blob = await apiClient.medicalRecords.getFileBlob(record.record_id);
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = record.file?.original_filename || `record-${record.record_id}`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(url);
              } catch (err: any) {
                toast.error("Download failed", { description: err.message || "Failed to download record file" });
              }
            }}
          >
            <Download className="mr-1.5 h-3.5 w-3.5" /> Download
          </Button>
        )}

        {(record.record_type === "mri" || record.record_type === "medical_image" || record.file?.content_type?.startsWith("image/")) && (
          <Button asChild size="sm" variant="outline" className="border-primary/40 text-primary hover:bg-primary/5">
            <Link to="/app/ai-analysis" search={{ recordId: record.record_id }}>
              <Brain className="mr-1.5 h-3.5 w-3.5" /> AI Analysis
            </Link>
          </Button>
        )}

        {canManage && (
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button size="sm" variant="ghost" className="text-destructive hover:text-destructive">
                <Trash2 className="h-3.5 w-3.5" />
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Delete this medical record?</AlertDialogTitle>
                <AlertDialogDescription>
                  This will mark "{record.title}" as deleted. Historical clinical records remain in database audits.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                <AlertDialogAction
                  onClick={onDelete}
                  className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                >
                  Delete
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        )}
      </div>
    </li>
  );
}
