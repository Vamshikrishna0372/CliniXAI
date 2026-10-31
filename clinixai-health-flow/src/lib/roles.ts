import {
  LayoutDashboard, Users, UserCog, Stethoscope, Calendar, ClipboardList, Brain,
  History, Pill, CalendarClock, FileText, Bell, User, Settings, Building2,
  Activity, ReceiptText, BarChart3, ShieldAlert, UserPlus, LogIn as CheckIn,
  ListOrdered, QrCode, FolderOpen, Cpu, Trash2, CalendarDays,
} from "lucide-react";

export type Role = "admin" | "doctor" | "staff" | "patient";

export const ROLE_LABEL: Record<Role, string> = {
  admin: "Hospital Admin",
  doctor: "Doctor",
  staff: "Hospital Staff",
  patient: "Patient",
};

export type NavItem = {
  title: string;
  slug: string;
  icon: React.ComponentType<{ className?: string }>;
  group?: string;
};

const dash = (title = "Dashboard"): NavItem => ({ title, slug: "", icon: LayoutDashboard });

export const NAV_BY_ROLE: Record<Role, NavItem[]> = {
  admin: [
    dash("Hospital Overview"),
    { title: "Doctors", slug: "doctors", icon: Stethoscope, group: "People" },
    { title: "Hospital Staff", slug: "staff", icon: UserCog, group: "People" },
    { title: "Patients", slug: "patients", icon: Users, group: "People" },
    { title: "User Accounts", slug: "users", icon: Users, group: "People" },
    { title: "Departments", slug: "departments", icon: Building2, group: "Structure" },
    { title: "Appointments", slug: "appointments", icon: Calendar, group: "Operations" },
    { title: "Consultations", slug: "consultations", icon: ClipboardList, group: "Operations" },
    { title: "Billing", slug: "billing", icon: ReceiptText, group: "Financial" },
    { title: "AI Insights", slug: "ai-insights", icon: Brain, group: "Intelligence" },
    { title: "AI Models", slug: "ai-models", icon: Cpu, group: "Intelligence" },
    { title: "Reports", slug: "reports", icon: FileText, group: "Intelligence" },
    { title: "Analytics", slug: "analytics", icon: BarChart3, group: "Intelligence" },
    { title: "Activity Logs", slug: "activity-logs", icon: ShieldAlert, group: "Administration" },
    { title: "Recycle Bin", slug: "trash", icon: Trash2, group: "Administration" },
    { title: "Notifications", slug: "notifications", icon: Bell, group: "Administration" },
    { title: "Hospital Settings", slug: "settings", icon: Settings, group: "Administration" },
    { title: "Profile", slug: "profile", icon: User, group: "Administration" },
  ],
  doctor: [
    dash(),
    { title: "Appointments", slug: "appointments", icon: Calendar },
    { title: "Calendar", slug: "calendar", icon: CalendarDays },
    { title: "My Patients", slug: "patients", icon: Users },
    { title: "Consultations", slug: "consultations", icon: ClipboardList },
    { title: "AI Analysis", slug: "ai-analysis", icon: Brain, group: "AI" },
    { title: "AI History", slug: "ai-history", icon: History, group: "AI" },
    { title: "Prescriptions", slug: "prescriptions", icon: Pill },
    { title: "Follow-Ups", slug: "follow-ups", icon: CalendarClock },
    { title: "Medical Records", slug: "medical-records", icon: FileText },
    { title: "Notifications", slug: "notifications", icon: Bell, group: "Account" },
    { title: "Profile", slug: "profile", icon: User, group: "Account" },
  ],
  staff: [
    dash(),
    { title: "Patients", slug: "patients", icon: Users },
    { title: "Patient Registration", slug: "patient-registration", icon: UserPlus },
    { title: "Appointments", slug: "appointments", icon: Calendar },
    { title: "Patient Check-In", slug: "check-in", icon: CheckIn },
    { title: "Queue Management", slug: "queue", icon: ListOrdered },
    { title: "Billing", slug: "billing", icon: ReceiptText },
    { title: "Receipts", slug: "receipts", icon: FileText },
    { title: "Documents", slug: "documents", icon: FolderOpen },
    { title: "Notifications", slug: "notifications", icon: Bell, group: "Account" },
    { title: "Profile", slug: "profile", icon: User, group: "Account" },
  ],
  patient: [
    dash(),
    { title: "Find Doctor", slug: "doctors", icon: Stethoscope },
    { title: "Book Appointment", slug: "book", icon: Calendar },
    { title: "My Appointments", slug: "appointments", icon: CalendarClock },
    { title: "Medical Records", slug: "medical-records", icon: FileText },
    { title: "Medical Timeline", slug: "timeline", icon: Activity },
    { title: "Documents", slug: "documents", icon: FolderOpen },
    { title: "AI Reports", slug: "ai-reports", icon: Brain, group: "Insights" },
    { title: "Prescriptions", slug: "prescriptions", icon: Pill },
    { title: "Bills & Receipts", slug: "bills", icon: ReceiptText },
    { title: "QR Health Card", slug: "qr-card", icon: QrCode },
    { title: "Notifications", slug: "notifications", icon: Bell, group: "Account" },
    { title: "Profile", slug: "profile", icon: User, group: "Account" },
    { title: "Settings", slug: "settings", icon: Settings, group: "Account" },
  ],
};

export function findNavItem(role: Role, slug: string): NavItem | undefined {
  return NAV_BY_ROLE[role].find((n) => n.slug === slug);
}

export function titleForSection(role: Role, slug: string): string {
  return findNavItem(role, slug)?.title ?? "Not found";
}

/* =================================================================
 * Role isolation — which /app/* sections each role may open.
 * Sidebar slugs are always allowed; the extras below cover detail
 * routes and secondary screens that are not in the sidebar.
 * ================================================================= */
const EXTRA_ALLOWED: Record<Role, string[]> = {
  admin: ["settings", "profile", "notifications", "receipts", "bills", "reports", "activity-logs", "ai-models", "trash", "ai-analysis", "calendar", "users"],
  doctor: ["consultations", "ai-analysis", "ai-history", "prescriptions", "medical-records", "settings", "patients", "follow-ups", "calendar", "documents", "timeline"],
  staff: ["patients", "billing", "receipts", "documents", "settings", "queue", "check-in", "patient-registration", "appointments", "book", "calendar", "timeline"],
  patient: ["book", "doctors", "appointments", "medical-records", "timeline", "ai-reports", "prescriptions", "bills", "qr-card", "settings", "profile", "notifications", "documents", "ai-analysis"],
};

export function canAccessSection(role: Role, slug: string): boolean {
  if (!slug) return true;
  const base = slug.split("/")[0] ?? "";
  if (NAV_BY_ROLE[role].some((n) => n.slug === base)) return true;
  return (EXTRA_ALLOWED[role] ?? []).includes(base);
}
