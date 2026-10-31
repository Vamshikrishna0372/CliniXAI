/**
 * Phase 10 — Clinical Intelligence mock data.
 * AI model registry, probability distributions, follow-up management and
 * AI usage analytics. Mock only; shapes mirror the future FastAPI contract.
 */
import { DOCTORS, PATIENTS, todayIso } from "@/lib/mock/domain";

export type AIModelKey = "brain-mri" | "chest-xray" | "skin" | "eye" | "bone";

export type AIModel = {
  id: AIModelKey;
  name: string;
  modality: "MRI" | "X-Ray" | "Dermoscopy" | "Fundus" | "X-Ray (Ortho)";
  status: "active" | "disabled" | "maintenance";
  version: string;
  lastTrained: string;
  architecture: string;
  inputSize: string;
  predictions: number;
  avgConfidence: number;
  gradcam: "enabled" | "disabled";
  classes: string[];
  datasetSize: number;
  accuracy: number;
  notes: string;
};

export const AI_MODELS: AIModel[] = [
  {
    id: "brain-mri", name: "Brain MRI Tumour Classifier", modality: "MRI", status: "active",
    version: "v2.4.1", lastTrained: "2026-05-18", architecture: "ResNet50 (transfer learning)",
    inputSize: "224 × 224 × 3", predictions: 1842, avgConfidence: 0.93, gradcam: "enabled",
    classes: ["Glioma", "Meningioma", "Pituitary", "No Tumor"], datasetSize: 7023, accuracy: 0.961,
    notes: "Validated on axial T1-contrast sequences. Decision support only.",
  },
  {
    id: "chest-xray", name: "Chest X-Ray Screening", modality: "X-Ray", status: "active",
    version: "v3.1.0", lastTrained: "2026-06-02", architecture: "ResNet50 + FPN head",
    inputSize: "320 × 320 × 1", predictions: 4610, avgConfidence: 0.89, gradcam: "enabled",
    classes: ["Normal", "Pneumonia", "Effusion", "Nodule", "Cardiomegaly"], datasetSize: 21400, accuracy: 0.942,
    notes: "PA and AP views supported. Paediatric films flagged for manual review.",
  },
  {
    id: "skin", name: "Dermatology Lesion Classifier", modality: "Dermoscopy", status: "active",
    version: "v1.8.3", lastTrained: "2026-04-11", architecture: "EfficientNet-B3",
    inputSize: "300 × 300 × 3", predictions: 968, avgConfidence: 0.86, gradcam: "enabled",
    classes: ["Melanocytic nevus", "Melanoma", "Basal cell carcinoma", "Benign keratosis"], datasetSize: 10015, accuracy: 0.908,
    notes: "Dermoscopic images only; clinical photographs are out of distribution.",
  },
  {
    id: "eye", name: "Diabetic Retinopathy Grading", modality: "Fundus", status: "maintenance",
    version: "v2.0.0-rc2", lastTrained: "2026-06-21", architecture: "InceptionV3",
    inputSize: "512 × 512 × 3", predictions: 512, avgConfidence: 0.84, gradcam: "enabled",
    classes: ["No DR", "Mild", "Moderate", "Severe", "Proliferative"], datasetSize: 35126, accuracy: 0.897,
    notes: "Release candidate under clinical validation. Results labelled provisional.",
  },
  {
    id: "bone", name: "Bone Fracture Detection", modality: "X-Ray (Ortho)", status: "disabled",
    version: "v1.2.7", lastTrained: "2026-01-29", architecture: "DenseNet121",
    inputSize: "256 × 256 × 1", predictions: 337, avgConfidence: 0.81, gradcam: "disabled",
    classes: ["No fracture", "Fracture"], datasetSize: 4820, accuracy: 0.874,
    notes: "Disabled pending Grad-CAM explainability upgrade.",
  },
];

export const getAIModel = (id?: string) => AI_MODELS.find((m) => m.id === id);

/** Map a free-text image type onto a registry model. */
export function modelForImageType(imageType?: string): AIModel {
  const t = (imageType || "mri").toLowerCase();
  if (t.includes("mri") || t.includes("brain")) return AI_MODELS[0]!;
  if (t.includes("skin") || t.includes("derm") || t.includes("lesion")) return AI_MODELS[2]!;
  if (t.includes("fundus") || t.includes("eye") || t.includes("retin")) return AI_MODELS[3]!;
  if (t.includes("bone") || t.includes("fracture") || t.includes("ortho")) return AI_MODELS[4]!;
  return AI_MODELS[1]!;
}

export type ClassProbability = { label: string; probability: number };

/**
 * Build a probability distribution for a model where `top` carries `confidence`
 * and the remaining mass is spread over the other classes.
 */
export function buildProbabilities(model: AIModel, top: string, confidence: number): ClassProbability[] {
  const classes = model.classes.includes(top) ? model.classes : [top, ...model.classes];
  const rest = classes.filter((c) => c !== top);
  const remaining = Math.max(0, 1 - confidence);
  const weights = rest.map((_, i) => 1 / (i + 1.5));
  const sum = weights.reduce((a, b) => a + b, 0) || 1;
  return [
    { label: top, probability: confidence },
    ...rest.map((label, i) => ({ label, probability: (remaining * weights[i]!) / sum })),
  ].map((p) => ({ ...p, probability: Number(p.probability.toFixed(4)) }));
}

