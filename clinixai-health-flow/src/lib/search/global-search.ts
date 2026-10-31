import type { ClinixState } from "@/lib/store/clinix-store";
import { inr, billTotal } from "@/lib/mock/domain";
import { canAccessSection, type Role } from "@/lib/roles";

export type SearchGroup =
  | "Patients"
  | "Doctors"
  | "Hospital Staff"
  | "Departments"
  | "Appointments"
  | "Consultations"
  | "Medical Records"
  | "Prescriptions"
  | "Bills"
  | "AI Reports"
  | "Notifications"
  | "Documents";

export type SearchResult = {
  id: string;
  group: SearchGroup;
  title: string;
  subtitle: string;
  to: string;
  /** Concatenated haystack used for matching. */
  keywords: string;
};

const GROUP_SECTION: Record<SearchGroup, string> = {
  Patients: "patients",
  Doctors: "doctors",
  "Hospital Staff": "staff",
  Departments: "departments",
  Appointments: "appointments",
  Consultations: "consultations",
  "Medical Records": "medical-records",
  Prescriptions: "prescriptions",
  Bills: "bills",
  "AI Reports": "ai-reports",
  Notifications: "notifications",
  Documents: "documents",
};

export const SEARCH_GROUP_ORDER: SearchGroup[] = [
  "Patients", "Doctors", "Hospital Staff", "Departments", "Appointments",
  "Consultations", "Medical Records", "Prescriptions", "Bills", "AI Reports",
  "Documents", "Notifications",
];

