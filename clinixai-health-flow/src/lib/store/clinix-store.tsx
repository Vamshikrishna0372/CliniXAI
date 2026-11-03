/**
 * CliniXAI shared mock domain store.
 *
 * Single source of truth for all mutable frontend state across every role.
 * Screens must read/write through `useClinix()` instead of importing the raw
 * arrays from `@/lib/mock/domain` so that a mutation on one screen propagates
 * everywhere (dashboards, queues, billing, timeline, notifications).
 *
 * When FastAPI is wired in, each action below maps 1:1 to an API call; the
 * shape of the state is intentionally close to the future API contract.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { apiClient, getStoredTokens, getApiBaseUrl, getWebSocketUrl } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import {
  AI_REPORTS, APPOINTMENTS, BILLS, CONSULTATIONS, DEPARTMENTS, DOCTORS,
  DOCTOR_META, DOCUMENTS, PATIENTS, PRESCRIPTIONS, QUEUE, RECEIPTS, STAFF,
  billTotal, getDoctor, inr, nextAppointmentId, nextBillId, nextPatientId, nextReceiptId,
  todayIso,
  type ActivityLog, type AIReport, type Appointment, type AppointmentStatus, type Bill, type Consultation,
  type Department, type Doctor, type DoctorMeta, type MedDocument, type Medication,
  type Patient, type PaymentMethod, type Prescription, type QueueEntry, type Receipt,
  type Staff, type TimelineEvent,
} from "@/lib/mock/domain";
import { type NotifCategory, type Notification } from "@/lib/notifications-mock";
import {
  AI_MODELS, FOLLOW_UPS, buildProbabilities, dueDateFor, modelForImageType, nextFollowUpId,
  type AIModel, type FollowUp, type FollowUpInterval,
} from "@/lib/mock/ai-models";

/** Soft-deleted records live here until restored or purged (Phase 10). */
export type TrashKind = "patient" | "doctor" | "staff" | "department" | "ai-report";
export type TrashItem = {
  id: string;
  kind: TrashKind;
  recordId: string;
  label: string;
  deletedAt: string;
  deletedBy: string;
  record: Patient | Doctor | Staff | Department | AIReport;
};

export type ClinixState = {
  patients: Patient[];
  doctors: Doctor[];
  doctorMeta: DoctorMeta[];
  staff: Staff[];
  departments: Department[];
  appointments: Appointment[];
  consultations: Consultation[];
  prescriptions: Prescription[];
  aiReports: AIReport[];
  bills: Bill[];
  receipts: Receipt[];
  documents: MedDocument[];
  queue: QueueEntry[];
  activityLog: ActivityLog[];
  notifications: Notification[];
  followUps: FollowUp[];
  aiModels: AIModel[];
  trash: TrashItem[];
};

const initialState: ClinixState = {
  patients: [],
  doctors: [],
  doctorMeta: [],
  staff: [],
  departments: [],
  appointments: [],
  consultations: [],
  prescriptions: [],
  aiReports: [],
  bills: [],
  receipts: [],
  documents: [],
  queue: [],
  activityLog: [],
  notifications: [],
  followUps: [],
  aiModels: [...AI_MODELS],
  trash: [],
};

let seq = 1;
const uid = (prefix: string) => `${prefix}-${Date.now().toString(36)}-${seq++}`;
const nowTime = () => new Date().toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", hour12: false });

export type ClinixActions = {
  /* --- notifications --- */
  notify: (n: { category: NotifCategory; title: string; body: string }) => void;
  markNotificationRead: (id: string, read?: boolean) => void;
  markAllNotificationsRead: () => void;
  clearNotifications: () => void;
  /* --- audit --- */
  log: (entry: { user: string; role: ActivityLog["role"]; action: string; entity: string; entityId?: string; status?: ActivityLog["status"] }) => void;
  /* --- patient --- */
  registerPatient: (data: Omit<Patient, "id" | "registeredOn">) => Patient;
  updatePatient: (id: string, patch: Partial<Patient>) => void;
  /* --- appointments --- */
  bookAppointment: (input: { patientId: string; doctorId: string; date: string; time: string; reason: string; note?: string }) => Promise<Appointment>;
  cancelAppointment: (id: string, reason?: string) => Promise<any>;
  rescheduleAppointment: (id: string, date: string, time: string) => void;
  checkInAppointment: (id: string) => QueueEntry | undefined;
  confirmAppointment: (id: string) => Promise<any>;
  completeAppointment: (id: string) => Promise<any>;
  refreshAppointments: () => Promise<void>;
  /* --- queue --- */
  setQueueStatus: (token: string, status: QueueEntry["status"]) => void;
  callNextPatient: () => QueueEntry | undefined;
  /* --- consultations --- */
  startConsultation: (appointmentId: string) => void;
  completeConsultation: (input: {
    appointmentId: string;
    diagnosis: string;
    medications: Medication[];
    notes?: string;
    followUp?: string;
    aiUsed?: boolean;
  }) => { prescription?: Prescription; bill: Bill };
  /* --- prescriptions --- */
  addPrescription: (rx: Omit<Prescription, "id">) => Prescription;
  /* --- documents --- */
  uploadDocument: (doc: Omit<MedDocument, "id" | "date" | "status"> & { id?: string; status?: MedDocument["status"] }) => MedDocument;
  removeDocument: (id: string) => void;
  /* --- AI --- */
  createAIAnalysis: (input: { patientId: string; doctorId?: string; appointmentId?: string; imageType: string }) => AIReport;
  completeAIAnalysis: (id: string, result: { prediction: string; confidence: number; explanation: string; gradcam?: "available" | "unavailable"; gradcamUrl?: string; imageUrl?: string; probabilities?: { label: string; probability: number }[] }, originalId?: string) => void;
  /* --- Phase 10: follow-ups, models, soft delete --- */
  scheduleFollowUp: (input: { patientId: string; doctorId: string; interval: FollowUpInterval; reason: string; dueDate?: string; appointmentId?: string; notes?: string }) => FollowUp;
  updateFollowUp: (id: string, patch: Partial<FollowUp>) => void;
  setFollowUpStatus: (id: string, status: FollowUp["status"]) => void;
  setAIModelStatus: (id: string, status: AIModel["status"]) => void;
  softDelete: (kind: TrashKind, recordId: string, actor?: string) => void;
  restoreTrash: (trashId: string) => void;
  purgeTrash: (trashId: string) => void;
  reviewAIReport: (id: string, decision: "accepted" | "rejected" | "not-relevant", note: string) => void;
  /* --- billing --- */
  generateBill: (input: { patientId: string; appointmentId: string; doctorId: string; items: { label: string; amount: number }[]; discount?: number }) => Bill;
  recordPayment: (billId: string, method: PaymentMethod, reference?: string) => Receipt | undefined;
  /* --- admin --- */
  addStaff: (s: Omit<Staff, "id" | "lastActive" | "photoInitial">) => Staff;
  updateStaff: (id: string, patch: Partial<Staff>) => void;
  removeStaff: (id: string) => void;
  updateDoctor: (id: string, patch: Partial<Doctor>) => void;
  addDepartment: (d: Omit<Department, "id">) => Department;
  updateDepartment: (id: string, patch: Partial<Department>) => void;
  removeDepartment: (id: string) => void;
  updateDoctorMeta: (doctorId: string, patch: Partial<DoctorMeta>) => void;
};

type ClinixContextValue = ClinixState & ClinixActions & {
  /* derived helpers bound to live state */
  getPatient: (id: string) => Patient | undefined;
  getDoctor: (id: string) => Doctor | undefined;
  getAppointment: (id: string) => Appointment | undefined;
  getBill: (id: string) => Bill | undefined;
  getReceipt: (id: string) => Receipt | undefined;
  getPrescription: (id: string) => Prescription | undefined;
  getAIReport: (id: string) => AIReport | undefined;
  unreadCount: number;
};

const ClinixContext = createContext<ClinixContextValue | null>(null);

