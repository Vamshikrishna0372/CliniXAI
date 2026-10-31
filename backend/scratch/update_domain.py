with open('clinixai-health-flow/src/lib/mock/domain.ts', 'r', encoding='utf-8') as f:
    content = f.read()

target = """export type MedDocument = {
  id: string;
  patientId: string;
  appointmentId?: string;
  name: string;
  category: "Consultation" | "Diagnostic Report" | "Medical Image" | "Prescription" | "AI Report" | "Brain MRI" | "Chest X-Ray" | "CT Scan" | "Lab Report" | "MRI" | "X-Ray" | "Other" | string;
  fileType: "PDF" | "JPG" | "PNG" | "DICOM";
  uploadedBy: "patient" | "staff" | "doctor";
  date: string;
  status: DocumentStatus;
  sizeKb: number;
};"""

replacement = """export type MedDocument = {
  id: string;
  patientId: string;
  appointmentId?: string;
  name: string;
  category: "Consultation" | "Diagnostic Report" | "Medical Image" | "Prescription" | "AI Report" | "Brain MRI" | "Chest X-Ray" | "CT Scan" | "Lab Report" | "MRI" | "X-Ray" | "Other" | string;
  fileType: "PDF" | "JPG" | "PNG" | "DICOM";
  uploadedBy: "patient" | "staff" | "doctor";
  date: string;
  status: DocumentStatus;
  sizeKb: number;
  uploaderUserId?: string;
  uploaderName?: string;
  uploaderRole?: "patient" | "staff" | "doctor" | string;
  aiAnalysisId?: string;
  aiAnalysisStatus?: string;
  modality?: string;
};"""

target_fmt = """export function fmtDate(d: string) {
  return new Date(d + "T00:00:00").toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}"""

replacement_fmt = """export function fmtDate(d: string) {
  if (!d) return "—";
  const date = d.includes("T") || d.includes(" ") ? new Date(d) : new Date(d + "T00:00:00");
  if (isNaN(date.getTime())) {
    return "Review date unavailable";
  }
  return date.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}"""

# Normalize CRLF
content_norm = content.replace("\r\n", "\n")
target_norm = target.replace("\r\n", "\n")
replacement_norm = replacement.replace("\r\n", "\n")
target_fmt_norm = target_fmt.replace("\r\n", "\n")
replacement_fmt_norm = replacement_fmt.replace("\r\n", "\n")

if target_norm in content_norm:
    content_norm = content_norm.replace(target_norm, replacement_norm)
    print("Replaced MedDocument successfully")
else:
    print("Failed to find target MedDocument")

if target_fmt_norm in content_norm:
    content_norm = content_norm.replace(target_fmt_norm, replacement_fmt_norm)
    print("Replaced fmtDate successfully")
else:
    print("Failed to find target fmtDate")

# Write back preserving original line endings if CRLF was present
if "\r\n" in content:
    content_norm = content_norm.replace("\n", "\r\n")

with open('clinixai-health-flow/src/lib/mock/domain.ts', 'w', encoding='utf-8') as f:
    f.write(content_norm)