/** Build the full searchable index for a role, honouring role isolation. */
export function buildSearchIndex(s: ClinixState, role: Role, currentUserId?: string): SearchResult[] {
  const out: SearchResult[] = [];
  if (!s) return out;

  const isPatient = role === "patient";
  const mine = (pid?: string) => !isPatient || !currentUserId || pid === currentUserId;
  const allow = (g: SearchGroup) => canAccessSection(role, GROUP_SECTION[g]);

  const doctors = Array.isArray(s.doctors) ? s.doctors : [];
  const patients = Array.isArray(s.patients) ? s.patients : [];
  const staff = Array.isArray(s.staff) ? s.staff : [];
  const departments = Array.isArray(s.departments) ? s.departments : [];
  const appointments = Array.isArray(s.appointments) ? s.appointments : [];
  const consultations = Array.isArray(s.consultations) ? s.consultations : [];
  const prescriptions = Array.isArray(s.prescriptions) ? s.prescriptions : [];
  const bills = Array.isArray(s.bills) ? s.bills : [];
  const aiReports = Array.isArray(s.aiReports) ? s.aiReports : [];
  const documents = Array.isArray(s.documents) ? s.documents : [];
  const notifications = Array.isArray(s.notifications) ? s.notifications : [];

  const doctorName = (id?: string) => {
    if (!id) return "Unassigned";
    const d = doctors.find((x) => x && x.id === id);
    return d?.name ?? "Unassigned";
  };

  const patientName = (id?: string) => {
    if (!id) return "Patient";
    const p = patients.find((x) => x && x.id === id);
    if (!p) return id;
    const fn = (p.firstName ?? "").trim();
    const ln = (p.lastName ?? "").trim();
    return `${fn} ${ln}`.trim() || id;
  };

  /* Staff have no Patients directory route, but they need to find patients
     for registration/check-in — route those results to the check-in desk. */
  const patientsTo = allow("Patients") ? "/app/patients" : "/app/check-in";
  const push = (r: SearchResult) => {
    if (allow(r.group) || (r.group === "Patients" && role === "staff")) out.push(r);
  };

  if (!isPatient) {
    for (const p of patients) {
      if (!p) continue;
      const fn = p.firstName ?? "";
      const ln = p.lastName ?? "";
      const id = p.id ?? "";
      const mobile = p.mobile ?? "";
      const email = p.email ?? "";
      const city = p.city ?? "";
      const bg = p.bloodGroup ?? "";
      const conds = Array.isArray(p.conditions) ? p.conditions.join(" ") : "";
      push({
        id: `pat-${id}`, group: "Patients",
        title: `${fn} ${ln}`.trim() || id || "Patient",
        subtitle: `${id} • ${mobile} • ${bg}`,
        to: patientsTo,
        keywords: `${fn} ${ln} ${id} ${mobile} ${email} ${city} ${bg} ${conds}`,
      });
    }

    for (const st of staff) {
      if (!st) continue;
      const fn = st.firstName ?? "";
      const ln = st.lastName ?? "";
      const id = st.id ?? "";
      const email = st.email ?? "";
      const mobile = st.mobile ?? "";
      const dept = st.department ?? "";
      const desk = st.desk ?? "";
      const status = st.status ?? "";
      push({
        id: `staff-${id}`, group: "Hospital Staff",
        title: `${fn} ${ln}`.trim() || id || "Staff",
        subtitle: `${dept} • ${desk} • ${status}`,
        to: "/app/staff",
        keywords: `${fn} ${ln} ${id} ${email} ${mobile} ${dept} ${desk}`,
      });
    }

    for (const d of departments) {
      if (!d) continue;
      const id = d.id ?? "";
      const name = d.name ?? "";
      const code = d.code ?? "";
      const status = d.status ?? "";
      const desc = d.description ?? "";
      push({
        id: `dept-${id}`, group: "Departments",
        title: name || id || "Department",
        subtitle: `${code} • ${status}`,
        to: "/app/departments",
        keywords: `${name} ${code} ${desc}`,
      });
    }
  }

  for (const d of doctors) {
    if (!d) continue;
    const id = d.id ?? "";
    const name = d.name ?? "";
    const spec = d.specialization ?? "";
    const dept = d.department ?? "";
    const qual = d.qualification ?? "";
    const langs = Array.isArray(d.languages) ? d.languages.join(" ") : "";
    push({
      id: `doc-${id}`, group: "Doctors",
      title: name || id || "Doctor",
      subtitle: `${spec} • ${dept}`,
      to: `/app/doctors/${id}`,
      keywords: `${name} ${id} ${spec} ${dept} ${qual} ${langs}`,
    });
  }

  for (const a of appointments) {
    if (!a || !mine(a.patientId)) continue;
    const id = a.id ?? "";
    const pName = patientName(a.patientId);
    const dName = doctorName(a.doctorId);
    const date = a.date ?? "";
    const time = a.time ?? "";
    const status = a.status ?? "";
    const reason = a.reason ?? "";
    const token = a.token ?? "";
    push({
      id: `apt-${id}`, group: "Appointments",
      title: `${pName} — ${dName}`,
      subtitle: `${date} ${time} • ${status}`,
      to: `/app/appointments/${id}`,
      keywords: `${id} ${pName} ${dName} ${reason} ${status} ${date} ${token}`,
    });
  }

  for (const c of consultations) {
    if (!c || !mine(c.patientId)) continue;
    const id = c.id ?? "";
    const pName = patientName(c.patientId);
    const dName = doctorName(c.doctorId);
    const date = c.date ?? "";
    const status = c.status ?? "";
    push({
      id: `cons-${id}`, group: "Consultations",
      title: `${pName} — consultation`,
      subtitle: `${date} • ${status}`,
      to: `/app/consultations/${id}`,
      keywords: `${id} ${pName} ${dName} ${status} ${date}`,
    });
  }

  for (const rx of prescriptions) {
    if (!rx || !mine(rx.patientId)) continue;
    const id = rx.id ?? "";
    const dx = rx.diagnosis ?? "";
    const pName = patientName(rx.patientId);
    const dName = doctorName(rx.doctorId);
    const date = rx.date ?? "";
    const meds = Array.isArray(rx.medications)
      ? rx.medications.map((m) => m?.name ?? "").join(" ")
      : "";
    push({
      id: `rx-${id}`, group: "Prescriptions",
      title: dx || "Prescription",
      subtitle: `${pName} • ${date}`,
      to: `/app/prescriptions/${id}`,
      keywords: `${id} ${dx} ${pName} ${dName} ${meds}`,
    });
    push({
      id: `mr-${id}`, group: "Medical Records",
      title: `${dx} record`,
      subtitle: `${pName} • ${date}`,
      to: "/app/medical-records",
      keywords: `${id} record ${dx} ${pName} ${date}`,
    });
  }

  for (const b of bills) {
    if (!b || !mine(b.patientId)) continue;
    const id = b.id ?? "";
    const pName = patientName(b.patientId);
    const status = b.status ?? "";
    const method = b.method ?? "";
    const ref = b.reference ?? "";
    const items = Array.isArray(b.items)
      ? b.items.map((i) => i?.label ?? "").join(" ")
      : "";
    push({
      id: `bill-${id}`, group: "Bills",
      title: `${id} — ${inr(billTotal(b))}`,
      subtitle: `${pName} • ${status}`,
      to: role === "patient" ? `/app/bills/${id}` : `/app/billing/${id}`,
      keywords: `${id} ${pName} ${status} ${method} ${ref} ${items}`,
    });
  }

  for (const r of aiReports) {
    if (!r || !mine(r.patientId)) continue;
    const id = r.id ?? "";
    const pred = r.prediction ?? r.imageType ?? "";
    const imgType = r.imageType ?? "";
    const status = r.status ?? "";
    const pName = patientName(r.patientId);
    const ver = r.modelVersion ?? "";
    push({
      id: `ai-${id}`, group: "AI Reports",
      title: pred || "AI Report",
      subtitle: `${pName} • ${status}`,
      to: role === "patient" ? `/app/ai-reports/${id}` : `/app/ai-analysis/${id}`,
      keywords: `${id} ${imgType} ${pred} ${status} ${pName} ${ver}`,
    });
  }

  for (const d of documents) {
    if (!d || !mine(d.patientId)) continue;
    const id = d.id ?? "";
    const name = d.name ?? "";
    const cat = d.category ?? "";
    const type = d.fileType ?? "";
    const status = d.status ?? "";
    const pName = patientName(d.patientId);
    push({
      id: `docm-${id}`, group: "Documents",
      title: name || "Document",
      subtitle: `${cat} • ${type} • ${status}`,
      to: "/app/documents",
      keywords: `${id} ${name} ${cat} ${type} ${pName}`,
    });
  }

  for (const n of notifications) {
    if (!n) continue;
    const id = n.id ?? "";
    const title = n.title ?? "";
    const body = n.body ?? "";
    const time = n.time ?? "";
    const cat = n.category ?? "";
    push({
      id: `notif-${id}`, group: "Notifications",
      title: title || "Notification",
      subtitle: `${body} • ${time}`,
      to: "/app/notifications",
      keywords: `${title} ${body} ${cat}`,
    });
  }

  return out;
}