export function ClinixProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<ClinixState>(initialState);
  const { user, isAuthenticated, hydrated } = useAuth();

  // Sync live clinical data from MongoDB Atlas when authenticated
  useEffect(() => {
    if (!user || !isAuthenticated || !hydrated) {
      setState(initialState);
      return;
    }

    let mounted = true;
    const fetchLive = async () => {
      try {
        const realRole = (user.rawRole || user.role || "").toLowerCase().trim();
        const isAdmin = realRole === "hospital_admin" || realRole === "admin";
        const isDoctor = realRole === "doctor";
        const isStaff = realRole === "hospital_staff" || realRole === "staff";
        const isPatient = realRole === "patient" || (!isAdmin && !isDoctor && !isStaff);

        // Role-aware endpoint mapping to prevent unauthorized 403 requests
        const [
          aptRes,
          deptRes,
          docRes,
          patRes,
          notifRes,
          docuRes,
          billRes,
          fuRes,
          auditRes,
          aiRes,
          staffRes,
          consRes,
          rxRes
        ] = await Promise.allSettled([
          apiClient.appointments.list({ page_size: 100 }),
          apiClient.departments.list(),
          apiClient.doctors.list({ page_size: 100 }),
          (isAdmin || isStaff || isDoctor)
            ? apiClient.patients.list({ page_size: 100 })
            : apiClient.patients.getMe().then((res) => ({ data: res?.data ? [res.data] : [] })).catch(() => ({ data: [] })),
          apiClient.notifications.list({ page_size: 100 }),
          apiClient.documents.list({ limit: 100 }),
          (isAdmin || isStaff || isPatient) ? apiClient.billing.list({ page_size: 100 }) : Promise.resolve({ data: [] }),
          apiClient.followUps.list({ limit: 100 }),
          isAdmin ? apiClient.auditLogs.list({ limit: 100 }) : Promise.resolve({ data: [] }),
          (isAdmin || isDoctor || isPatient) ? apiClient.ai.listAnalyses({ page_size: 100 }) : Promise.resolve({ data: [] }),
          isAdmin ? apiClient.staff.list({ page_size: 100 }) : Promise.resolve({ data: [] }),
          apiClient.consultations.list({ page_size: 100 }),
          apiClient.prescriptions.list({ page_size: 100 }),
        ]);

        if (!mounted) return;

        setState((prev) => {
          let nextApts = prev.appointments;
          let nextDepts = prev.departments;
          let nextDocs = prev.doctors;
          let nextPats = prev.patients;
          let nextNotifs = prev.notifications;
          let nextMedDocs = prev.documents;
          let nextBills = prev.bills;
          let nextFollowUps = prev.followUps;
          let nextLogs = prev.activityLog;
          let nextAiReports = prev.aiReports;
          let nextStaff = prev.staff;
          let nextConsultations = prev.consultations;
          let nextPrescriptions = prev.prescriptions;

          if (aptRes.status === "fulfilled" && aptRes.value?.data && Array.isArray(aptRes.value.data)) {
            nextApts = aptRes.value.data.map((a: any) => {
              let normStatus: AppointmentStatus = "scheduled";
              const st = (a.status || "").toLowerCase().replace(/_/g, "-");
              if (st === "completed") normStatus = "completed";
              else if (st === "cancelled") normStatus = "cancelled";
              else if (st === "in-consultation" || st === "in-progress") normStatus = "in-consultation";
              else if (st === "in-queue" || st === "waiting") normStatus = "in-queue";
              else if (st === "checked-in") normStatus = "checked-in";
              else if (st === "confirmed") normStatus = "confirmed";
              else if (st === "no-show") normStatus = "no-show";
              else normStatus = "scheduled";

              return {
                id: a.appointment_id,
                patientId: a.patient_id,
                doctorId: a.doctor_id,
                date: a.appointment_date,
                time: a.start_time,
                status: normStatus,
                reason: a.reason || "General Consultation",
                type: a.appointment_type || "in_person",
                note: a.reason,
              };
            });
          }

          if (deptRes.status === "fulfilled" && deptRes.value?.data && Array.isArray(deptRes.value.data)) {
            nextDepts = deptRes.value.data.map((d: any) => ({
              id: d.department_id,
              name: d.name,
              code: d.code,
              doctorCount: 1,
              description: d.description || "",
            }));
          }

          if (docRes.status === "fulfilled" && docRes.value?.data && Array.isArray(docRes.value.data)) {
            nextDocs = docRes.value.data.map((d: any) => {
              const fullName = d.full_name || `${d.first_name || ""} ${d.last_name || ""}`.trim();
              const initials = fullName
                .replace(/^Dr\.\s*/i, "")
                .split(" ")
                .filter(Boolean)
                .map((n: string) => n.charAt(0))
                .join("")
                .slice(0, 2)
                .toUpperCase() || "DR";

              return {
                id: d.doctor_id,
                name: fullName,
                email: d.email || "",
                specialization: d.specialization || "General Medicine",
                qualification: d.qualification || "MBBS, MD",
                department: d.department_id || "General Medicine",
                experienceYears: d.experience_years || 10,
                languages: ["English", "Hindi"],
                consultationFee: d.consultation_fee || 500,
                status: d.status || "active",
                nextAvailable: "Available Today",
                availableSlots: ["09:00", "09:30", "10:00", "11:00", "14:00", "15:00"],
                photoInitial: initials,
              };
            });
          }

          if (patRes.status === "fulfilled" && patRes.value?.data) {
            const rawPats = Array.isArray(patRes.value.data) ? patRes.value.data : [patRes.value.data];
            nextPats = rawPats.map((p: any) => {
              const fullName = p.full_name || `${p.first_name || ""} ${p.last_name || ""}`.trim();
              const nameParts = fullName.split(" ");
              return {
                id: p.patient_id,
                firstName: p.first_name || nameParts[0] || "Patient",
                lastName: p.last_name || nameParts.slice(1).join(" ") || "",
                email: p.email || "",
                mobile: p.phone || p.mobile || "",
                phone: p.phone || p.mobile || "",
                gender: p.gender || "female",
                dob: p.date_of_birth || "1995-01-01",
                bloodGroup: p.blood_group || "O+",
                conditions: p.conditions || p.allergies || p.medical_history || [],
                allergies: p.allergies || [],
                city: p.address?.city || p.city || "Tech City",
                registeredOn: p.created_at ? p.created_at.split("T")[0] : todayIso(),
                status: p.status || "active",
                emergency: p.emergency_contact
                  ? {
                      name: p.emergency_contact.name || "Emergency Contact",
                      relationship: p.emergency_contact.relationship || "Guardian",
                      mobile: p.emergency_contact.phone || p.emergency_contact.mobile || "",
                    }
                  : undefined,
              };
            });
          }

          if (notifRes.status === "fulfilled" && notifRes.value?.data && Array.isArray(notifRes.value.data)) {
            nextNotifs = notifRes.value.data.map((n: any) => {
              const nType = (n.notification_type || "").toLowerCase();
              let cat: NotifCategory = "system";
              if (nType.includes("appointment")) cat = "appointment";
              else if (nType.includes("bill") || nType.includes("payment")) cat = "billing";
              else if (nType.includes("rx") || nType.includes("prescription")) cat = "prescription";
              else if (nType.includes("follow")) cat = "follow-up";
              else if (nType.includes("ai")) cat = "ai-report";

              return {
                id: n.notification_id,
                category: cat,
                title: n.title,
                body: n.body,
                time: n.created_at ? n.created_at.split("T")[1]?.slice(0, 5) || "today" : "now",
                read: n.status === "READ",
                referenceId: n.reference_id,
                referenceType: n.reference_type,
              };
            });
          }

          if (docuRes.status === "fulfilled" && docuRes.value?.items && Array.isArray(docuRes.value.items)) {
            nextMedDocs = docuRes.value.items.map((d: any) => {
              const ext = (d.original_file_name || "").split(".").pop()?.toLowerCase() || "";
              let ft: MedDocument["fileType"] = "PDF";
              if (ext === "png") ft = "PNG";
              else if (ext === "jpg" || ext === "jpeg") ft = "JPG";
              else if (ext === "dcm") ft = "DICOM";

              const rawCat = (d.category || "").toLowerCase();
              let cat: MedDocument["category"] = "Other";
              if (d.is_mri || rawCat.includes("brain") || rawCat.includes("mri") || (d.title || "").toLowerCase().includes("mri") || (d.original_file_name || "").toLowerCase().includes("mri")) cat = "Brain MRI";
              else if (rawCat.includes("x-ray") || rawCat.includes("xray") || (d.title || "").toLowerCase().includes("x-ray")) cat = "Chest X-Ray";
              else if (rawCat.includes("ct")) cat = "CT Scan";
              else if (rawCat.includes("image")) cat = "Medical Image";
              else if (rawCat.includes("lab") || rawCat.includes("diagnostic")) cat = "Lab Report";
              else if (rawCat.includes("prescription")) cat = "Prescription";
              else if (rawCat.includes("consultation")) cat = "Consultation";
              else if (rawCat.includes("ai")) cat = "AI Report";
              else cat = d.category || "Other";

              const rawRoleStr = String(d.uploaded_by_role || d.uploader_role || d.uploader?.role || "").trim().toLowerCase().replace("userrole.", "");
              let uRole: MedDocument["uploadedBy"] = "staff";
              if (rawRoleStr.includes("patient")) {
                uRole = "patient";
              } else if (rawRoleStr.includes("doctor")) {
                uRole = "doctor";
              } else if (rawRoleStr.includes("admin")) {
                uRole = "staff";
              } else if (rawRoleStr.includes("staff")) {
                uRole = "staff";
              } else if (d.uploaded_by?.startsWith("USR-DOC")) {
                uRole = "doctor";
              } else if (d.uploaded_by?.startsWith("USR-PAT")) {
                uRole = "patient";
              }

              const detailedRole = rawRoleStr.includes("patient")
                ? "patient"
                : rawRoleStr.includes("doctor")
                ? "doctor"
                : rawRoleStr.includes("admin")
                ? "hospital_admin"
                : rawRoleStr.includes("staff")
                ? "staff"
                : uRole;

              const uName = d.uploader?.name || d.uploader_name || (detailedRole === "doctor" ? "Doctor" : detailedRole === "patient" ? "Patient" : detailedRole === "hospital_admin" ? "Hospital Administrator" : "Hospital Staff");
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
                uploadedByUserId: uId,
                uploaderName: uName,
                uploaderRole: detailedRole,
                uploadedByRole: detailedRole,
                aiAnalysisId: d.ai_analysis_id || undefined,
                aiAnalysisStatus: d.ai_analysis_status || undefined,
                modality: d.modality || (cat.includes("MRI") ? "Brain MRI" : cat.includes("X-Ray") ? "Chest X-Ray" : cat),
                date: d.created_at ? d.created_at.split("T")[0] : todayIso(),
                sizeKb: Math.max(1, Math.round((d.file_size_bytes || 1024) / 1024)),
                status: "available" as const,
              };
            });
          }

          if (billRes.status === "fulfilled" && billRes.value?.data && Array.isArray(billRes.value.data)) {
            nextBills = billRes.value.data.map((b: any) => ({
              id: b.bill_id,
              patientId: b.patient_id,
              appointmentId: b.appointment_id || "",
              doctorId: b.doctor_id || "DOC-1",
              items: b.line_items || [{ label: "Clinical Fee & Services", amount: b.grand_total }],
              subtotal: b.subtotal || b.grand_total,
              discount: b.discount_amount || 0,
              total: b.grand_total,
              status: b.status === "PAID" ? "paid" : b.status === "CANCELLED" ? "cancelled" : b.status === "ISSUED" ? "issued" : "draft",
              dueDate: b.created_at ? b.created_at.split("T")[0] : todayIso(),
              paidAt: b.amount_paid > 0 ? b.created_at : undefined,
            }));
          }

          if (fuRes.status === "fulfilled" && fuRes.value?.items && Array.isArray(fuRes.value.items)) {
            nextFollowUps = fuRes.value.items.map((f: any) => {
              const rawDate = f.scheduled_date ? String(f.scheduled_date).split("T")[0] : todayIso();
              const st = (f.status || "scheduled").toLowerCase();
              const mappedStatus = st === "scheduled" ? "upcoming" : st;
              return {
                id: f.follow_up_id,
                patientId: f.patient_id,
                doctorId: f.doctor_id,
                appointmentId: f.appointment_id,
                consultationId: f.consultation_id,
                interval: "custom" as any,
                reason: f.reason || "Follow-up consultation",
                dueDate: rawDate,
                status: mappedStatus as any,
                createdOn: f.created_at ? String(f.created_at).split("T")[0] : todayIso(),
                notes: f.notes,
              };
            });
          }

          if (auditRes.status === "fulfilled" && auditRes.value?.items && Array.isArray(auditRes.value.items)) {
            nextLogs = auditRes.value.items.map((l: any) => ({
              id: l.audit_id,
              timestamp: l.timestamp,
              user: l.actor_id || "System",
              role: (l.role || "staff").toLowerCase() as any,
              action: l.action,
              entity: l.resource,
              entityId: l.resource_id,
              status: "success",
            }));
          }

          const aiItems = aiRes.status === "fulfilled" ? (aiRes.value?.items || aiRes.value?.data) : undefined;
          if (Array.isArray(aiItems)) {
            nextAiReports = aiItems.map((r: any) => ({
              id: r.analysis_id,
              patientId: r.patient_id,
              doctorId: r.doctor_id || "",
              date: r.created_at ? String(r.created_at).split("T")[0] : todayIso(),
              imageType: r.model?.name || r.model?.module_id || "Brain MRI",
              status: r.status === "REVIEWED" ? "doctor-reviewed" : "analysis-completed",
              prediction: r.prediction?.predicted_class || "Normal",
              confidence: typeof r.prediction?.confidence === "number" ? (r.prediction.confidence > 1 ? r.prediction.confidence / 100 : r.prediction.confidence) : 0.95,
              explanation: r.prediction?.clinical_summary || "Real AI analysis completed.",
              gradcam: r.explainability?.artifact_storage_key || r.gradcam_path ? "available" : "unavailable",
              probabilities: r.prediction?.probabilities || r.prediction?.class_probabilities || [],
              doctorDecision: r.doctor_review?.decision,
              doctorNote: r.doctor_review?.clinical_interpretation,
              reviewedAt: r.doctor_review?.reviewed_at,
              imageUrl: r.input?.image_url || r.image_url,
            }));
          }

          if (staffRes.status === "fulfilled" && staffRes.value?.data && Array.isArray(staffRes.value.data)) {
            nextStaff = staffRes.value.data.map((s: any) => ({
              id: s.staff_id,
              name: s.full_name,
              role: s.designation || "Staff",
              department: s.department_id || "General",
              email: s.email,
              phone: s.phone || "",
              status: s.status || "active",
              photoInitial: s.full_name ? s.full_name.charAt(0) : "S",
            }));
          }

          if (consRes.status === "fulfilled" && consRes.value?.data && Array.isArray(consRes.value.data)) {
            nextConsultations = consRes.value.data.map((c: any) => ({
              id: c.consultation_id,
              appointmentId: c.appointment_id,
              patientId: c.patient_id,
              doctorId: c.doctor_id,
              date: c.created_at ? c.created_at.split("T")[0] : todayIso(),
              time: c.created_at ? c.created_at.split("T")[1]?.slice(0, 5) || "09:00" : "09:00",
              chiefComplaint: c.chief_complaint?.complaint || "Routine Checkup",
              vitals: c.vitals ? {
                bp: `${c.vitals.bp_systolic || c.vitals.blood_pressure_systolic || 120}/${c.vitals.bp_diastolic || c.vitals.blood_pressure_diastolic || 80}`,
                pulse: c.vitals.heart_rate_bpm || 72,
                temp: c.vitals.temperature_c ? `${c.vitals.temperature_c}°C` : c.vitals.temperature_celsius ? `${c.vitals.temperature_celsius}°C` : "37°C",
                spO2: c.vitals.spo2_percent ? `${c.vitals.spo2_percent}%` : "98%",
              } : undefined,
              diagnoses: c.diagnoses ? c.diagnoses.map((d: any) => d.name || d.code) : [],
              doctorInstructions: Array.isArray(c.doctor_instructions) ? c.doctor_instructions.join("; ") : (c.instructions?.doctor_instructions || c.doctor_instructions || ""),
              status: (c.status || "in-progress").toLowerCase() as any,
            }));
          }

          if (rxRes.status === "fulfilled" && rxRes.value?.data && Array.isArray(rxRes.value.data)) {
            nextPrescriptions = rxRes.value.data.map((p: any) => ({
              id: p.prescription_id,
              consultationId: p.consultation_id,
              patientId: p.patient_id,
              doctorId: p.doctor_id,
              date: p.created_at ? p.created_at.split("T")[0] : todayIso(),
              diagnosis: p.diagnosis || "Consultation",
              medications: p.medications ? p.medications.map((m: any) => ({
                name: m.drug_name,
                dosage: m.dosage,
                frequency: m.frequency,
                duration: m.duration,
                instructions: m.instructions,
              })) : [],
              notes: p.notes,
            }));
          }

          return {
            ...prev,
            appointments: nextApts,
            departments: nextDepts,
            doctors: nextDocs,
            patients: nextPats,
            notifications: nextNotifs,
            documents: nextMedDocs,
            bills: nextBills,
            followUps: nextFollowUps,
            activityLog: nextLogs,
            aiReports: nextAiReports,
            staff: nextStaff,
            consultations: nextConsultations,
            prescriptions: nextPrescriptions,
          };
        });
      } catch {
        // Handle error gracefully
      }
    };

    fetchLive();
    return () => {
      mounted = false;
    };
  }, [user]);

  // Real-time WebSocket notifications stream (Phase 17)
  useEffect(() => {
    console.log("[ClinixStore] WS useEffect triggered. user:", !!user, "auth:", isAuthenticated, "hydrated:", hydrated);
    if (!user || !isAuthenticated || !hydrated) return;

    let ws: WebSocket | null = null;
    let pingTimer: any = null;
    let reconnectTimer: any = null;
    let isDisposed = false;
    let retryDelay = 1000;

    const catchUpNotifications = () => {
      apiClient.notifications.list({ page_size: 100 }).then((res) => {
        if (!isDisposed && res?.data && Array.isArray(res.data)) {
          const mapped: Notification[] = res.data.map((n: any) => {
            const nType = (n.notification_type || n.type || "").toLowerCase();
            let cat: NotifCategory = "system";
            if (nType.includes("appointment")) cat = "appointment";
            else if (nType.includes("bill") || nType.includes("payment")) cat = "billing";
            else if (nType.includes("rx") || nType.includes("prescription")) cat = "prescription";
            else if (nType.includes("follow")) cat = "follow-up";
            else if (nType.includes("ai")) cat = "ai-report";

            return {
              id: n.notification_id,
              category: cat,
              title: n.title,
              body: n.body || n.message || "",
              time: n.created_at ? n.created_at.split("T")[1]?.slice(0, 5) || "now" : "now",
              read: n.read === true || n.status === "READ" || n.status === "read",
              referenceId: n.reference_id || n.source_id,
              referenceType: n.reference_type || n.source_type,
            };
          });
          setState((prev) => ({ ...prev, notifications: mapped }));
        }
      }).catch(() => {});
    };

    const connectWS = () => {
      if (isDisposed) return;
      const wsUrl = getWebSocketUrl();

      try {
        const token = getStoredTokens()?.accessToken;
        ws = token ? new WebSocket(wsUrl, [`bearer.${token}`]) : new WebSocket(wsUrl);

        ws.onopen = () => {
          retryDelay = 1000; // Reset backoff on successful connection
          // Catch up authoritative notifications from MongoDB upon reconnect
          catchUpNotifications();

          if (pingTimer) clearInterval(pingTimer);
          pingTimer = setInterval(() => {
            if (ws && ws.readyState === WebSocket.OPEN) {
              ws.send("ping");
            }
          }, 25000);
        };

        ws.onmessage = (event) => {
          if (event.data === "pong") return;
          try {
            const parsed = JSON.parse(event.data);
            const evName = parsed?.event;

            if (evName === "notification.created" || evName === "notification_received") {
              const n = parsed.notification || parsed.data;
              if (!n) return;
              const nType = (n.notification_type || n.type || "").toLowerCase();
              let cat: NotifCategory = "system";
              if (nType.includes("appointment")) cat = "appointment";
              else if (nType.includes("bill") || nType.includes("payment")) cat = "billing";
              else if (nType.includes("rx") || nType.includes("prescription")) cat = "prescription";
              else if (nType.includes("follow")) cat = "follow-up";
              else if (nType.includes("ai")) cat = "ai-report";

              const incoming: Notification = {
                id: n.notification_id,
                category: cat,
                title: n.title,
                body: n.body || n.message || "",
                time: n.created_at ? n.created_at.split("T")[1]?.slice(0, 5) || "now" : "now",
                read: n.read === true || n.status === "READ" || n.status === "read",
                referenceId: n.reference_id || n.source_id,
                referenceType: n.reference_type || n.source_type,
              };

              setState((prev) => {
                if (prev.notifications.some((x) => x.id === incoming.id)) {
                  return prev;
                }
                return {
                  ...prev,
                  notifications: [incoming, ...prev.notifications],
                };
              });
            } else if (evName === "notification.read") {
              const notifId = parsed.notification_id;
              if (notifId) {
                setState((prev) => ({
                  ...prev,
                  notifications: prev.notifications.map((x) =>
                    x.id === notifId ? { ...x, read: true } : x
                  ),
                }));
              }
            } else if (evName === "notification.unread") {
              const notifId = parsed.notification_id;
              if (notifId) {
                setState((prev) => ({
                  ...prev,
                  notifications: prev.notifications.map((x) =>
                    x.id === notifId ? { ...x, read: false } : x
                  ),
                }));
              }
            } else if (evName === "notification.read_all") {
              setState((prev) => ({
                ...prev,
                notifications: prev.notifications.map((x) => ({ ...x, read: true })),
              }));
            }
          } catch {
            // Ignore non-JSON
          }
        };

        ws.onclose = (event) => {
          if (pingTimer) clearInterval(pingTimer);
          // Do not reconnect if unmounted, or if server rejected auth (1008) or closed normally (1000)
          if (!isDisposed && event.code !== 1008 && event.code !== 1000) {
            reconnectTimer = setTimeout(() => {
              connectWS();
            }, retryDelay);
            retryDelay = Math.min(retryDelay * 2, 30000);
          }
        };

        ws.onerror = () => {
          ws?.close();
        };
      } catch {
        // Fallback gracefully
      }
    };

    connectWS();

    return () => {
      isDisposed = true;
      if (pingTimer) clearInterval(pingTimer);
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (ws) ws.close();
    };
  }, [user, isAuthenticated, hydrated]);


  /* ---------- notifications ---------- */
  const notify = useCallback<ClinixActions["notify"]>((n) => {
    setState((s) => ({
      ...s,
      notifications: [{ id: uid("N"), time: "now", read: false, ...n }, ...s.notifications],
    }));
  }, []);

  const markNotificationRead = useCallback<ClinixActions["markNotificationRead"]>((id, read = true) => {
    if (read) apiClient.notifications.markRead(id).catch(() => {});
    else apiClient.notifications.markUnread(id).catch(() => {});
    setState((s) => ({ ...s, notifications: s.notifications.map((n) => (n.id === id ? { ...n, read } : n)) }));
  }, []);

  const markAllNotificationsRead = useCallback(() => {
    apiClient.notifications.markAllRead().catch(() => {});
    setState((s) => ({ ...s, notifications: s.notifications.map((n) => ({ ...n, read: true })) }));
  }, []);

  const clearNotifications = useCallback(() => {
    setState((s) => {
      s.notifications.forEach((n) => apiClient.notifications.delete(n.id).catch(() => {}));
      return { ...s, notifications: [] };
    });
  }, []);


  const log = useCallback<ClinixActions["log"]>((entry) => {
    setState((s) => ({
      ...s,
      activityLog: [
        { id: uid("LOG"), timestamp: new Date().toISOString(), status: "success", ...entry },
        ...s.activityLog,
      ],
    }));
  }, []);

  const registerPatient = useCallback<ClinixActions["registerPatient"]>((data) => {
    const p: Patient = { ...data, id: nextPatientId(), registeredOn: todayIso() };

    // Persist new patient to MongoDB via FastAPI
    apiClient.patients.create({
      email: data.email,
      first_name: data.firstName,
      last_name: data.lastName,
      phone: data.mobile,
      gender: (data.gender || "male").toLowerCase(),
      date_of_birth: data.dob,
      blood_group: data.bloodGroup || "O+",
      allergies: data.allergies || [],
    }).catch(() => {});

    setState((s) => ({
      ...s,
      patients: [p, ...s.patients],
      activityLog: [{ id: uid("LOG"), timestamp: new Date().toISOString(), user: "Staff", role: "staff", action: "Patient registered", entity: "Patient", entityId: p.id, status: "success" }, ...s.activityLog],
      notifications: [{ id: uid("N"), category: "system", title: "Patient registered", body: `${p.firstName} ${p.lastName} • ${p.id}`, time: "now", read: false }, ...s.notifications],
    }));
    return p;
  }, []);

  const updatePatient = useCallback<ClinixActions["updatePatient"]>((id, p) => {
    setState((s) => ({ ...s, patients: s.patients.map((x) => (x.id === id ? { ...x, ...p } : x)) }));
  }, []);

  /* ---------- appointments ---------- */
  const bookAppointment = useCallback<ClinixActions["bookAppointment"]>(async (input) => {
    const doc = state.doctors.find((d) => d.id === input.doctorId) || getDoctor(input.doctorId);
    const deptId = (doc && doc.department && doc.department.startsWith("DEPT-"))
      ? doc.department
      : (doc?.department || "DEPT-CARD");

    let createdId = nextAppointmentId();
    try {
      const res = await apiClient.appointments.book({
        patient_id: input.patientId,
        doctor_id: input.doctorId,
        department_id: deptId,
        appointment_date: input.date,
        start_time: input.time,
        reason: input.reason,
        appointment_type: "new_consultation",
      });
      const returnedData = (res as any)?.data || res;
      if (returnedData && returnedData.appointment_id) {
        createdId = returnedData.appointment_id;
      }
    } catch (err: any) {
      const errMsg = err?.details?.message || err?.message || "Appointment slot is unavailable";
      throw new Error(errMsg);
    }

    const appt: Appointment = {
      id: createdId,
      ...input,
      status: "scheduled",
      createdAt: todayIso(),
    };

    setState((s) => {
      const existing = new Set(s.appointments.map((a) => a.id));
      let id = appt.id, n = 1;
      while (existing.has(id)) id = `${appt.id}-${n++}`;
      const finalAppt = { ...appt, id };
      // Do NOT create a local Consultation stub — the backend creates it when consultation is started
      return {
        ...s,
        appointments: [finalAppt, ...s.appointments],
        activityLog: [{ id: uid("LOG"), timestamp: new Date().toISOString(), user: "Patient", role: "patient", action: "Appointment created", entity: "Appointment", entityId: id, status: "success" }, ...s.activityLog],
        notifications: [{ id: uid("N"), category: "appointment", title: "Appointment confirmed", body: `${doc?.name ?? "Doctor"} • ${input.date} at ${input.time}`, time: "now", read: false }, ...s.notifications],
      };
    });
    return appt;
  }, []);

  const cancelAppointment = useCallback<ClinixActions["cancelAppointment"]>(async (id, reason) => {
    const res = await apiClient.appointments.cancel(id, reason);
    const updated = res?.data || res;
    setState((s) => ({
      ...s,
      appointments: s.appointments.map((a) => (a.id === id ? { ...a, status: "cancelled", note: reason ?? a.note } : a)),
      queue: s.queue.filter((q) => q.appointmentId !== id),
      activityLog: [{ id: uid("LOG"), timestamp: new Date().toISOString(), user: "Doctor", role: "doctor", action: "Appointment cancelled", entity: "Appointment", entityId: id, status: "warning" }, ...s.activityLog],
      notifications: [{ id: uid("N"), category: "appointment", title: "Appointment cancelled", body: `${id} has been cancelled.`, time: "now", read: false }, ...s.notifications],
    }));
    return updated;
  }, []);

  const rescheduleAppointment = useCallback<ClinixActions["rescheduleAppointment"]>((id, date, time) => {
    apiClient.appointments.reschedule(id, { appointment_date: date, start_time: time }).catch(() => {});
    setState((s) => ({
      ...s,
      appointments: s.appointments.map((a) => (a.id === id ? { ...a, date, time, status: "confirmed" } : a)),
      consultations: s.consultations.map((c) => (c.appointmentId === id ? { ...c, date } : c)),
      activityLog: [{ id: uid("LOG"), timestamp: new Date().toISOString(), user: "Patient", role: "patient", action: "Appointment rescheduled", entity: "Appointment", entityId: id, status: "success" }, ...s.activityLog],
      notifications: [{ id: uid("N"), category: "appointment", title: "Appointment rescheduled", body: `${id} moved to ${date} at ${time}.`, time: "now", read: false }, ...s.notifications],
    }));
  }, []);

  const checkInAppointment = useCallback<ClinixActions["checkInAppointment"]>((id) => {
    apiClient.appointments.checkIn(id).catch(() => {});
    let created: QueueEntry | undefined;
    setState((s) => {
      const appt = s.appointments.find((a) => a.id === id);
      if (!appt || s.queue.some((q) => q.appointmentId === id)) return s;
      const nums = s.queue.map((q) => parseInt(q.token.split("-")[1] ?? "0", 10));
      const token = `A-${String(Math.max(0, ...nums) + 1).padStart(3, "0")}`;
      const waiting = s.queue.filter((q) => q.status === "waiting").length;
      created = {
        token, appointmentId: id, patientId: appt.patientId, doctorId: appt.doctorId,
        checkInTime: nowTime(), status: "waiting", position: s.queue.length, estWaitMin: (waiting + 1) * 12,
      };
      return {
        ...s,
        queue: [...s.queue, created],
        appointments: s.appointments.map((a) => (a.id === id ? { ...a, status: "checked-in", token } : a)),
        activityLog: [{ id: uid("LOG"), timestamp: new Date().toISOString(), user: "Reception", role: "staff", action: "Patient checked in", entity: "Appointment", entityId: id, status: "success" }, ...s.activityLog],
        notifications: [{ id: uid("N"), category: "appointment", title: "Checked in", body: `Token ${token} issued.`, time: "now", read: false }, ...s.notifications],
      };
    });
    return created;
  }, []);

  const confirmAppointment = useCallback<ClinixActions["confirmAppointment"]>(async (id) => {
    const res = await apiClient.appointments.confirm(id);
    const updated = res?.data || res;
    setState((s) => ({
      ...s,
      appointments: s.appointments.map((a) => (a.id === id ? { ...a, status: "confirmed" } : a)),
      activityLog: [{ id: uid("LOG"), timestamp: new Date().toISOString(), user: "Doctor", role: "doctor", action: "Appointment confirmed", entity: "Appointment", entityId: id, status: "success" }, ...s.activityLog],
      notifications: [{ id: uid("N"), category: "appointment", title: "Appointment confirmed", body: `${id} is confirmed.`, time: "now", read: false }, ...s.notifications],
    }));
    return updated;
  }, []);

  const completeAppointment = useCallback<ClinixActions["completeAppointment"]>(async (id) => {
    const res = await apiClient.appointments.complete(id);
    const updated = res?.data || res;
    setState((s) => ({
      ...s,
      appointments: s.appointments.map((a) => (a.id === id ? { ...a, status: "completed" } : a)),
      activityLog: [{ id: uid("LOG"), timestamp: new Date().toISOString(), user: "Doctor", role: "doctor", action: "Appointment completed", entity: "Appointment", entityId: id, status: "success" }, ...s.activityLog],
      notifications: [{ id: uid("N"), category: "appointment", title: "Appointment completed", body: `${id} completed.`, time: "now", read: false }, ...s.notifications],
    }));
    return updated;
  }, []);

  const refreshAppointments = useCallback<ClinixActions["refreshAppointments"]>(async () => {
    try {
      const res = await apiClient.appointments.list({ page_size: 200 });
      if (res?.data && Array.isArray(res.data)) {
        const nextApts = res.data.map((a: any) => {
          let normStatus: AppointmentStatus = "scheduled";
          const st = (a.status || "").toLowerCase().replace(/_/g, "-");
          if (st === "completed") normStatus = "completed";
          else if (st === "cancelled") normStatus = "cancelled";
          else if (st === "in-consultation" || st === "in-progress") normStatus = "in-consultation";
          else if (st === "in-queue" || st === "waiting") normStatus = "in-queue";
          else if (st === "checked-in") normStatus = "checked-in";
          else if (st === "confirmed") normStatus = "confirmed";
          else if (st === "no-show") normStatus = "no-show";
          else normStatus = "scheduled";

          return {
            id: a.appointment_id,
            patientId: a.patient_id,
            doctorId: a.doctor_id,
            date: a.appointment_date,
            time: a.start_time,
            status: normStatus,
            reason: a.reason || "General Consultation",
            type: a.appointment_type || "in_person",
            note: a.reason,
          };
        });
        setState((prev) => ({ ...prev, appointments: nextApts }));
      }
    } catch (e) {
      console.warn("Could not refresh appointments:", e);
    }
  }, []);

  /* ---------- queue ---------- */
  const setQueueStatus = useCallback<ClinixActions["setQueueStatus"]>((token, status) => {
    setState((s) => {
      const entry = s.queue.find((q) => q.token === token);
      const apptStatus: Appointment["status"] | undefined =
        status === "in-consultation" ? "in-consultation" :
        status === "completed" ? "completed" :
        status === "waiting" || status === "called" ? "in-queue" : undefined;
      return {
        ...s,
        queue: s.queue.map((q) => (q.token === token ? { ...q, status } : q)),
        appointments: entry && apptStatus
          ? s.appointments.map((a) => (a.id === entry.appointmentId ? { ...a, status: apptStatus } : a))
          : s.appointments,
      };
    });
  }, []);

  const callNextPatient = useCallback<ClinixActions["callNextPatient"]>(() => {
    let called: QueueEntry | undefined;
    setState((s) => {
      const next = s.queue.find((q) => q.status === "waiting");
      if (!next) return s;
      called = { ...next, status: "called" };
      return {
        ...s,
        queue: s.queue.map((q) => (q.token === next.token ? { ...q, status: "called" } : q)),
        appointments: s.appointments.map((a) => (a.id === next.appointmentId ? { ...a, status: "in-queue" } : a)),
        notifications: [{ id: uid("N"), category: "appointment", title: `Token ${next.token} called`, body: "Please proceed to the consultation room.", time: "now", read: false }, ...s.notifications],
      };
    });
    return called;
  }, []);

  /* ---------- consultations ---------- */
  const startConsultation = useCallback<ClinixActions["startConsultation"]>((appointmentId) => {
    apiClient.consultations.start(appointmentId).catch(() => {});
    setState((s) => ({
      ...s,
      appointments: s.appointments.map((a) => (a.id === appointmentId ? { ...a, status: "in-consultation" } : a)),
      queue: s.queue.map((q) => (q.appointmentId === appointmentId ? { ...q, status: "in-consultation" } : q)),
      consultations: s.consultations.map((c) => (c.appointmentId === appointmentId ? { ...c, status: "in-progress", startedAt: nowTime() } : c)),
    }));
  }, []);

  const completeConsultation = useCallback<ClinixActions["completeConsultation"]>((input) => {
    const { appointmentId, diagnosis, medications, notes, followUp, aiUsed } = input;
    let result!: { prescription?: Prescription; bill: Bill };

    setState((s) => {
      const a = s.appointments.find((x) => x.id === appointmentId);
      if (!a) return s;
      const doc = s.doctors.find((d) => d.id === a.doctorId);
      const targetConsult = s.consultations.find((c) => c.appointmentId === appointmentId || c.id === appointmentId);
      const today = todayIso();

      const rx: Prescription | undefined = medications.length
        ? { id: uid("RX"), appointmentId, patientId: a.patientId, doctorId: a.doctorId, date: today, diagnosis, medications, notes, followUp }
        : undefined;

      if (targetConsult?.id) {
        apiClient.consultations.updateAssessment(targetConsult.id, {
          assessment: { summary: notes || `Patient evaluated for ${diagnosis}`, risk_level: "low" }
        }).then(() => {
          return apiClient.consultations.updateDiagnoses(targetConsult.id, {
            diagnoses: [{ name: diagnosis, type: "primary" }]
          });
        }).then(() => {
          if (rx) {
            return apiClient.prescriptions.create(targetConsult.id, {
              patient_id: a.patientId,
              doctor_id: a.doctorId,
              diagnosis,
              medications: medications.map((m) => ({
                name: m.name,
                dosage: m.dosage,
                frequency: m.frequency,
                duration: m.duration,
                instructions: m.instructions,
              })),
              notes,
            });
          }
        }).then(() => {
          return apiClient.consultations.complete(targetConsult.id);
        }).catch((err) => {
          console.warn("Consultation completion API sync warning:", err);
        });
      }

      const existingBill = s.bills.find((b) => b.appointmentId === appointmentId);
      const bill: Bill = existingBill ?? {
        id: nextBillId() + (s.bills.some((b) => b.id === nextBillId()) ? `-${seq++}` : ""),
        patientId: a.patientId, appointmentId, doctorId: a.doctorId, date: today,
        items: [{ label: "Consultation Fee", amount: doc?.consultationFee ?? 500 }],
        discount: 0, status: "pending",
      };
      result = { prescription: rx, bill };

      const summaryDoc: MedDocument = {
        id: uid("DOC"), patientId: a.patientId, appointmentId,
        name: `Consultation summary — ${doc?.name ?? "Doctor"}.pdf`,
        category: "Consultation", fileType: "PDF", uploadedBy: "doctor",
        date: today, status: "available", sizeKb: 208,
      };

      return {
        ...s,
        appointments: s.appointments.map((x) => (x.id === appointmentId ? { ...x, status: "completed" } : x)),
        queue: s.queue.map((q) => (q.appointmentId === appointmentId ? { ...q, status: "completed" } : q)),
        consultations: s.consultations.map((c) => (c.appointmentId === appointmentId || c.id === appointmentId
          ? { ...c, status: "completed", completedAt: nowTime(), prescriptionId: rx?.id, aiUsed: !!aiUsed || c.aiUsed, followUpRecommended: !!followUp, billingReady: true }
          : c)),
        prescriptions: rx ? [rx, ...s.prescriptions] : s.prescriptions,
        bills: existingBill ? s.bills : [bill, ...s.bills],
        documents: [summaryDoc, ...s.documents],
        activityLog: [{ id: uid("LOG"), timestamp: new Date().toISOString(), user: doc?.name ?? "Doctor", role: "doctor", action: "Consultation completed", entity: "Consultation", entityId: appointmentId, status: "success" }, ...s.activityLog],
        notifications: [
          { id: uid("N"), category: "billing", title: "Bill ready", body: `${bill.id} • ${inr(billTotal(bill))} pending at reception.`, time: "now", read: false },
          ...(rx ? [{ id: uid("N"), category: "prescription" as NotifCategory, title: "Prescription issued", body: diagnosis, time: "now", read: false }] : []),
          ...s.notifications,
        ],
      };
    });

    return result;
  }, []);

  const addPrescription = useCallback<ClinixActions["addPrescription"]>((rx) => {
    const created: Prescription = { ...rx, id: uid("RX") };
    // Persist to MongoDB if consultation ID is available
    if (rx.consultationId) {
      apiClient.prescriptions.create(rx.consultationId, {
        patient_id: rx.patientId,
        doctor_id: rx.doctorId,
        diagnosis: rx.diagnosis || "Consultation",
        medications: (rx.medications || []).map((m) => ({
          drug_name: m.name,
          dosage: m.dosage,
          frequency: m.frequency,
          duration: m.duration,
          instructions: m.instructions,
        })),
        notes: rx.notes,
      }).catch(() => {});
    }
    setState((s) => ({ ...s, prescriptions: [created, ...s.prescriptions] }));
    return created;
  }, []);

  /* ---------- documents ---------- */
  const uploadDocument = useCallback<ClinixActions["uploadDocument"]>((doc) => {
    const docId = (doc as any).id || uid("DOC");
    const created: MedDocument = { id: docId, date: todayIso(), status: doc.status ?? "available", ...doc };
    // If a raw File object was attached, upload it via the real backend
    if ((doc as any)._file instanceof File) {
      const fd = new FormData();
      fd.append("file", (doc as any)._file);
      fd.append("patient_id", doc.patientId);
      fd.append("title", doc.name);
      fd.append("category", doc.category || "Other");
      if (doc.appointmentId) fd.append("appointment_id", doc.appointmentId);
      apiClient.documents.upload(fd).catch(() => {});
    }
    setState((s) => ({
      ...s,
      documents: [created, ...s.documents],
      notifications: [{ id: uid("N"), category: "system", title: "Document uploaded", body: created.name, time: "now", read: false }, ...s.notifications],
    }));
    return created;
  }, []);

  const removeDocument = useCallback<ClinixActions["removeDocument"]>((id) => {
    apiClient.documents.delete(id).catch(() => {});
    setState((s) => ({ ...s, documents: s.documents.filter((d) => d.id !== id) }));
  }, []);

  /* ---------- AI ---------- */
  const createAIAnalysis = useCallback<ClinixActions["createAIAnalysis"]>((input) => {
    const model = modelForImageType(input.imageType);
    const report: AIReport = {
      id: uid("AI"), date: todayIso(), status: "processing", ...input,
      modelId: model.id, modelVersion: model.version,
      gradcam: model.gradcam === "enabled" ? "available" : "unavailable",
    };
    setState((s) => ({ ...s, aiReports: [report, ...s.aiReports] }));
    return report;
  }, []);

  const completeAIAnalysis = useCallback<ClinixActions["completeAIAnalysis"]>((id, result, originalId) => {
    setState((s) => ({
      ...s,
      aiReports: s.aiReports.map((r) => {
        if (r.id !== id && (!originalId || r.id !== originalId)) return r;
        const model = s.aiModels.find((m) => m.id === r.modelId) ?? modelForImageType(r.imageType);
        return {
          ...r, ...result, id, status: "analysis-completed" as const,
          modelId: r.modelId ?? model.id, modelVersion: r.modelVersion ?? model.version,
          probabilities: result.probabilities ?? buildProbabilities(model, result.prediction, result.confidence),
        };
      }),
      activityLog: [{ id: uid("LOG"), timestamp: new Date().toISOString(), user: "System", role: "system", action: "AI analysis completed", entity: "AI Report", entityId: id, status: "success" }, ...s.activityLog],
      notifications: [{ id: uid("N"), category: "ai-report", title: "AI analysis ready", body: `${result.prediction} • awaiting doctor review.`, time: "now", read: false }, ...s.notifications],
    }));
  }, []);

  const reviewAIReport = useCallback<ClinixActions["reviewAIReport"]>((id, decision, note) => {
    const label = decision === "accepted" ? "Accepted" : decision === "rejected" ? "Rejected" : "Not clinically relevant";
    setState((s) => ({
      ...s,
      aiReports: s.aiReports.map((r) => (r.id === id
        ? { ...r, status: decision === "accepted" ? "finalized" : "doctor-reviewed", doctorNote: `${label}: ${note}`, reviewDecision: decision, reviewedOn: todayIso() }
        : r)),
      activityLog: [{ id: uid("LOG"), timestamp: new Date().toISOString(), user: "Doctor", role: "doctor", action: `AI analysis ${label.toLowerCase()}`, entity: "AI Report", entityId: id, status: decision === "accepted" ? "success" : "warning" }, ...s.activityLog],
      notifications: [{ id: uid("N"), category: "ai-report", title: "AI report reviewed", body: `${id} — ${label}.`, time: "now", read: false }, ...s.notifications],
    }));
  }, []);

  /* ---------- Phase 10: follow-ups ---------- */
  const scheduleFollowUp = useCallback<ClinixActions["scheduleFollowUp"]>((input) => {
    let created!: FollowUp;
    setState((s) => {
      const dateStr = input.dueDate ?? dueDateFor(input.interval);
      created = {
        id: nextFollowUpId(s.followUps.length + seq++),
        patientId: input.patientId,
        doctorId: input.doctorId,
        appointmentId: input.appointmentId,
        dueDate: dateStr,
        interval: input.interval,
        reason: input.reason,
        status: "upcoming",
        createdOn: todayIso(),
        notes: input.notes,
      };
      // Persist to MongoDB via FastAPI
      apiClient.followUps.create({
        patient_id: input.patientId,
        doctor_id: input.doctorId,
        scheduled_date: dateStr.includes("T") ? dateStr : `${dateStr}T09:00:00Z`,
        reason: input.reason,
        notes: input.notes,
        appointment_id: input.appointmentId,
      }).catch(() => {});
      return {
        ...s,
        followUps: [created, ...s.followUps],
        activityLog: [{ id: uid("LOG"), timestamp: new Date().toISOString(), user: getDoctor(input.doctorId)?.name ?? "Doctor", role: "doctor", action: "Follow-up scheduled", entity: "Follow-up", entityId: created.id, status: "success" }, ...s.activityLog],
        notifications: [{ id: uid("N"), category: "appointment", title: "Follow-up scheduled", body: `${created.reason} • due ${created.dueDate}`, time: "now", read: false }, ...s.notifications],
      };
    });
    return created;
  }, []);

  const updateFollowUp = useCallback<ClinixActions["updateFollowUp"]>((id, patch) => {
    const formattedDate = patch.dueDate ? (patch.dueDate.includes("T") ? patch.dueDate : `${patch.dueDate}T09:00:00Z`) : undefined;
    const backendStatus = patch.status === "upcoming" ? "scheduled" : patch.status;
    apiClient.followUps.update(id, {
      scheduled_date: formattedDate,
      reason: patch.reason,
      notes: patch.notes,
      status: backendStatus as any,
    }).catch(() => {});
    setState((s) => ({ ...s, followUps: s.followUps.map((f) => (f.id === id ? { ...f, ...patch } : f)) }));
  }, []);

  const setFollowUpStatus = useCallback<ClinixActions["setFollowUpStatus"]>((id, status) => {
    const backendStatus = status === "upcoming" ? "scheduled" : status;
    // Persist status change to MongoDB via FastAPI
    apiClient.followUps.update(id, { status: backendStatus as any }).catch(() => {});
    setState((s) => ({
      ...s,
      followUps: s.followUps.map((f) => (f.id === id ? { ...f, status } : f)),
      activityLog: [{ id: uid("LOG"), timestamp: new Date().toISOString(), user: "Doctor", role: "doctor", action: `Follow-up ${status}`, entity: "Follow-up", entityId: id, status: status === "cancelled" ? "warning" : "success" }, ...s.activityLog],
    }));
  }, []);

  /* ---------- Phase 10: AI model management ---------- */
  const setAIModelStatus = useCallback<ClinixActions["setAIModelStatus"]>((id, status) => {
    setState((s) => ({
      ...s,
      aiModels: s.aiModels.map((m) => (m.id === id ? { ...m, status } : m)),
      activityLog: [{ id: uid("LOG"), timestamp: new Date().toISOString(), user: "Admin", role: "admin", action: `AI model ${status}`, entity: "AI Model", entityId: id, status: status === "active" ? "success" : "warning" }, ...s.activityLog],
    }));
  }, []);

  /* ---------- Phase 10: soft delete & restore ---------- */
  const softDelete = useCallback<ClinixActions["softDelete"]>((kind, recordId, actor = "Admin") => {
    setState((s) => {
      let record: TrashItem["record"] | undefined;
      let label = recordId;
      const next: ClinixState = { ...s };
      if (kind === "patient") {
        record = s.patients.find((x) => x.id === recordId);
        if (record) label = `${(record as Patient).firstName} ${(record as Patient).lastName}`;
        next.patients = s.patients.filter((x) => x.id !== recordId);
      } else if (kind === "doctor") {
        record = s.doctors.find((x) => x.id === recordId);
        if (record) label = (record as Doctor).name;
        next.doctors = s.doctors.filter((x) => x.id !== recordId);
      } else if (kind === "staff") {
        record = s.staff.find((x) => x.id === recordId);
        if (record) label = `${(record as Staff).firstName} ${(record as Staff).lastName}`;
        next.staff = s.staff.filter((x) => x.id !== recordId);
      } else if (kind === "department") {
        record = s.departments.find((x) => x.id === recordId);
        if (record) label = (record as Department).name;
        next.departments = s.departments.filter((x) => x.id !== recordId);
      } else {
        record = s.aiReports.find((x) => x.id === recordId);
        if (record) label = (record as AIReport).imageType;
        next.aiReports = s.aiReports.filter((x) => x.id !== recordId);
      }
      if (!record) return s;
      const item: TrashItem = { id: uid("TRASH"), kind, recordId, label, deletedAt: new Date().toISOString(), deletedBy: actor, record };
      next.trash = [item, ...s.trash];
      next.activityLog = [{ id: uid("LOG"), timestamp: new Date().toISOString(), user: actor, role: "admin", action: `${kind} moved to trash`, entity: kind, entityId: recordId, status: "warning" }, ...s.activityLog];
      return next;
    });
  }, []);

  const restoreTrash = useCallback<ClinixActions["restoreTrash"]>((trashId) => {
    setState((s) => {
      const item = s.trash.find((t) => t.id === trashId);
      if (!item) return s;
      const collMap: Record<string, string> = {
        patient: "patients",
        doctor: "doctors",
        staff: "staff",
        department: "departments",
        "ai-report": "ai_analyses",
      };
      const collectionName = collMap[item.kind] || "patients";
      apiClient.admin.restore(collectionName, item.recordId).catch(() => {});

      const next: ClinixState = { ...s, trash: s.trash.filter((t) => t.id !== trashId) };
      if (item.kind === "patient") next.patients = [item.record as Patient, ...s.patients];
      else if (item.kind === "doctor") next.doctors = [item.record as Doctor, ...s.doctors];
      else if (item.kind === "staff") next.staff = [item.record as Staff, ...s.staff];
      else if (item.kind === "department") next.departments = [...s.departments, item.record as Department];
      else next.aiReports = [item.record as AIReport, ...s.aiReports];
      next.activityLog = [{ id: uid("LOG"), timestamp: new Date().toISOString(), user: "Admin", role: "admin", action: `${item.kind} restored`, entity: item.kind, entityId: item.recordId, status: "success" }, ...s.activityLog];
      return next;
    });
  }, []);

  const purgeTrash = useCallback<ClinixActions["purgeTrash"]>((trashId) => {
    setState((s) => {
      const item = s.trash.find((t) => t.id === trashId);
      if (!item) return s;
      const collMap: Record<string, string> = {
        patient: "patients",
        doctor: "doctors",
        staff: "staff",
        department: "departments",
        "ai-report": "ai_analyses",
      };
      const collectionName = collMap[item.kind] || "patients";
      apiClient.admin.purge(collectionName, item.recordId).catch(() => {});

      return {
        ...s,
        trash: s.trash.filter((t) => t.id !== trashId),
        activityLog: [{ id: uid("LOG"), timestamp: new Date().toISOString(), user: "Admin", role: "admin", action: `${item.kind} permanently deleted`, entity: item.kind, entityId: item.recordId, status: "warning" }, ...s.activityLog],
      };
    });
  }, []);

  /* ---------- billing ---------- */
  const generateBill = useCallback<ClinixActions["generateBill"]>((input) => {
    let created!: Bill;
    // Persist to MongoDB via FastAPI billing endpoint
    apiClient.billing.create({
      patient_id: input.patientId,
      appointment_id: input.appointmentId,
      line_items: input.items.map((i) => ({
        item_code: i.label.toLowerCase().replace(/[^a-z0-9]+/g, "_").slice(0, 50) || "svc",
        description: i.label,
        unit_price: i.amount,
        quantity: 1,
        tax_percent: 0,
        discount_amount: 0,
      })),
      notes: "Auto-generated bill",
    }).then((res) => {
      if (res?.data?.bill_id) {
        setState((s) => ({
          ...s,
          bills: s.bills.map((b) => b.id === created.id ? { ...b, id: res.data.bill_id } : b),
        }));
      }
    }).catch(() => {});

    setState((s) => {
      let id = nextBillId(), n = 1;
      const ids = new Set(s.bills.map((b) => b.id));
      while (ids.has(id)) id = `${nextBillId()}-${n++}`;
      created = { id, date: todayIso(), discount: input.discount ?? 0, status: "pending", ...input, items: input.items };
      return {
        ...s,
        bills: [created, ...s.bills],
        activityLog: [{ id: uid("LOG"), timestamp: new Date().toISOString(), user: "Billing", role: "staff", action: "Bill generated", entity: "Bill", entityId: id, status: "success" }, ...s.activityLog],
        notifications: [{ id: uid("N"), category: "billing", title: "Invoice generated", body: `${id} • ${inr(billTotal(created))}`, time: "now", read: false }, ...s.notifications],
      };
    });
    return created;
  }, []);

  const recordPayment = useCallback<ClinixActions["recordPayment"]>((billId, method, reference) => {
    let receipt: Receipt | undefined;
    setState((s) => {
      const bill = s.bills.find((b) => b.id === billId);
      if (!bill || bill.status === "paid") return s;
      const rid = nextReceiptId(bill.id);
      const amt = billTotal(bill);
      // Persist payment to MongoDB — only call once with the resolved amount
      apiClient.billing.recordPayment(billId, {
        amount: Math.max(amt, 0.01),
        method,
        reference_number: reference,
      }).catch(() => {});
      receipt = {
        id: rid, billId: bill.id, patientId: bill.patientId, doctorId: bill.doctorId,
        appointmentId: bill.appointmentId, date: todayIso(), amount: amt, method, reference,
      };
      return {
        ...s,
        bills: s.bills.map((b) => (b.id === billId ? { ...b, status: "paid", method, reference, paidOn: todayIso(), receiptId: rid } : b)),
        receipts: [receipt!, ...s.receipts],
        activityLog: [{ id: uid("LOG"), timestamp: new Date().toISOString(), user: "Billing", role: "staff", action: "Payment recorded", entity: "Bill", entityId: billId, status: "success" }, ...s.activityLog],
        notifications: [{ id: uid("N"), category: "billing", title: "Payment received", body: `${inr(amt)} via ${method.toUpperCase()} • receipt ${rid}`, time: "now", read: false }, ...s.notifications],
      };
    });
    return receipt;
  }, []);

  /* ---------- admin ---------- */
  const addStaff = useCallback<ClinixActions["addStaff"]>((data) => {
    const nums = (state.staff || []).map((x) => parseInt(x.id.split("-").at(-1)!, 10));
    const created: Staff = {
      ...data,
      id: `STF-2026-${String(Math.max(...nums, 0) + seq++).padStart(5, "0")}`,
      lastActive: "just now",
      photoInitial: `${data.firstName[0] ?? "S"}${data.lastName[0] ?? ""}`.toUpperCase(),
    };

    apiClient.staff.create({
      email: data.email,
      full_name: `${data.firstName} ${data.lastName}`,
      designation: data.desk || "Senior Staff Coordinator",
      department_id: data.department,
      phone: data.mobile,
    }).catch(() => {});

    setState((s) => ({
      ...s,
      staff: [created, ...s.staff],
      activityLog: [{ id: uid("LOG"), timestamp: new Date().toISOString(), user: "Admin", role: "admin", action: "Staff added", entity: "Staff", entityId: created.id, status: "success" }, ...s.activityLog],
    }));
    return created;
  }, [state.staff]);

  const updateStaff = useCallback<ClinixActions["updateStaff"]>((id, p) => {
    const payload: any = {};
    if (p.firstName) payload.first_name = p.firstName;
    if (p.lastName) payload.last_name = p.lastName;
    if (p.mobile) payload.phone = p.mobile;
    if (p.department) payload.department_id = p.department;
    if (p.desk) payload.job_title = p.desk;
    if (p.status) payload.status = p.status.toLowerCase();

    apiClient.staff.update(id, payload).catch((err) => {
      console.warn("Failed to persist staff update to backend:", err);
    });

    setState((s) => ({
      ...s,
      staff: s.staff.map((x) => (x.id === id ? { ...x, ...p } : x)),
      activityLog: [{ id: uid("LOG"), timestamp: new Date().toISOString(), user: "Admin", role: "admin", action: "Staff updated", entity: "Staff", entityId: id, status: "success" }, ...s.activityLog],
    }));
  }, []);

  const updateDoctor = useCallback<ClinixActions["updateDoctor"]>((id, p) => {
    const payload: any = {};
    if (p.name) {
      const parts = p.name.trim().split(" ");
      payload.first_name = parts[0];
      payload.last_name = parts.slice(1).join(" ") || "MD";
      payload.full_name = p.name;
    }
    if (p.specialization) payload.specialization = p.specialization;
    if (p.qualification) payload.qualification = p.qualification;
    if (p.department) payload.department_id = p.department;
    if (p.experienceYears !== undefined) payload.experience_years = p.experienceYears;
    if (p.consultationFee !== undefined) payload.consultation_fee = p.consultationFee;
    if (p.status) payload.status = p.status.toLowerCase();

    apiClient.doctors.update(id, payload).catch((err) => {
      console.warn("Failed to persist doctor update to backend:", err);
    });

    setState((s) => ({
      ...s,
      doctors: s.doctors.map((x) => (x.id === id ? { ...x, ...p } : x)),
      activityLog: [{ id: uid("LOG"), timestamp: new Date().toISOString(), user: "Admin", role: "admin", action: "Doctor updated", entity: "Doctor", entityId: id, status: "success" }, ...s.activityLog],
    }));
  }, []);

  const removeStaff = useCallback<ClinixActions["removeStaff"]>((id) => {
    softDelete("staff", id);
  }, [softDelete]);

  const addDepartment = useCallback<ClinixActions["addDepartment"]>((d) => {
    let created!: Department;
    setState((s) => {
      created = { ...d, id: `DEP-${String(s.departments.length + 1).padStart(2, "0")}-${seq++}` };
      return {
        ...s,
        departments: [...s.departments, created],
        activityLog: [{ id: uid("LOG"), timestamp: new Date().toISOString(), user: "Admin", role: "admin", action: "Department added", entity: "Department", entityId: created.id, status: "success" }, ...s.activityLog],
      };
    });
    return created;
  }, []);

  const updateDepartment = useCallback<ClinixActions["updateDepartment"]>((id, p) => {
    setState((s) => ({
      ...s,
      departments: s.departments.map((d) => (d.id === id ? { ...d, ...p } : d)),
      activityLog: [{ id: uid("LOG"), timestamp: new Date().toISOString(), user: "Admin", role: "admin", action: "Department updated", entity: "Department", entityId: id, status: "success" }, ...s.activityLog],
    }));
  }, []);

  const removeDepartment = useCallback<ClinixActions["removeDepartment"]>((id) => {
    softDelete("department", id);
  }, [softDelete]);

  const updateDoctorMeta = useCallback<ClinixActions["updateDoctorMeta"]>((doctorId, p) => {
    setState((s) => ({
      ...s,
      doctorMeta: s.doctorMeta.map((m) => (m.doctorId === doctorId ? { ...m, ...p } : m)),
      activityLog: [{ id: uid("LOG"), timestamp: new Date().toISOString(), user: "Admin", role: "admin", action: "Doctor updated", entity: "Doctor", entityId: doctorId, status: "success" }, ...s.activityLog],
    }));
  }, []);

  const value = useMemo<ClinixContextValue>(() => ({
    ...state,
    unreadCount: state.notifications.filter((n) => !n.read).length,
    getPatient: (id) => state.patients.find((p) => p.id === id),
    getDoctor: (id) => state.doctors.find((d) => d.id === id),
    getAppointment: (id) => state.appointments.find((a) => a.id === id),
    getBill: (id) => state.bills.find((b) => b.id === id),
    getReceipt: (id) => state.receipts.find((r) => r.id === id),
    getPrescription: (id) => state.prescriptions.find((p) => p.id === id),
    getAIReport: (id) => state.aiReports.find((a) => a.id === id),
    notify, markNotificationRead, markAllNotificationsRead, clearNotifications, log,
    registerPatient, updatePatient,
    bookAppointment, cancelAppointment, rescheduleAppointment, checkInAppointment, confirmAppointment, completeAppointment, refreshAppointments,
    setQueueStatus, callNextPatient,
    startConsultation, completeConsultation, addPrescription,
    uploadDocument, removeDocument,
    createAIAnalysis, completeAIAnalysis, reviewAIReport,
    scheduleFollowUp, updateFollowUp, setFollowUpStatus, setAIModelStatus,
    softDelete, restoreTrash, purgeTrash,
    generateBill, recordPayment,
    addStaff, updateStaff, removeStaff, updateDoctor,
    addDepartment, updateDepartment, removeDepartment, updateDoctorMeta,
  }), [
    state, notify, markNotificationRead, markAllNotificationsRead, clearNotifications, log,
    registerPatient, updatePatient, bookAppointment, cancelAppointment, rescheduleAppointment,
    checkInAppointment, confirmAppointment, completeAppointment, refreshAppointments, setQueueStatus, callNextPatient, startConsultation, completeConsultation,
    addPrescription, uploadDocument, removeDocument, createAIAnalysis, completeAIAnalysis,
    reviewAIReport, scheduleFollowUp, updateFollowUp, setFollowUpStatus, setAIModelStatus,
    softDelete, restoreTrash, purgeTrash,
    generateBill, recordPayment, addStaff, updateStaff, removeStaff, updateDoctor,
    addDepartment, updateDepartment, removeDepartment, updateDoctorMeta,
  ]);

  return <ClinixContext.Provider value={value}>{children}</ClinixContext.Provider>;
}

