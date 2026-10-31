with open('clinixai-health-flow/src/lib/store/clinix-store.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

target = """              return {
                id: d.document_id,
                patientId: d.patient_id,
                appointmentId: d.consultation_id || undefined,
                name: d.title || d.original_file_name || "Document",
                category: cat,
                fileType: ft,
                uploadedBy: d.uploaded_by?.startsWith("USR-DOC") ? "doctor" : d.uploaded_by?.startsWith("USR-PAT") ? "patient" : "staff",
                date: d.created_at ? d.created_at.split("T")[0] : todayIso(),
                sizeKb: Math.max(1, Math.round((d.file_size_bytes || 1024) / 1024)),
                status: "available" as const,
              };"""

replacement = """              const uRoleRaw = (d.uploader?.role || d.uploader_role || (d.uploaded_by?.startsWith("USR-DOC") ? "doctor" : d.uploaded_by?.startsWith("USR-PAT") ? "patient" : "staff")).toLowerCase();
              const uRole: MedDocument["uploadedBy"] = uRoleRaw === "doctor" ? "doctor" : uRoleRaw === "patient" ? "patient" : "staff";
              const uName = d.uploader?.name || d.uploader_name || (uRole === "doctor" ? "Doctor" : uRole === "patient" ? "Patient" : "Hospital Staff");
              const uId = d.uploader?.user_id || d.uploaded_by_user_id || d.uploaded_by;

              return {
                id: d.document_id,
                patientId: d.patient_id,
                appointmentId: d.consultation_id || undefined,
                name: d.title || d.original_file_name || "Document",
                category: cat,
                fileType: ft,
                uploadedBy: uRole,
                uploaderUserId: uId,
                uploaderName: uName,
                uploaderRole: uRole,
                aiAnalysisId: d.ai_analysis_id || undefined,
                aiAnalysisStatus: d.ai_analysis_status || undefined,
                modality: d.modality || (cat.includes("MRI") ? "Brain MRI" : cat.includes("X-Ray") ? "Chest X-Ray" : cat),
                date: d.created_at ? d.created_at.split("T")[0] : todayIso(),
                sizeKb: Math.max(1, Math.round((d.file_size_bytes || 1024) / 1024)),
                status: "available" as const,
              };"""

content_norm = content.replace("\r\n", "\n")
target_norm = target.replace("\r\n", "\n")
replacement_norm = replacement.replace("\r\n", "\n")

if target_norm in content_norm:
    content_norm = content_norm.replace(target_norm, replacement_norm)
    print("Replaced in clinix-store.tsx successfully")
else:
    print("Failed to find target in clinix-store.tsx")

if "\r\n" in content:
    content_norm = content_norm.replace("\n", "\r\n")

with open('clinixai-health-flow/src/lib/store/clinix-store.tsx', 'w', encoding='utf-8') as f:
    f.write(content_norm)
