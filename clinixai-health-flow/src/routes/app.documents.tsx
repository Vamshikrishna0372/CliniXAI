import { useEffect, useMemo, useRef, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import {
  UploadCloud, Trash2, Search, LayoutGrid, List, Eye, Download, Printer, FileText, Image as ImgIcon, Loader2,
} from "lucide-react";
import { PageHeader } from "@/components/app-shell/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription,
  AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { FileUpload } from "@/components/dashboard/file-upload";
import { DocumentBadge } from "@/components/domain/status-badge";
import { EmptyState } from "@/components/dashboard/states";
import { fmtDate, type MedDocument } from "@/lib/mock/domain";
import { useAuth } from "@/lib/auth-context";
import { useClinix } from "@/lib/store/clinix-store";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

import { apiClient } from "@/lib/api-client";

export const Route = createFileRoute("/app/documents")({
  head: () => ({ meta: [{ title: "Documents — CliniXAI" }, { name: "robots", content: "noindex" }] }),
  component: DocumentsPage,
});

const CATEGORIES: MedDocument["category"][] = [
  "Brain MRI",
  "Chest X-Ray",
  "CT Scan",
  "Lab Report",
  "Prescription",
  "Consultation",
  "Other",
];
const CATEGORY_LABEL: Record<string, string> = {
  "Brain MRI": "Brain MRI",
  "Chest X-Ray": "Chest X-Ray",
  "CT Scan": "CT Scan",
  "Lab Report": "Lab Report",
  Prescription: "Prescription",
  Consultation: "Consultation",
  "Medical Image": "Medical Image",
  "Diagnostic Report": "Lab Report",
  "AI Report": "AI Report",
  Other: "Other",
};

type SortKey = "date-desc" | "date-asc" | "name-asc" | "name-desc" | "size-desc" | "size-asc";
type ViewMode = "grid" | "list";

function fileTypeFrom(name: string): MedDocument["fileType"] {
  const ext = name.split(".").pop()?.toLowerCase();
  if (ext === "png") return "PNG";
  if (ext === "jpg" || ext === "jpeg") return "JPG";
  if (ext === "dcm") return "DICOM";
  return "PDF";
}

function DocumentsPage() {
  const { user } = useAuth();
  const { documents, patients, getPatient, uploadDocument, removeDocument } = useClinix();
  const isStaffLike = user?.role === "staff" || user?.role === "admin" || user?.role === "doctor";

  const patient = patients.find((p) => (p.email && p.email === user?.email) || p.id === user?.patientId || (p as any).userId === user?.id);
  const currentPatId = (user?.patientId && user.patientId.startsWith("PAT-"))
    ? user.patientId
    : (patient?.id && patient.id.startsWith("PAT-"))
      ? patient.id
      : "";

  const [uploadOpen, setUploadOpen] = useState(false);
  const [uploadCat, setUploadCat] = useState<MedDocument["category"]>("Brain MRI");
  const [uploadPatient, setUploadPatient] = useState(isStaffLike ? (patients[0]?.id ?? "") : currentPatId);

  const [filterPatient, setFilterPatient] = useState<string>(isStaffLike ? "all" : currentPatId);
  const [filterCat, setFilterCat] = useState<string>("all");
  const [q, setQ] = useState("");
  const [sort, setSort] = useState<SortKey>("date-desc");
  const [view, setView] = useState<ViewMode>("grid");
  const [preview, setPreview] = useState<MedDocument | null>(null);
  const [previewBlobUrl, setPreviewBlobUrl] = useState<string | null>(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    let active = true;
    let url: string | null = null;
    if (preview?.id) {
      setLoadingPreview(true);
      apiClient.documents
        .getFileBlob(preview.id)
        .then((blob) => {
          if (!active) return;
          url = URL.createObjectURL(blob);
          setPreviewBlobUrl(url);
          setLoadingPreview(false);
        })
        .catch(() => {
          if (!active) return;
          setLoadingPreview(false);
        });
    } else {
      setPreviewBlobUrl(null);
    }
    return () => {
      active = false;
      if (url) {
        URL.revokeObjectURL(url);
      }
    };
  }, [preview?.id]);

  const scoped = useMemo(
    () => (isStaffLike ? documents : documents.filter((d) => d.patientId === currentPatId)),
    [documents, isStaffLike, currentPatId],
  );

  const filtered = useMemo(() => {
    let list = scoped.filter((d) => {
      if (isStaffLike && filterPatient !== "all" && d.patientId !== filterPatient) return false;
      if (filterCat !== "all" && d.category !== filterCat) return false;
      if (q && !(d.name + " " + d.patientId).toLowerCase().includes(q.toLowerCase())) return false;
      return true;
    });
    list = [...list].sort((a, b) => {
      switch (sort) {
        case "date-asc": return a.date < b.date ? -1 : 1;
        case "name-asc": return a.name.localeCompare(b.name);
        case "name-desc": return b.name.localeCompare(a.name);
        case "size-desc": return b.sizeKb - a.sizeKb;
        case "size-asc": return a.sizeKb - b.sizeKb;
        default: return a.date < b.date ? 1 : -1;
      }
    });
    return list;
  }, [scoped, isStaffLike, filterPatient, filterCat, q, sort]);

  const [uploading, setUploading] = useState(false);

  const doUpload = async (files: FileList | File[] | null) => {
    if (!files || files.length === 0) return;
    if (isStaffLike && !uploadPatient) { toast.error("Select a patient first"); return; }
    const pid = isStaffLike ? uploadPatient : currentPatId;
    if (!pid || !pid.startsWith("PAT-")) {
      toast.error("Canonical patient profile (PAT-...) required for document upload.");
      return;
    }
    setUploading(true);
    let successCount = 0;

    for (const f of Array.from(files)) {
      try {
        let effectiveCat = uploadCat;
        const lowerName = f.name.toLowerCase();
        if (effectiveCat === "Other") {
          if (lowerName.includes("mri") || lowerName.includes("brain")) {
            effectiveCat = "Brain MRI";
          } else if (lowerName.includes("xray") || lowerName.includes("x-ray") || lowerName.includes("chest") || lowerName.includes("cxr")) {
            effectiveCat = "Chest X-Ray";
          }
        }

        const fd = new FormData();
        let backendCat: string = "Other";
        if (effectiveCat === "Brain MRI") backendCat = "MRI";
        else if (effectiveCat === "Chest X-Ray") backendCat = "X-Ray";
        else if (effectiveCat === "CT Scan") backendCat = "CT";
        else if (effectiveCat === "Lab Report" || effectiveCat === "Diagnostic Report") backendCat = "Lab Report";
        else if (effectiveCat === "Consultation") backendCat = "Medical PDF";
        else if (effectiveCat === "Prescription") backendCat = "Prescription";
        else if (effectiveCat === "Medical Image") backendCat = "MRI";
        else backendCat = String(effectiveCat);

        fd.append("patient_id", pid);
        fd.append("title", f.name);
        fd.append("category", backendCat);
        fd.append("file", f);

        const createdDoc = await apiClient.documents.upload(fd);
        const resolvedRole = (createdDoc.uploader_role || createdDoc.uploaded_by_role || user?.role || "patient").toLowerCase().replace("userrole.", "");
        const appRole: "patient" | "doctor" | "staff" = resolvedRole.includes("patient")
          ? "patient"
          : resolvedRole.includes("doctor")
          ? "doctor"
          : "staff";

        uploadDocument({
          id: createdDoc.document_id,
          patientId: createdDoc.patient_id,
          name: createdDoc.title || createdDoc.original_file_name,
          category: effectiveCat,
          fileType: fileTypeFrom(createdDoc.original_file_name),
          uploadedBy: appRole,
          uploaderRole: resolvedRole,
          uploadedByRole: resolvedRole,
          uploaderName: createdDoc.uploader_name || user?.fullName || (user ? `${user.firstName} ${user.lastName}`.trim() : undefined),
          uploaderUserId: createdDoc.uploaded_by_user_id || createdDoc.uploaded_by || user?.id,
          sizeKb: Math.max(1, Math.round((createdDoc.file_size_bytes || f.size) / 1024)),
        });
        successCount++;
      } catch (err: any) {
        toast.error(`Failed to upload ${f.name}: ${err?.message || "Server error"}`);
      }
    }

    setUploading(false);
    if (successCount > 0) {
      toast.success(successCount > 1 ? `${successCount} documents uploaded successfully` : "Document uploaded successfully");
      setUploadOpen(false);
    }
    if (inputRef.current) inputRef.current.value = "";
  };

  const handleDownload = async (d: MedDocument) => {
    try {
      const blob = await apiClient.documents.getFileBlob(d.id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = d.name || `document-${d.id}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err: any) {
      toast.error("Download failed", { description: err.message || "Failed to download document" });
    }
  };

  const handlePrint = async (d: MedDocument) => {
    try {
      const blob = await apiClient.documents.getFileBlob(d.id);
      const url = URL.createObjectURL(blob);
      const w = window.open(url, "_blank");
      if (w) {
        w.onload = () => {
          w.print();
        };
      }
    } catch (err: any) {
      toast.error("Print failed", { description: err.message || "Failed to print document" });
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Document Center"
        description={isStaffLike ? "Upload and manage patient documents, reports, and medical images." : "All your medical documents, reports, and prescriptions in one place."}
        actions={
          <Dialog open={uploadOpen} onOpenChange={setUploadOpen}>
            <Button onClick={() => setUploadOpen(true)}><UploadCloud className="mr-1.5 h-4 w-4" /> Upload</Button>
            <DialogContent className="max-w-lg">
              <DialogHeader><DialogTitle>Upload document</DialogTitle></DialogHeader>
              <div className="space-y-3">
                {isStaffLike && (
                  <div>
                    <Label>Patient</Label>
                    <Select value={uploadPatient} onValueChange={setUploadPatient}>
                      <SelectTrigger><SelectValue placeholder="Select patient" /></SelectTrigger>
                      <SelectContent>{patients.map((p) => <SelectItem key={p.id} value={p.id}>{p.firstName} {p.lastName} • {p.id}</SelectItem>)}</SelectContent>
                    </Select>
                  </div>
                )}
                <div>
                  <Label>Category</Label>
                  <Select value={uploadCat} onValueChange={(v) => setUploadCat(v as MedDocument["category"])}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>{CATEGORIES.map((c) => <SelectItem key={c} value={c}>{CATEGORY_LABEL[c]}</SelectItem>)}</SelectContent>
                  </Select>
                </div>
                <FileUpload onFileSelect={(f) => doUpload([f])} label="Drag & drop documents here" hint="PDF, JPG, PNG, DICOM — or click to browse" />
                <input ref={inputRef} type="file" multiple accept="image/*,application/pdf" className="hidden" onChange={(e) => doUpload(e.target.files)} />
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => inputRef.current?.click()} disabled={uploading}>Choose file(s)</Button>
                <Button onClick={() => setUploadOpen(false)} disabled={uploading}>{uploading ? "Uploading..." : "Done"}</Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        }
      />

      <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap [&>*]:min-w-0">
        <div className="relative min-w-0 flex-1 sm:min-w-[220px]"><Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" /><Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search documents…" className="pl-9" aria-label="Search documents" /></div>
        {isStaffLike && (
          <Select value={filterPatient} onValueChange={setFilterPatient}>
            <SelectTrigger className="w-full sm:w-44 sm:shrink-0"><SelectValue placeholder="Patient" /></SelectTrigger>
            <SelectContent><SelectItem value="all">All patients</SelectItem>{patients.map((p) => <SelectItem key={p.id} value={p.id}>{p.firstName} {p.lastName}</SelectItem>)}</SelectContent>
          </Select>
        )}
        <Select value={filterCat} onValueChange={setFilterCat}>
          <SelectTrigger className="w-full sm:w-40 sm:shrink-0"><SelectValue placeholder="Category" /></SelectTrigger>
          <SelectContent><SelectItem value="all">All categories</SelectItem>{CATEGORIES.map((c) => <SelectItem key={c} value={c}>{CATEGORY_LABEL[c]}</SelectItem>)}</SelectContent>
        </Select>
        <Select value={sort} onValueChange={(v) => setSort(v as SortKey)}>
          <SelectTrigger className="w-full sm:w-44 sm:shrink-0"><SelectValue placeholder="Sort by" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="date-desc">Newest first</SelectItem>
            <SelectItem value="date-asc">Oldest first</SelectItem>
            <SelectItem value="name-asc">Name (A–Z)</SelectItem>
            <SelectItem value="name-desc">Name (Z–A)</SelectItem>
            <SelectItem value="size-desc">Largest first</SelectItem>
            <SelectItem value="size-asc">Smallest first</SelectItem>
          </SelectContent>
        </Select>
        <div className="flex shrink-0 gap-1 rounded-md border border-border p-0.5">
          <Button size="icon" variant={view === "grid" ? "default" : "ghost"} className="h-8 w-8" aria-label="Grid view" onClick={() => setView("grid")}><LayoutGrid className="h-4 w-4" /></Button>
          <Button size="icon" variant={view === "list" ? "default" : "ghost"} className="h-8 w-8" aria-label="List view" onClick={() => setView("list")}><List className="h-4 w-4" /></Button>
        </div>
      </div>

      {filtered.length === 0 ? (
        <EmptyState title="No documents found" description="Try adjusting your filters or upload a new document." />
      ) : view === "grid" ? (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {filtered.map((d) => {
            const p = getPatient(d.patientId);
            const Icon = d.category === "Medical Image" ? ImgIcon : FileText;
            return (
              <Card key={d.id} className="overflow-hidden">
                <CardContent className="flex flex-col gap-2 p-4">
                  <div className="flex items-start justify-between gap-2">
                    <span className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-primary/10 text-primary"><Icon className="h-5 w-5" /></span>
                    <DocumentBadge status={d.status} />
                  </div>
                  <p className="min-w-0 truncate text-sm font-medium text-foreground" title={d.name}>{d.name}</p>
                  <p className="text-xs text-muted-foreground">{CATEGORY_LABEL[d.category]} • {d.fileType} • {d.sizeKb} KB</p>
                  {isStaffLike && <p className="truncate text-xs text-muted-foreground">{p?.firstName} {p?.lastName}</p>}
                  <p className="text-xs text-muted-foreground">{fmtDate(d.date)}</p>
                  <div className="mt-1 flex flex-wrap gap-1.5">
                    <Button size="sm" variant="outline" className="h-7 px-2" onClick={() => setPreview(d)}><Eye className="mr-1 h-3.5 w-3.5" /> Preview</Button>
                    <Button size="icon" variant="ghost" className="h-7 w-7" aria-label="Download" onClick={() => handleDownload(d)}><Download className="h-3.5 w-3.5" /></Button>
                    <Button size="icon" variant="ghost" className="h-7 w-7" aria-label="Print" onClick={() => handlePrint(d)}><Printer className="h-3.5 w-3.5" /></Button>
                    <ConfirmDelete name={d.name} onConfirm={() => { removeDocument(d.id); toast.success("Document removed"); }} />
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      ) : (
        <Card><CardContent className="p-0"><ul className="divide-y divide-border">
          {filtered.map((d) => {
            const p = getPatient(d.patientId);
            return (
              <li key={d.id} className="grid grid-cols-1 gap-2 p-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,150px)_minmax(0,120px)_minmax(0,120px)_auto] lg:items-center [&>*]:min-w-0">
                <div className="min-w-0"><p className="truncate text-sm font-medium">{d.name}</p><p className="text-xs text-muted-foreground">{CATEGORY_LABEL[d.category]} • {d.fileType} • {d.sizeKb} KB</p></div>
                <span className="truncate text-xs text-muted-foreground">{isStaffLike ? `${p?.firstName ?? ""} ${p?.lastName ?? ""}` : ""}</span>
                <span className="text-xs text-muted-foreground">{fmtDate(d.date)}</span>
                <DocumentBadge status={d.status} />
                <div className="flex flex-wrap gap-1.5 lg:justify-end">
                  <Button size="icon" variant="ghost" className="h-8 w-8" aria-label="Preview" onClick={() => setPreview(d)}><Eye className="h-4 w-4" /></Button>
                  <Button size="icon" variant="ghost" className="h-8 w-8" aria-label="Download" onClick={() => handleDownload(d)}><Download className="h-4 w-4" /></Button>
                  <Button size="icon" variant="ghost" className="h-8 w-8" aria-label="Print" onClick={() => handlePrint(d)}><Printer className="h-4 w-4" /></Button>
                  <ConfirmDelete name={d.name} onConfirm={() => { removeDocument(d.id); toast.success("Document removed"); }} iconOnly />
                </div>
              </li>
            );
          })}
        </ul></CardContent></Card>
      )}

      <Dialog open={!!preview} onOpenChange={(o) => !o && setPreview(null)}>
        <DialogContent className="max-w-md">
          {preview && (
            <>
              <DialogHeader><DialogTitle className="truncate">{preview.name}</DialogTitle></DialogHeader>
              <div className="grid gap-2 text-sm">
                <div className={cn("mb-2 flex max-h-56 items-center justify-center overflow-hidden rounded-lg border border-border bg-muted/30 p-2")}>
                  {loadingPreview ? (
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <Loader2 className="h-4 w-4 animate-spin" /> Loading preview...
                    </div>
                  ) : previewBlobUrl && (preview.category === "Medical Image" || preview.fileType === "JPG" || preview.fileType === "PNG") ? (
                    <img
                      src={previewBlobUrl}
                      alt={preview.name}
                      className="max-h-48 max-w-full object-contain rounded"
                      onError={(e) => {
                        (e.target as HTMLElement).style.display = "none";
                      }}
                    />
                  ) : previewBlobUrl && preview.fileType === "PDF" ? (
                    <iframe
                      src={previewBlobUrl}
                      className="h-48 w-full rounded border border-border"
                      title={preview.name}
                    />
                  ) : (
                    <FileText className="h-10 w-10 text-muted-foreground" />
                  )}
                </div>
                <Row label="Category" value={CATEGORY_LABEL[preview.category]} />
                <Row label="File type" value={preview.fileType} />
                <Row label="Size" value={`${preview.sizeKb} KB`} />
                <Row label="Uploaded by" value={preview.uploadedBy} />
                <Row label="Date" value={fmtDate(preview.date)} />
                <Row label="Status" value={<DocumentBadge status={preview.status} />} />
                {preview.appointmentId && <Row label="Appointment" value={preview.appointmentId} />}
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => handlePrint(preview)}><Printer className="mr-1.5 h-4 w-4" /> Print</Button>
                <Button onClick={() => handleDownload(preview)}><Download className="mr-1.5 h-4 w-4" /> Download</Button>
              </DialogFooter>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-2 border-b border-border/60 py-1.5">
      <span className="text-muted-foreground">{label}</span>
      <span className="min-w-0 truncate font-medium text-foreground">{value}</span>
    </div>
  );
}

function ConfirmDelete({ name, onConfirm, iconOnly }: { name: string; onConfirm: () => void; iconOnly?: boolean }) {
  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>
        {iconOnly ? (
          <Button size="icon" variant="ghost" className="h-8 w-8 text-error" aria-label={`Delete ${name}`}><Trash2 className="h-4 w-4" /></Button>
        ) : (
          <Button size="icon" variant="ghost" className="h-7 w-7 text-error" aria-label={`Delete ${name}`}><Trash2 className="h-3.5 w-3.5" /></Button>
        )}
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Delete document?</AlertDialogTitle>
          <AlertDialogDescription>This will permanently remove "{name}". This action cannot be undone.</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction onClick={onConfirm} className="bg-error text-error-foreground hover:bg-error/90">Delete</AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
