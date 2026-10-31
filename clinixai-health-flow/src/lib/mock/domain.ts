// Shared mock domain for Phase 3 — realistic (fictional) healthcare data.
// Consistent IDs cross-referenced across Patient and Staff views.

export type AppointmentStatus =
  | "scheduled" | "confirmed" | "checked-in" | "in-queue"
  | "in-consultation" | "completed" | "cancelled" | "no-show";

export type BillingStatus = "pending" | "paid";
export type AIStatus = "uploaded" | "processing" | "analysis-completed" | "doctor-reviewed" | "finalized";
export type DocumentStatus = "uploaded" | "processing" | "available" | "failed";
export type PaymentMethod = "cash" | "upi" | "card";

export type Doctor = {
  id: string;
  name: string;
  qualification: string;
  specialization: string;
  department: string;
  experienceYears: number;
  languages: string[];
  consultationFee: number;
  nextAvailable: string; // ISO-ish label
  availableSlots: string[]; // e.g. ["09:00","09:30",...]
  photoInitial: string;
  email?: string;
  status?: string;
};

export type Patient = {
  id: string;
  firstName: string;
  lastName: string;
  dob: string; // YYYY-MM-DD
  gender: "Male" | "Female" | "Other";
  mobile: string;
  email: string;
  address: string;
  city: string;
  state: string;
  postal: string;
  bloodGroup: string;
  allergies: string[];
  conditions: string[];
  medications: string[];
  emergency?: { name: string; relationship: string; mobile: string };
  registeredOn: string;
  lastVisit?: string;
};

export type Appointment = {
  id: string;
  patientId: string;
  doctorId: string;
  date: string; // YYYY-MM-DD
  time: string; // HH:MM
  reason: string;
  note?: string;
  status: AppointmentStatus;
  token?: string; // queue token when checked in
  createdAt: string;
};

export type Medication = {
  name: string;
  dosage: string;
  frequency: string;
  duration: string;
  instructions?: string;
};

export type Prescription = {
  id: string;
  consultationId?: string;
  appointmentId: string;
  patientId: string;
  doctorId: string;
  date: string;
  diagnosis: string;
  medications: Medication[];
  notes?: string;
  followUp?: string;
};

export type AIReport = {
  id: string;
  patientId: string;
  appointmentId?: string;
  doctorId?: string;
  imageType: string;
  date: string;
  status: AIStatus;
  prediction?: string;
  confidence?: number;
  explanation?: string;
  doctorNote?: string;
  /* Phase 10 — clinical intelligence */
  modelId?: string;
  modelVersion?: string;
  probabilities?: { label: string; probability: number }[];
  gradcam?: "available" | "unavailable";
  gradcamUrl?: string;
  reviewDecision?: "accepted" | "rejected" | "not-relevant";
  reviewedOn?: string;
  imageUrl?: string;
};

export type Bill = {
  id: string;
  patientId: string;
  appointmentId: string;
  doctorId: string;
  date: string;
  items: { label: string; amount: number }[];
  discount: number;
  status: BillingStatus;
  method?: PaymentMethod;
  reference?: string;
  paidOn?: string;
  receiptId?: string;
};

export type Receipt = {
  id: string;
  billId: string;
  patientId: string;
  doctorId: string;
  appointmentId: string;
  date: string;
  amount: number;
  method: PaymentMethod;
  reference?: string;
};

export type MedDocument = {
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
};

export type QueueEntry = {
  token: string;
  appointmentId: string;
  patientId: string;
  doctorId: string;
  checkInTime: string;
  status: "waiting" | "called" | "in-consultation" | "completed" | "skipped";
  position: number;
  estWaitMin: number;
};