/** Rank: prefix match on title > word-start in title > substring anywhere. */
export function searchIndex(index: SearchResult[], query: string, limitPerGroup = 5): SearchResult[] {
  const q = query.trim().toLowerCase();
  if (!q) return [];
  const scored: { r: SearchResult; score: number }[] = [];
  for (const r of index) {
    const title = r.title.toLowerCase();
    const hay = `${title} ${r.subtitle} ${r.keywords}`.toLowerCase();
    const idx = hay.indexOf(q);
    if (idx === -1) continue;
    let score = 10;
    if (title.startsWith(q)) score = 100;
    else if (title.includes(q)) score = 60;
    else if (new RegExp(`\\b${q.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}`).test(hay)) score = 30;
    scored.push({ r, score });
  }
  scored.sort((a, b) => b.score - a.score || a.r.title.localeCompare(b.r.title));

  const perGroup = new Map<SearchGroup, number>();
  const out: SearchResult[] = [];
  for (const { r } of scored) {
    const n = perGroup.get(r.group) ?? 0;
    if (n >= limitPerGroup) continue;
    perGroup.set(r.group, n + 1);
    out.push(r);
  }
  return out;
}

/** Split a string into [before, match, after] segments for highlighting. */
export function highlightParts(text: string, query: string): { text: string; match: boolean }[] {
  const q = query.trim();
  if (!q) return [{ text, match: false }];
  const i = text.toLowerCase().indexOf(q.toLowerCase());
  if (i === -1) return [{ text, match: false }];
  return [
    { text: text.slice(0, i), match: false },
    { text: text.slice(i, i + q.length), match: true },
    { text: text.slice(i + q.length), match: false },
  ].filter((p) => p.text.length > 0);
}