export function useClinix(): ClinixContextValue {
  const ctx = useContext(ClinixContext);
  if (!ctx) throw new Error("useClinix must be used within ClinixProvider");
  return ctx;
}

/* ---------- derived selectors (pure, take live state slices) ---------- */
export function patientTimelineFrom(s: ClinixState, pid: string): TimelineEvent[] {
  const events: TimelineEvent[] = [];
  const patient = s.patients.find((p) => p.id === pid);
  if (patient) events.push({ id: `reg-${pid}`, kind: "registration", title: "Patient registered", description: `Welcome, ${patient.firstName}`, date: patient.registeredOn });
  for (const a of s.appointments.filter((a) => a.patientId === pid)) {
    const doc = s.doctors.find((d) => d.id === a.doctorId);
    events.push({ id: `apt-${a.id}`, kind: "appointment", title: `Appointment ${a.status === "completed" ? "completed" : a.status === "cancelled" ? "cancelled" : "booked"} — ${doc?.name ?? "Doctor"}`, description: `${doc?.department} • ${a.time}`, date: a.date, ref: { type: "appointment", id: a.id } });
  }
  for (const p of s.prescriptions.filter((p) => p.patientId === pid)) events.push({ id: `rx-${p.id}`, kind: "prescription", title: "Prescription issued", description: p.diagnosis, date: p.date, ref: { type: "prescription", id: p.id } });
  for (const ai of s.aiReports.filter((a) => a.patientId === pid)) events.push({ id: `ai-${ai.id}`, kind: "ai", title: `AI analysis — ${ai.imageType}`, description: ai.prediction, date: ai.date, ref: { type: "ai-report", id: ai.id } });
  for (const b of s.bills.filter((b) => b.patientId === pid)) events.push({ id: `bill-${b.id}`, kind: "billing", title: `Bill ${b.status === "paid" ? "paid" : "generated"}`, description: `${inr(billTotal(b))} • ${b.id}`, date: b.date, ref: { type: "bill", id: b.id } });
  for (const d of s.documents.filter((d) => d.patientId === pid)) events.push({ id: `doc-${d.id}`, kind: d.category === "Medical Image" ? "image" : "report", title: `${d.category} uploaded`, description: d.name, date: d.date });
  return events.sort((a, b) => (a.date < b.date ? 1 : -1));
}