/* ---------- Doctors ---------- */
export const DOCTORS: Doctor[] = [
  { id: "DOC-001", name: "Dr. Meera Krishnan", qualification: "MBBS, MD (Cardiology)", specialization: "Interventional Cardiologist", department: "Cardiology", experienceYears: 14, languages: ["English","Hindi","Tamil"], consultationFee: 800, nextAvailable: "Today, 3:30 PM", availableSlots: ["09:00","09:30","10:00","11:00","15:30","16:00","16:30"], photoInitial: "MK" },
  { id: "DOC-002", name: "Dr. Arjun Menon", qualification: "MBBS, MS (Orthopaedics)", specialization: "Joint Replacement Surgeon", department: "Orthopaedics", experienceYears: 11, languages: ["English","Malayalam","Hindi"], consultationFee: 900, nextAvailable: "Tomorrow, 10:00 AM", availableSlots: ["10:00","10:30","11:30","12:00","14:00","14:30"], photoInitial: "AM" },
  { id: "DOC-003", name: "Dr. Sara D'Souza", qualification: "MBBS, MD (Pulmonology)", specialization: "Respiratory Medicine", department: "Pulmonology", experienceYears: 9, languages: ["English","Konkani","Hindi"], consultationFee: 700, nextAvailable: "Today, 5:00 PM", availableSlots: ["09:30","10:30","11:00","17:00","17:30"], photoInitial: "SD" },
  { id: "DOC-004", name: "Dr. Vikram Rathi", qualification: "MBBS, DM (Neurology)", specialization: "Consultant Neurologist", department: "Neurology", experienceYears: 16, languages: ["English","Hindi","Punjabi"], consultationFee: 1200, nextAvailable: "Thu, 11:00 AM", availableSlots: ["11:00","11:30","12:00","15:00"], photoInitial: "VR" },
  { id: "DOC-005", name: "Dr. Aisha Rahman", qualification: "MBBS, MD (Dermatology)", specialization: "Cosmetic Dermatologist", department: "Dermatology", experienceYears: 8, languages: ["English","Hindi","Urdu"], consultationFee: 650, nextAvailable: "Today, 2:00 PM", availableSlots: ["10:00","10:30","14:00","14:30","15:00","15:30"], photoInitial: "AR" },
  { id: "DOC-006", name: "Dr. Rohan Kapoor", qualification: "MBBS, MD (General Medicine)", specialization: "Internal Medicine", department: "General Medicine", experienceYears: 12, languages: ["English","Hindi"], consultationFee: 500, nextAvailable: "Today, 11:30 AM", availableSlots: ["09:00","09:30","10:00","11:30","12:00","16:00"], photoInitial: "RK" },
  { id: "DOC-007", name: "Dr. Priya Nair", qualification: "MBBS, MS (OBG)", specialization: "Obstetrics & Gynaecology", department: "OBG", experienceYears: 10, languages: ["English","Malayalam","Tamil"], consultationFee: 750, nextAvailable: "Tomorrow, 9:30 AM", availableSlots: ["09:30","10:00","10:30","11:00","15:00"], photoInitial: "PN" },
  { id: "DOC-008", name: "Dr. Kabir Sethi", qualification: "MBBS, MD (Paediatrics)", specialization: "Paediatric Consultant", department: "Paediatrics", experienceYears: 7, languages: ["English","Hindi","Bengali"], consultationFee: 600, nextAvailable: "Today, 4:00 PM", availableSlots: ["10:00","11:00","14:00","16:00","16:30","17:00"], photoInitial: "KS" },
];

/* ---------- Patients ---------- */
export const PATIENTS: Patient[] = [
  { id: "PAT-2026-00124", firstName: "Anaya", lastName: "Reddy", dob: "1994-03-12", gender: "Female", mobile: "+91 98450 12345", email: "anaya.reddy@example.com", address: "12, Jasmine Cross", city: "Bengaluru", state: "Karnataka", postal: "560034", bloodGroup: "O+", allergies: ["Penicillin"], conditions: ["Mild asthma"], medications: ["Salbutamol inhaler (PRN)"], emergency: { name: "Rohit Reddy", relationship: "Spouse", mobile: "+91 98861 22110" }, registeredOn: "2024-11-02", lastVisit: "2026-01-10" },
  { id: "PAT-2026-00125", firstName: "Ishaan", lastName: "Verma", dob: "1988-07-24", gender: "Male", mobile: "+91 99720 44561", email: "ishaan.verma@example.com", address: "204, Neelkanth Apts", city: "Mumbai", state: "Maharashtra", postal: "400058", bloodGroup: "A+", allergies: [], conditions: ["Hypertension"], medications: ["Telmisartan 40mg OD"], emergency: { name: "Kavya Verma", relationship: "Sister", mobile: "+91 98212 44561" }, registeredOn: "2025-02-18", lastVisit: "2026-01-14" },
  { id: "PAT-2026-00126", firstName: "Meher", lastName: "Kapoor", dob: "2001-11-05", gender: "Female", mobile: "+91 98110 90031", email: "meher.k@example.com", address: "B-7, Model Town", city: "Delhi", state: "Delhi", postal: "110009", bloodGroup: "B+", allergies: ["Sulfa drugs"], conditions: [], medications: [], emergency: { name: "Rina Kapoor", relationship: "Mother", mobile: "+91 98110 22203" }, registeredOn: "2025-08-01" },
  { id: "PAT-2026-00127", firstName: "Devan", lastName: "Iyer", dob: "1972-05-19", gender: "Male", mobile: "+91 97390 55810", email: "devan.iyer@example.com", address: "45, MG Road", city: "Kochi", state: "Kerala", postal: "682016", bloodGroup: "AB+", allergies: [], conditions: ["Type-2 diabetes"], medications: ["Metformin 500mg BD"], emergency: { name: "Latha Iyer", relationship: "Spouse", mobile: "+91 97390 22019" }, registeredOn: "2023-06-30", lastVisit: "2026-01-05" },
  { id: "PAT-2026-00128", firstName: "Zara", lastName: "Khan", dob: "1996-01-08", gender: "Female", mobile: "+91 99000 11223", email: "zara.khan@example.com", address: "24, Park Street", city: "Kolkata", state: "West Bengal", postal: "700016", bloodGroup: "O-", allergies: [], conditions: [], medications: [], emergency: { name: "Amir Khan", relationship: "Father", mobile: "+91 99000 22114" }, registeredOn: "2026-01-11" },
  { id: "PAT-2026-00129", firstName: "Rehan", lastName: "Mathew", dob: "2015-09-30", gender: "Male", mobile: "+91 98450 00019", email: "guardian.mathew@example.com", address: "Villa 3, Palm Grove", city: "Chennai", state: "Tamil Nadu", postal: "600041", bloodGroup: "A-", allergies: ["Peanuts"], conditions: [], medications: [], emergency: { name: "Anna Mathew", relationship: "Mother", mobile: "+91 98450 33210" }, registeredOn: "2024-04-14", lastVisit: "2025-12-20" },
];