/* ---------------- Follow-ups ---------------- */

export type FollowUpStatus = "upcoming" | "completed" | "overdue" | "cancelled";
export type FollowUpInterval = "7d" | "15d" | "30d" | "custom";

export type FollowUp = {
  id: string;
  patientId: string;
  doctorId: string;
  appointmentId?: string;
  consultationId?: string;
  dueDate: string; // YYYY-MM-DD
  interval: FollowUpInterval;
  reason: string;
  status: FollowUpStatus;
  createdOn: string;
  notes?: string;
};

const addDays = (iso: string, days: number) => {
  const d = new Date(iso + "T00:00:00");
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
};

export const intervalDays = (i: FollowUpInterval) => (i === "7d" ? 7 : i === "15d" ? 15 : i === "30d" ? 30 : 0);
export const dueDateFor = (interval: FollowUpInterval, from = todayIso()) => addDays(from, intervalDays(interval));

/** Recompute overdue purely from the due date (upcoming that has passed). */
export function resolveFollowUpStatus(f: FollowUp, today = todayIso()): FollowUpStatus {
  if (f.status === "upcoming" && f.dueDate < today) return "overdue";
  return f.status;
}

const _today = todayIso();
export const FOLLOW_UPS: FollowUp[] = [
  { id: "FU-2026-0001", patientId: PATIENTS[0]!.id, doctorId: DOCTORS[0]!.id, dueDate: addDays(_today, 7), interval: "7d", reason: "Review persistent cough after antibiotics", status: "upcoming", createdOn: addDays(_today, -1) },
  { id: "FU-2026-0002", patientId: PATIENTS[1]!.id, doctorId: DOCTORS[1]!.id, dueDate: addDays(_today, 15), interval: "15d", reason: "Blood pressure recheck", status: "upcoming", createdOn: addDays(_today, -5) },
  { id: "FU-2026-0003", patientId: PATIENTS[2]!.id, doctorId: DOCTORS[0]!.id, dueDate: addDays(_today, -3), interval: "30d", reason: "HbA1c and lipid panel review", status: "upcoming", createdOn: addDays(_today, -33) },
  { id: "FU-2026-0004", patientId: PATIENTS[3 % PATIENTS.length]!.id, doctorId: DOCTORS[2 % DOCTORS.length]!.id, dueDate: addDays(_today, -12), interval: "custom", reason: "Post-operative wound check", status: "completed", createdOn: addDays(_today, -30), notes: "Wound healing well; sutures removed." },
  { id: "FU-2026-0005", patientId: PATIENTS[4 % PATIENTS.length]!.id, doctorId: DOCTORS[1]!.id, dueDate: addDays(_today, 2), interval: "7d", reason: "Repeat chest X-ray after AI-flagged opacity", status: "upcoming", createdOn: addDays(_today, -5) },
  { id: "FU-2026-0006", patientId: PATIENTS[1]!.id, doctorId: DOCTORS[3 % DOCTORS.length]!.id, dueDate: addDays(_today, -20), interval: "15d", reason: "Physiotherapy progress review", status: "cancelled", createdOn: addDays(_today, -35), notes: "Patient relocated." },
  { id: "FU-2026-0007", patientId: PATIENTS[0]!.id, doctorId: DOCTORS[0]!.id, dueDate: addDays(_today, 30), interval: "30d", reason: "Spirometry re-assessment", status: "upcoming", createdOn: _today },
];

export const nextFollowUpId = (existing: number) => `FU-2026-${String(1000 + existing).padStart(4, "0")}`;

/* ---------------- AI usage analytics (mock) ---------------- */

export type AIUsagePoint = { label: string; scans: number; accepted: number; rejected: number; avgConfidence: number };

export const AI_USAGE_DAILY: AIUsagePoint[] = Array.from({ length: 14 }, (_, i) => {
  const scans = 18 + ((i * 7) % 23);
  const accepted = Math.round(scans * (0.62 + ((i % 5) * 0.04)));
  return {
    label: addDays(_today, i - 13).slice(5),
    scans,
    accepted,
    rejected: Math.max(0, Math.round(scans * 0.12) - (i % 3)),
    avgConfidence: Number((0.82 + ((i % 6) * 0.02)).toFixed(2)),
  };
});

export const AI_USAGE_MONTHLY: AIUsagePoint[] = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug"].map((label, i) => {
  const scans = 320 + i * 47;
  return {
    label,
    scans,
    accepted: Math.round(scans * (0.66 + i * 0.01)),
    rejected: Math.round(scans * (0.14 - i * 0.005)),
    avgConfidence: Number((0.84 + i * 0.008).toFixed(2)),
  };
});

export const AI_USAGE_BY_MODULE = AI_MODELS.map((m) => ({
  model: m.name,
  id: m.id,
  scans: m.predictions,
  avgConfidence: m.avgConfidence,
  acceptanceRate: Number((0.58 + (m.accuracy - 0.87) * 2).toFixed(2)),
}));
