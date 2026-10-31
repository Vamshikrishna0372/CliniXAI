with open("clinixai-health-flow/src/routes/app.ai-analysis.tsx", "r", encoding="utf-8") as f:
    text = f.read()

# 1. Update AIAnalysisSearchParams and validateSearch
search_old = """interface AIAnalysisSearchParams {
  document_id?: string;
  documentId?: string;
  patient_id?: string;
  patientId?: string;
  appointment_id?: string;
  appointmentId?: string;
  medical_record_id?: string;
  medicalRecordId?: string;
  recordId?: string;
  record_id?: string;
}

export const Route = createFileRoute("/app/ai-analysis")({
  head: () => ({ meta: [{ title: "AI Analysis — CliniXAI" }, { name: "robots", content: "noindex" }] }),
  validateSearch: (search: Record<string, unknown>): AIAnalysisSearchParams => ({
    document_id: typeof search.document_id === "string" ? search.document_id : typeof search.documentId === "string" ? search.documentId : undefined,
    patient_id: typeof search.patient_id === "string" ? search.patient_id : typeof search.patientId === "string" ? search.patientId : undefined,
    appointment_id: typeof search.appointment_id === "string" ? search.appointment_id : typeof search.appointmentId === "string" ? search.appointmentId : undefined,
    medical_record_id: typeof search.medical_record_id === "string" ? search.medical_record_id : typeof search.medicalRecordId === "string" ? search.medicalRecordId : undefined,
    recordId: typeof search.recordId === "string" ? search.recordId : undefined,
    record_id: typeof search.record_id === "string" ? search.record_id : undefined,
  }),
  component: AIAnalysisPage,
});"""

search_new = """interface AIAnalysisSearchParams {
  document_id?: string;
  documentId?: string;
  patient_id?: string;
  patientId?: string;
  appointment_id?: string;
  appointmentId?: string;
  medical_record_id?: string;
  medicalRecordId?: string;
  recordId?: string;
  record_id?: string;
  modality?: string;
}

export const Route = createFileRoute("/app/ai-analysis")({
  head: () => ({ meta: [{ title: "AI Analysis — CliniXAI" }, { name: "robots", content: "noindex" }] }),
  validateSearch: (search: Record<string, unknown>): AIAnalysisSearchParams => ({
    document_id: typeof search.document_id === "string" ? search.document_id : typeof search.documentId === "string" ? search.documentId : undefined,
    patient_id: typeof search.patient_id === "string" ? search.patient_id : typeof search.patientId === "string" ? search.patientId : undefined,
    appointment_id: typeof search.appointment_id === "string" ? search.appointment_id : typeof search.appointmentId === "string" ? search.appointmentId : undefined,
    medical_record_id: typeof search.medical_record_id === "string" ? search.medical_record_id : typeof search.medicalRecordId === "string" ? search.medicalRecordId : undefined,
    recordId: typeof search.recordId === "string" ? search.recordId : undefined,
    record_id: typeof search.record_id === "string" ? search.record_id : undefined,
    modality: typeof search.modality === "string" ? search.modality : undefined,
  }),
  component: AIAnalysisPage,
});"""

text = text.replace(search_old, search_new)

# 2. Update moduleType resolution
mod_old = """      const cat = String(existingDoc.category || "").toLowerCase();
      const title = String(existingDoc.title || "").toLowerCase();
      let moduleType = "BRAIN_MRI";
      if (cat.includes("chest") || cat.includes("xray") || title.includes("chest")) moduleType = "CHEST_XRAY";
      else if (cat.includes("skin") || cat.includes("derm")) moduleType = "SKIN_DERMOSCOPY";
      else if (cat.includes("retin") || cat.includes("fundus")) moduleType = "RETINAL_FUNDUS";
      else if (cat.includes("bone")) moduleType = "BONE_XRAY";"""

mod_new = """      const cat = String(existingDoc.category || "").toLowerCase();
      const title = String(existingDoc.title || "").toLowerCase();
      let moduleType = routeSearch.modality || "BRAIN_MRI";
      if (!routeSearch.modality) {
        if (cat.includes("brain") || cat.includes("mri") || title.includes("brain") || title.includes("mri")) moduleType = "BRAIN_MRI";
        else if (cat.includes("chest") || cat.includes("xray") || cat.includes("x-ray") || title.includes("chest") || title.includes("x-ray")) moduleType = "CHEST_XRAY";
        else if (cat.includes("skin") || cat.includes("derm")) moduleType = "SKIN_DERMOSCOPY";
        else if (cat.includes("retin") || cat.includes("fundus")) moduleType = "RETINAL_FUNDUS";
        else if (cat.includes("bone")) moduleType = "BONE_XRAY";
      }"""

text = text.replace(mod_old, mod_new)

with open("clinixai-health-flow/src/routes/app.ai-analysis.tsx", "w", encoding="utf-8", newline="") as f:
    f.write(text)

print("Updated app.ai-analysis.tsx successfully")