// Signed-in patient defaults to first patient
export const CURRENT_PATIENT_ID = "PAT-2026-00124";

/* ---------- Appointments ---------- */
const TODAY = new Date();
const iso = (offsetDays: number) => {
  const d = new Date(TODAY); d.setDate(d.getDate() + offsetDays);
  return d.toISOString().slice(0, 10);
};

export const APPOINTMENTS: Appointment[] = [
  { id: "APT-2026-00841", patientId: "PAT-2026-00124", doctorId: "DOC-001", date: iso(2), time: "10:30", reason: "Chest tightness on exertion", status: "confirmed", createdAt: iso(-1) },
  { id: "APT-2026-00842", patientId: "PAT-2026-00124", doctorId: "DOC-006", date: iso(-14), time: "11:00", reason: "Seasonal cough follow-up", status: "completed", createdAt: iso(-16) },
  { id: "APT-2026-00843", patientId: "PAT-2026-00125", doctorId: "DOC-004", date: iso(0), time: "11:30", reason: "Recurrent migraine", status: "checked-in", token: "A-014", createdAt: iso(-2) },
  { id: "APT-2026-00844", patientId: "PAT-2026-00126", doctorId: "DOC-005", date: iso(0), time: "14:00", reason: "Skin allergy review", status: "in-queue", token: "A-015", createdAt: iso(-1) },
  { id: "APT-2026-00845", patientId: "PAT-2026-00127", doctorId: "DOC-006", date: iso(0), time: "09:30", reason: "Diabetes quarterly review", status: "in-consultation", token: "A-012", createdAt: iso(-3) },
  { id: "APT-2026-00846", patientId: "PAT-2026-00128", doctorId: "DOC-007", date: iso(0), time: "10:00", reason: "Routine consultation", status: "checked-in", token: "A-013", createdAt: iso(-1) },
  { id: "APT-2026-00847", patientId: "PAT-2026-00129", doctorId: "DOC-008", date: iso(1), time: "16:00", reason: "Fever & sore throat", status: "scheduled", createdAt: iso(0) },
  { id: "APT-2026-00848", patientId: "PAT-2026-00124", doctorId: "DOC-003", date: iso(-30), time: "09:00", reason: "Asthma review", status: "completed", createdAt: iso(-32) },
  { id: "APT-2026-00849", patientId: "PAT-2026-00125", doctorId: "DOC-002", date: iso(-7), time: "15:00", reason: "Knee pain evaluation", status: "cancelled", createdAt: iso(-9) },
  { id: "APT-2026-00850", patientId: "PAT-2026-00127", doctorId: "DOC-001", date: iso(7), time: "11:00", reason: "Cardiac follow-up", status: "confirmed", createdAt: iso(-1) },
];

/* ---------- Prescriptions ---------- */
export const PRESCRIPTIONS: Prescription[] = [
  { id: "RX-2026-00311", appointmentId: "APT-2026-00842", patientId: "PAT-2026-00124", doctorId: "DOC-006", date: iso(-14), diagnosis: "Acute upper respiratory infection", medications: [
    { name: "Azithromycin 500mg", dosage: "1 tablet", frequency: "Once daily", duration: "3 days", instructions: "After food" },
    { name: "Levocetirizine 5mg", dosage: "1 tablet", frequency: "At bedtime", duration: "5 days" },
    { name: "Paracetamol 650mg", dosage: "1 tablet", frequency: "If fever > 100°F", duration: "SOS" },
  ], notes: "Steam inhalation twice daily. Hydration.", followUp: "Review in 7 days if symptoms persist." },
  { id: "RX-2026-00298", appointmentId: "APT-2026-00848", patientId: "PAT-2026-00124", doctorId: "DOC-003", date: iso(-30), diagnosis: "Mild persistent asthma", medications: [
    { name: "Budesonide + Formoterol inhaler", dosage: "1 puff", frequency: "Twice daily", duration: "Ongoing", instructions: "Rinse mouth after use" },
    { name: "Salbutamol inhaler", dosage: "1–2 puffs", frequency: "As needed", duration: "SOS" },
  ], followUp: "Spirometry in 3 months." },
  { id: "RX-2026-00405", appointmentId: "APT-2026-00845", patientId: "PAT-2026-00127", doctorId: "DOC-006", date: iso(0), diagnosis: "Type-2 diabetes — stable", medications: [
    { name: "Metformin 500mg", dosage: "1 tablet", frequency: "Twice daily", duration: "3 months", instructions: "With meals" },
  ], followUp: "HbA1c and lipid panel in 3 months." },
];

