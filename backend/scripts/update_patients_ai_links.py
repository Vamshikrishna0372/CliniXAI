with open("clinixai-health-flow/src/routes/app.patients.$id.tsx", "r", encoding="utf-8") as f:
    text = f.read()

target1 = """                        search={{
                          patient_id: selectedDocument.patient_id,
                          document_id: selectedDocument.document_id,
                          appointment_id: selectedDocument.appointment_id || undefined,
                          medical_record_id: selectedDocument.medical_record_id || undefined,
                        }}"""

replacement1 = """                        search={{
                          patient_id: selectedDocument.patient_id,
                          document_id: selectedDocument.document_id,
                          appointment_id: selectedDocument.appointment_id || undefined,
                          medical_record_id: selectedDocument.medical_record_id || undefined,
                          modality: isBrainMri(selectedDocument) ? "BRAIN_MRI" : undefined,
                        }}"""

target2 = """                                search={{
                                  document_id: docId,
                                  patient_id: doc.patient_id,
                                  appointment_id: doc.appointment_id || undefined,
                                  medical_record_id: doc.medical_record_id || undefined,
                                }}"""

replacement2 = """                                search={{
                                  document_id: docId,
                                  patient_id: doc.patient_id,
                                  appointment_id: doc.appointment_id || undefined,
                                  medical_record_id: doc.medical_record_id || undefined,
                                  modality: isBrainMri(doc) ? "BRAIN_MRI" : undefined,
                                }}"""

if target1 in text:
    print("target1 found")
    text = text.replace(target1, replacement1)
else:
    print("target1 NOT found")

if target2 in text:
    print("target2 found")
    text = text.replace(target2, replacement2)
else:
    print("target2 NOT found")

with open("clinixai-health-flow/src/routes/app.patients.$id.tsx", "w", encoding="utf-8", newline="") as f:
    f.write(text)

print("Done")