/* ---------- AI Reports ---------- */
export const AI_REPORTS: AIReport[] = [
  { id: "AI-2026-00072", patientId: "PAT-2026-00124", appointmentId: "APT-2026-00848", doctorId: "DOC-003", imageType: "Chest X-ray (PA view)", date: iso(-30), status: "finalized", prediction: "No acute cardiopulmonary abnormality", confidence: 0.94, explanation: "Model attention focused on hilar and cardiac silhouette; no consolidation detected.", doctorNote: "Radiograph is unremarkable. Continue current asthma plan." },
  { id: "AI-2026-00081", patientId: "PAT-2026-00124", appointmentId: "APT-2026-00841", imageType: "12-lead ECG", date: iso(-1), status: "doctor-reviewed", prediction: "Sinus rhythm — no ischaemic changes", confidence: 0.88, explanation: "Attention distributed across leads II, V4–V6; ST-segments within normal limits.", doctorNote: "Awaiting stress test before final impression." },
  { id: "AI-2026-00090", patientId: "PAT-2026-00124", imageType: "Skin lesion photograph", date: iso(-2), status: "analysis-completed", prediction: "Benign nevus", confidence: 0.79, explanation: "Uniform pigmentation and regular borders highlighted by the model." },
];

/* ---------- Bills & Receipts ---------- */
export const BILLS: Bill[] = [
  { id: "BILL-2026-00418", patientId: "PAT-2026-00124", appointmentId: "APT-2026-00842", doctorId: "DOC-006", date: iso(-14), items: [{ label: "Consultation Fee", amount: 500 }, { label: "Nebulisation", amount: 250 }], discount: 0, status: "paid", method: "upi", reference: "UPI/2039182", paidOn: iso(-14), receiptId: "RCT-2026-00418" },
  { id: "BILL-2026-00432", patientId: "PAT-2026-00124", appointmentId: "APT-2026-00848", doctorId: "DOC-003", date: iso(-30), items: [{ label: "Consultation Fee", amount: 700 }, { label: "Spirometry", amount: 600 }], discount: 100, status: "paid", method: "cash", paidOn: iso(-30), receiptId: "RCT-2026-00432" },
  { id: "BILL-2026-00501", patientId: "PAT-2026-00124", appointmentId: "APT-2026-00841", doctorId: "DOC-001", date: iso(-1), items: [{ label: "Consultation Fee", amount: 800 }, { label: "ECG", amount: 350 }], discount: 0, status: "pending" },
  { id: "BILL-2026-00502", patientId: "PAT-2026-00127", appointmentId: "APT-2026-00845", doctorId: "DOC-006", date: iso(0), items: [{ label: "Consultation Fee", amount: 500 }, { label: "HbA1c panel", amount: 900 }], discount: 50, status: "pending" },
  { id: "BILL-2026-00503", patientId: "PAT-2026-00125", appointmentId: "APT-2026-00843", doctorId: "DOC-004", date: iso(0), items: [{ label: "Consultation Fee", amount: 1200 }], discount: 0, status: "pending" },
];

export const RECEIPTS: Receipt[] = [
  { id: "RCT-2026-00418", billId: "BILL-2026-00418", patientId: "PAT-2026-00124", doctorId: "DOC-006", appointmentId: "APT-2026-00842", date: iso(-14), amount: 750, method: "upi", reference: "UPI/2039182" },
  { id: "RCT-2026-00432", billId: "BILL-2026-00432", patientId: "PAT-2026-00124", doctorId: "DOC-003", appointmentId: "APT-2026-00848", date: iso(-30), amount: 1200, method: "cash" },
];

/* ---------- Documents ---------- */
export const DOCUMENTS: MedDocument[] = [
  { id: "DOC-2026-01001", patientId: "PAT-2026-00124", appointmentId: "APT-2026-00842", name: "Consultation summary — Dr. Kapoor.pdf", category: "Consultation", fileType: "PDF", uploadedBy: "doctor", date: iso(-14), status: "available", sizeKb: 214 },
  { id: "DOC-2026-01002", patientId: "PAT-2026-00124", appointmentId: "APT-2026-00848", name: "Chest X-ray — PA view.jpg", category: "Medical Image", fileType: "JPG", uploadedBy: "staff", date: iso(-30), status: "available", sizeKb: 1804 },
  { id: "DOC-2026-01003", patientId: "PAT-2026-00124", name: "CBC — Lab report.pdf", category: "Diagnostic Report", fileType: "PDF", uploadedBy: "patient", date: iso(-8), status: "available", sizeKb: 342 },
  { id: "DOC-2026-01004", patientId: "PAT-2026-00124", appointmentId: "APT-2026-00841", name: "ECG trace.pdf", category: "Diagnostic Report", fileType: "PDF", uploadedBy: "staff", date: iso(-1), status: "processing", sizeKb: 512 },
];

/* ---------- Queue ---------- */
export const QUEUE: QueueEntry[] = [
  { token: "A-012", appointmentId: "APT-2026-00845", patientId: "PAT-2026-00127", doctorId: "DOC-006", checkInTime: "09:20", status: "in-consultation", position: 0, estWaitMin: 0 },
  { token: "A-013", appointmentId: "APT-2026-00846", patientId: "PAT-2026-00128", doctorId: "DOC-007", checkInTime: "09:40", status: "waiting", position: 1, estWaitMin: 10 },
  { token: "A-014", appointmentId: "APT-2026-00843", patientId: "PAT-2026-00125", doctorId: "DOC-004", checkInTime: "10:55", status: "waiting", position: 2, estWaitMin: 25 },
  { token: "A-015", appointmentId: "APT-2026-00844", patientId: "PAT-2026-00126", doctorId: "DOC-005", checkInTime: "13:35", status: "waiting", position: 3, estWaitMin: 40 },
];

/* ---------- Lookups ---------- */
export const getDoctor = (id: string) => DOCTORS.find((d) => d.id === id);
export const getPatient = (id: string) => PATIENTS.find((p) => p.id === id);
export const getAppointment = (id: string) => APPOINTMENTS.find((a) => a.id === id);
export const getBill = (id: string) => BILLS.find((b) => b.id === id);
export const getReceipt = (id: string) => RECEIPTS.find((r) => r.id === id);
export const getPrescription = (id: string) => PRESCRIPTIONS.find((p) => p.id === id);
export const getAIReport = (id: string) => AI_REPORTS.find((a) => a.id === id);

export const patientAppointments = (pid: string) => APPOINTMENTS.filter((a) => a.patientId === pid);
export const patientBills = (pid: string) => BILLS.filter((b) => b.patientId === pid);
export const patientPrescriptions = (pid: string) => PRESCRIPTIONS.filter((p) => p.patientId === pid);
export const patientAIReports = (pid: string) => AI_REPORTS.filter((a) => a.patientId === pid);
export const patientDocuments = (pid: string) => DOCUMENTS.filter((d) => d.patientId === pid);

export const billTotal = (b: Bill) => b.items.reduce((s, i) => s + i.amount, 0) - b.discount;
export const billSubtotal = (b: Bill) => b.items.reduce((s, i) => s + i.amount, 0);

export const inr = (n: number) => `₹${n.toLocaleString("en-IN")}`;

export function ageFromDob(dob: string) {
  const d = new Date(dob), n = new Date();
  let a = n.getFullYear() - d.getFullYear();
  const m = n.getMonth() - d.getMonth();
  if (m < 0 || (m === 0 && n.getDate() < d.getDate())) a--;
  return a;
}

export function fmtDate(d: string) {
  if (!d) return "—";
  const date = d.includes("T") || d.includes(" ") ? new Date(d) : new Date(d + "T00:00:00");
  if (isNaN(date.getTime())) {
    return "Review date unavailable";
  }
  return date.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

/* ---------- Timeline (derived) ---------- */
export type TimelineEvent = {
  id: string;
  kind: "registration" | "appointment" | "consultation" | "report" | "image" | "ai" | "prescription" | "billing" | "follow-up";
  title: string;
  description?: string;
  date: string;
  ref?: { type: string; id: string };
};

export function patientTimeline(pid: string): TimelineEvent[] {
  const events: TimelineEvent[] = [];
  const patient = getPatient(pid);
  if (patient) events.push({ id: `reg-${pid}`, kind: "registration", title: "Patient registered", description: `Welcome, ${patient.firstName}`, date: patient.registeredOn });
  for (const a of patientAppointments(pid)) {
    const doc = getDoctor(a.doctorId);
    events.push({ id: `apt-${a.id}`, kind: "appointment", title: `Appointment ${a.status === "completed" ? "completed" : "booked"} — ${doc?.name ?? "Doctor"}`, description: `${doc?.department} • ${a.time}`, date: a.date, ref: { type: "appointment", id: a.id } });
  }
  for (const p of patientPrescriptions(pid)) events.push({ id: `rx-${p.id}`, kind: "prescription", title: "Prescription issued", description: p.diagnosis, date: p.date, ref: { type: "prescription", id: p.id } });
  for (const ai of patientAIReports(pid)) events.push({ id: `ai-${ai.id}`, kind: "ai", title: `AI analysis — ${ai.imageType}`, description: ai.prediction, date: ai.date, ref: { type: "ai-report", id: ai.id } });
  for (const b of patientBills(pid)) events.push({ id: `bill-${b.id}`, kind: "billing", title: `Bill ${b.status === "paid" ? "paid" : "generated"}`, description: `${inr(billTotal(b))} • ${b.id}`, date: b.date, ref: { type: "bill", id: b.id } });
  for (const d of patientDocuments(pid)) events.push({ id: `doc-${d.id}`, kind: d.category === "Medical Image" ? "image" : "report", title: `${d.category} uploaded`, description: d.name, date: d.date });
  return events.sort((a, b) => (a.date < b.date ? 1 : -1));
}

/* ---------- ID generators ---------- */
export function nextPatientId() {
  const nums = PATIENTS.map((p) => parseInt(p.id.split("-").at(-1)!, 10));
  const next = Math.max(...nums, 0) + 1;
  return `PAT-2026-${String(next).padStart(5, "0")}`;
}
export function nextAppointmentId() {
  const nums = APPOINTMENTS.map((a) => parseInt(a.id.split("-").at(-1)!, 10));
  return `APT-2026-${String(Math.max(...nums, 0) + 1).padStart(5, "0")}`;
}
export function nextBillId() {
  const nums = BILLS.map((b) => parseInt(b.id.split("-").at(-1)!, 10));
  return `BILL-2026-${String(Math.max(...nums, 0) + 1).padStart(5, "0")}`;
}
export function nextReceiptId(billId: string) {
  return `RCT-${billId.slice(5)}`;
}

/* =================================================================
 * Phase 5 — Hospital Admin domain extensions
 * ================================================================= */

export type AccountStatus = "active" | "inactive";
export type Availability = "available" | "busy" | "off-duty";
type AdminRole = "admin" | "doctor" | "staff" | "patient";

export type Staff = {
  id: string;
  firstName: string;
  lastName: string;
  email: string;
  mobile: string;
  gender: "Male" | "Female" | "Other";
  department: string;
  desk: string;
  status: AccountStatus;
  lastActive: string;
  photoInitial: string;
};

export type Department = {
  id: string;
  name: string;
  code: string;
  description: string;
  status: AccountStatus;
};

export type DoctorSchedule = {
  doctorId: string;
  workingDays: ("Mon" | "Tue" | "Wed" | "Thu" | "Fri" | "Sat" | "Sun")[];
  startTime: string;
  endTime: string;
  slotMinutes: number;
  breaks: { from: string; to: string; label: string }[];
  unavailableDates: string[];
};

export type DoctorMeta = {
  doctorId: string;
  status: AccountStatus;
  availability: Availability;
  email: string;
  mobile: string;
  gender: "Male" | "Female" | "Other";
};

export type ActivityLog = {
  id: string;
  timestamp: string;
  user: string;
  role: AdminRole | "system";
  action: string;
  entity: string;
  entityId?: string;
  status: "success" | "warning" | "failure";
};

export const DEPARTMENTS: Department[] = [
  { id: "DEP-01", name: "General Medicine", code: "GM", description: "Primary care & internal medicine consultations.", status: "active" },
  { id: "DEP-02", name: "Cardiology", code: "CARD", description: "Heart & cardiovascular care including ECG and echo.", status: "active" },
  { id: "DEP-03", name: "Orthopaedics", code: "ORTH", description: "Bone, joint & musculoskeletal specialty.", status: "active" },
  { id: "DEP-04", name: "Neurology", code: "NEURO", description: "Nervous system & neurological disorders.", status: "active" },
  { id: "DEP-05", name: "Dermatology", code: "DERM", description: "Skin, hair, and cosmetic dermatology.", status: "active" },
  { id: "DEP-06", name: "Pulmonology", code: "PULM", description: "Respiratory medicine & pulmonary function.", status: "active" },
  { id: "DEP-07", name: "OBG", code: "OBG", description: "Obstetrics & Gynaecology.", status: "active" },
  { id: "DEP-08", name: "Paediatrics", code: "PAED", description: "Care for infants, children & adolescents.", status: "active" },
  { id: "DEP-09", name: "Radiology", code: "RAD", description: "Diagnostic imaging including X-ray, CT, MRI.", status: "inactive" },
];

export const STAFF: Staff[] = [
  { id: "STF-2026-00042", firstName: "Nikhil", lastName: "Menon", email: "nikhil.m@clinixai.in", mobile: "+91 98450 77821", gender: "Male", department: "Reception", desk: "Front Desk A", status: "active", lastActive: "2m ago", photoInitial: "NM" },
  { id: "STF-2026-00043", firstName: "Fatima", lastName: "Sheikh", email: "fatima.s@clinixai.in", mobile: "+91 99720 33410", gender: "Female", department: "Billing", desk: "Counter 1", status: "active", lastActive: "12m ago", photoInitial: "FS" },
  { id: "STF-2026-00044", firstName: "Rahul", lastName: "Bose", email: "rahul.b@clinixai.in", mobile: "+91 98110 22019", gender: "Male", department: "Reception", desk: "Front Desk B", status: "active", lastActive: "1h ago", photoInitial: "RB" },
  { id: "STF-2026-00045", firstName: "Sneha", lastName: "Patil", email: "sneha.p@clinixai.in", mobile: "+91 98212 55110", gender: "Female", department: "Records", desk: "Medical Records", status: "active", lastActive: "35m ago", photoInitial: "SP" },
  { id: "STF-2026-00046", firstName: "Aarav", lastName: "Gupta", email: "aarav.g@clinixai.in", mobile: "+91 97390 11009", gender: "Male", department: "Billing", desk: "Counter 2", status: "inactive", lastActive: "3d ago", photoInitial: "AG" },
  { id: "STF-2026-00047", firstName: "Divya", lastName: "Kulkarni", email: "divya.k@clinixai.in", mobile: "+91 99000 88771", gender: "Female", department: "Reception", desk: "Front Desk C", status: "active", lastActive: "8m ago", photoInitial: "DK" },
];

export const DOCTOR_META: DoctorMeta[] = DOCTORS.map((d, i) => ({
  doctorId: d.id,
  status: i === 3 ? "inactive" : "active",
  availability: (["available", "busy", "available", "off-duty", "available", "busy", "available", "available"][i] ?? "available") as Availability,
  email: `${d.name.toLowerCase().replace(/[^a-z]+/g, ".").replace(/^\.|\.$/g, "")}@clinixai.in`,
  mobile: `+91 984${String(50000 + i * 137).padStart(5, "0")}`,
  gender: (["Female", "Male", "Female", "Male", "Female", "Male", "Female", "Male"][i] as "Male" | "Female"),
}));
export const getDoctorMeta = (id: string) => DOCTOR_META.find((m) => m.doctorId === id);

export const DOCTOR_SCHEDULES: DoctorSchedule[] = DOCTORS.map((d) => ({
  doctorId: d.id,
  workingDays: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
  startTime: "09:00",
  endTime: "17:00",
  slotMinutes: 30,
  breaks: [{ from: "13:00", to: "14:00", label: "Lunch" }],
  unavailableDates: [],
}));
export const getDoctorSchedule = (id: string) => DOCTOR_SCHEDULES.find((s) => s.doctorId === id);

export type Consultation = {
  id: string;
  appointmentId: string;
  patientId: string;
  doctorId: string;
  date: string;
  status: "not-started" | "in-progress" | "completed";
  startedAt?: string;
  completedAt?: string;
  prescriptionId?: string;
  aiUsed: boolean;
  followUpRecommended: boolean;
  billingReady: boolean;
};

export const CONSULTATIONS: Consultation[] = APPOINTMENTS.map((a, i) => {
  const status: Consultation["status"] =
    a.status === "completed" ? "completed" :
    a.status === "in-consultation" ? "in-progress" : "not-started";
  const rx = PRESCRIPTIONS.find((p) => p.appointmentId === a.id);
  const ai = AI_REPORTS.find((r) => r.appointmentId === a.id);
  return {
    id: `CON-2026-${String(300 + i).padStart(5, "0")}`,
    appointmentId: a.id,
    patientId: a.patientId,
    doctorId: a.doctorId,
    date: a.date,
    status,
    startedAt: status !== "not-started" ? a.time : undefined,
    completedAt: status === "completed" ? a.time : undefined,
    prescriptionId: rx?.id,
    aiUsed: !!ai,
    followUpRecommended: !!rx?.followUp,
    billingReady: status === "completed",
  };
});
export const getConsultation = (id: string) => CONSULTATIONS.find((c) => c.id === id);

const _now = new Date();
const _minsAgo = (m: number) => new Date(_now.getTime() - m * 60_000).toISOString();

export const ACTIVITY_LOG: ActivityLog[] = [
  { id: "LOG-10001", timestamp: _minsAgo(2),   user: "Fatima Sheikh",       role: "staff",   action: "Payment recorded",       entity: "Bill",         entityId: "BILL-2026-00418", status: "success" },
  { id: "LOG-10002", timestamp: _minsAgo(6),   user: "Dr. Rohan Kapoor",    role: "doctor",  action: "Consultation completed", entity: "Consultation", entityId: "CON-2026-00304", status: "success" },
  { id: "LOG-10003", timestamp: _minsAgo(11),  user: "Nikhil Menon",        role: "staff",   action: "Patient checked in",     entity: "Appointment",  entityId: "APT-2026-00846", status: "success" },
  { id: "LOG-10004", timestamp: _minsAgo(18),  user: "System",              role: "system",  action: "AI analysis completed",  entity: "AI Report",    entityId: "AI-2026-00081",  status: "success" },
  { id: "LOG-10005", timestamp: _minsAgo(24),  user: "Dr. Vikram Rathi",    role: "doctor",  action: "Prescription finalized", entity: "Prescription", entityId: "RX-2026-00405",  status: "success" },
  { id: "LOG-10006", timestamp: _minsAgo(37),  user: "Anaya Reddy",         role: "patient", action: "Appointment created",    entity: "Appointment",  entityId: "APT-2026-00841", status: "success" },
  { id: "LOG-10007", timestamp: _minsAgo(52),  user: "Sneha Patil",         role: "staff",   action: "Patient registered",     entity: "Patient",      entityId: "PAT-2026-00128", status: "success" },
  { id: "LOG-10008", timestamp: _minsAgo(68),  user: "Admin",               role: "admin",   action: "Doctor added",           entity: "Doctor",       entityId: "DOC-008",        status: "success" },
  { id: "LOG-10009", timestamp: _minsAgo(90),  user: "Admin",               role: "admin",   action: "Staff added",            entity: "Staff",        entityId: "STF-2026-00047", status: "success" },
  { id: "LOG-10010", timestamp: _minsAgo(120), user: "Dr. Sara D'Souza",    role: "doctor",  action: "AI analysis reviewed",   entity: "AI Report",    entityId: "AI-2026-00072",  status: "success" },
  { id: "LOG-10011", timestamp: _minsAgo(155), user: "System",              role: "system",  action: "AI analysis failed",     entity: "AI Report",    entityId: "AI-2026-00088",  status: "failure" },
  { id: "LOG-10012", timestamp: _minsAgo(210), user: "Fatima Sheikh",       role: "staff",   action: "Bill generated",         entity: "Bill",         entityId: "BILL-2026-00503", status: "success" },
  { id: "LOG-10013", timestamp: _minsAgo(280), user: "Admin",               role: "admin",   action: "Account deactivated",    entity: "Doctor",       entityId: "DOC-004",        status: "warning" },
  { id: "LOG-10014", timestamp: _minsAgo(360), user: "Dr. Meera Krishnan",  role: "doctor",  action: "User login",             entity: "Session",                                  status: "success" },
  { id: "LOG-10015", timestamp: _minsAgo(720), user: "Admin",               role: "admin",   action: "User login",             entity: "Session",                                  status: "success" },
];

export const HOSPITAL_INFO = {
  name: "CliniXAI Multispeciality Hospital",
  logoInitial: "C",
  contact: "+91 80 4560 9800",
  email: "reception@clinixai.in",
  address: "142, Residency Road, Ashok Nagar",
  city: "Bengaluru",
  state: "Karnataka",
  postal: "560025",
  workingDays: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"] as string[],
  openTime: "08:00",
  closeTime: "20:00",
  defaultSlotMinutes: 30,
  bookingWindowDays: 30,
  receiptPrefix: "RCT-2026-",
  currency: "INR",
  location: { lat: 12.9698, lng: 77.6006 },
};

export const todayIso = () => new Date().toISOString().slice(0, 10);

export function adminOpsSummary() {
  const today = todayIso();
  const todays = APPOINTMENTS.filter((a) => a.date === today);
  const checkedIn = todays.filter((a) => ["checked-in", "in-queue", "in-consultation"].includes(a.status));
  const waiting = todays.filter((a) => a.status === "checked-in" || a.status === "in-queue");
  const inConsult = todays.filter((a) => a.status === "in-consultation");
  const completedToday = todays.filter((a) => a.status === "completed");
  const activeDoctors = DOCTOR_META.filter((m) => m.status === "active");
  const availableDocs = activeDoctors.filter((m) => m.availability === "available");
  const busyDocs = activeDoctors.filter((m) => m.availability === "busy");
  const pendingBills = BILLS.filter((b) => b.status === "pending");
  const paidToday = BILLS.filter((b) => b.status === "paid" && b.paidOn === today);
  const aiToday = AI_REPORTS.filter((r) => r.date === today);
  const aiPending = AI_REPORTS.filter((r) => r.status === "analysis-completed");
  const revenueToday = paidToday.reduce((s, b) => s + billTotal(b), 0);
  return {
    todaysAppointments: todays.length,
    checkedIn: checkedIn.length,
    waiting: waiting.length,
    activeDoctors: activeDoctors.length,
    availableDocs: availableDocs.length,
    busyDocs: busyDocs.length,
    completedConsults: completedToday.length,
    inConsult: inConsult.length,
    pendingBills: pendingBills.length,
    revenueToday,
    aiToday: aiToday.length,
    aiPending: aiPending.length,
  };
}

export function revenueByMonth() {
  const buckets = new Map<string, number>();
  const paid = BILLS.filter((b) => b.status === "paid" && b.paidOn);
  for (const b of paid) {
    const key = new Date(b.paidOn + "T00:00:00").toLocaleDateString("en-IN", { month: "short" });
    buckets.set(key, (buckets.get(key) ?? 0) + billTotal(b));
  }
  return Array.from(buckets, ([label, value]) => ({ label, value }));
}

export function revenueByDepartment() {
  const map = new Map<string, number>();
  for (const b of BILLS.filter((b) => b.status === "paid")) {
    const d = getDoctor(b.doctorId);
    const dept = d?.department ?? "Other";
    map.set(dept, (map.get(dept) ?? 0) + billTotal(b));
  }
  return Array.from(map, ([label, value]) => ({ label, value }));
}

export function paymentMethodMix() {
  const map = new Map<string, number>();
  for (const b of BILLS.filter((b) => b.status === "paid")) {
    const m = b.method ?? "cash";
    map.set(m, (map.get(m) ?? 0) + 1);
  }
  return Array.from(map, ([label, value]) => ({ label, value }));
}

export function appointmentsByDept() {
  const map = new Map<string, number>();
  for (const a of APPOINTMENTS) {
    const d = getDoctor(a.doctorId);
    const dept = d?.department ?? "Other";
    map.set(dept, (map.get(dept) ?? 0) + 1);
  }
  return Array.from(map, ([label, value]) => ({ label, value }));
}

export function appointmentsByDoctor() {
  const map = new Map<string, number>();
  for (const a of APPOINTMENTS) {
    const d = getDoctor(a.doctorId);
    if (!d) continue;
    map.set(d.name.replace("Dr. ", ""), (map.get(d.name.replace("Dr. ", "")) ?? 0) + 1);
  }
  return Array.from(map, ([label, value]) => ({ label, value }));
}

export function apptStatusMix() {
  const map = new Map<string, number>();
  for (const a of APPOINTMENTS) map.set(a.status, (map.get(a.status) ?? 0) + 1);
  return Array.from(map, ([label, value]) => ({ label, value }));
}

export function aiUsageByDept() {
  const map = new Map<string, number>();
  for (const r of AI_REPORTS) {
    const d = r.doctorId ? getDoctor(r.doctorId) : undefined;
    const dept = d?.department ?? "Unassigned";
    map.set(dept, (map.get(dept) ?? 0) + 1);
  }
  return Array.from(map, ([label, value]) => ({ label, value }));
}

export function doctorsInDept(dept: string) { return DOCTORS.filter((d) => d.department === dept); }
export function apptsForDoctor(id: string) { return APPOINTMENTS.filter((a) => a.doctorId === id); }
export function apptsForDept(dept: string) {
  const ids = new Set(doctorsInDept(dept).map((d) => d.id));
  return APPOINTMENTS.filter((a) => ids.has(a.doctorId));
}

export function fmtDateTime(iso: string) {
  const d = new Date(iso);
  return d.toLocaleString("en-IN", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

