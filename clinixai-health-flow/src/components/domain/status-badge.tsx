import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { AppointmentStatus, BillingStatus, AIStatus, DocumentStatus } from "@/lib/mock/domain";

type Tone = "neutral" | "info" | "warn" | "success" | "danger" | "muted";

const TONE: Record<Tone, string> = {
  neutral: "bg-muted text-foreground border-transparent",
  info: "bg-primary/10 text-primary border-transparent",
  warn: "bg-warning/15 text-warning border-transparent",
  success: "bg-success/15 text-success border-transparent",
  danger: "bg-error/15 text-error border-transparent",
  muted: "bg-muted text-muted-foreground border-transparent",
};

const APT: Record<string, { label: string; tone: Tone }> = {
  scheduled: { label: "Scheduled", tone: "neutral" },
  confirmed: { label: "Confirmed", tone: "info" },
  "checked-in": { label: "Checked In", tone: "info" },
  checked_in: { label: "Checked In", tone: "info" },
  "in-queue": { label: "In Queue", tone: "warn" },
  in_queue: { label: "In Queue", tone: "warn" },
  waiting: { label: "In Queue", tone: "warn" },
  "in-consultation": { label: "In Consultation", tone: "warn" },
  in_consultation: { label: "In Consultation", tone: "warn" },
  "in-progress": { label: "In Consultation", tone: "warn" },
  in_progress: { label: "In Consultation", tone: "warn" },
  completed: { label: "Completed", tone: "success" },
  cancelled: { label: "Cancelled", tone: "danger" },
  "no-show": { label: "No Show", tone: "muted" },
  no_show: { label: "No Show", tone: "muted" },
};
const BILL: Record<string, { label: string; tone: Tone }> = {
  pending: { label: "Pending", tone: "warn" },
  unpaid: { label: "Unpaid", tone: "danger" },
  issued: { label: "Issued", tone: "warn" },
  partially_paid: { label: "Partially Paid", tone: "info" },
  "partially-paid": { label: "Partially Paid", tone: "info" },
  paid: { label: "Paid", tone: "success" },
  cancelled: { label: "Cancelled", tone: "danger" },
  failed: { label: "Failed", tone: "danger" },
  refunded: { label: "Refunded", tone: "muted" },
  draft: { label: "Draft", tone: "neutral" },
};
const AI: Record<string, { label: string; tone: Tone }> = {
  uploaded: { label: "Uploaded", tone: "neutral" },
  processing: { label: "Processing", tone: "info" },
  "analysis-completed": { label: "Analysis Complete", tone: "warn" },
  awaiting_review: { label: "Awaiting Review", tone: "warn" },
  "doctor-reviewed": { label: "Doctor Reviewed", tone: "info" },
  reviewed: { label: "Reviewed", tone: "info" },
  finalized: { label: "Finalized", tone: "success" },
};
const DOC: Record<string, { label: string; tone: Tone }> = {
  uploaded: { label: "Uploaded", tone: "neutral" },
  processing: { label: "Processing", tone: "info" },
  available: { label: "Available", tone: "success" },
  verified: { label: "Verified", tone: "success" },
  failed: { label: "Failed", tone: "danger" },
};

export function AppointmentBadge({ status, className }: { status?: string; className?: string }) {
  const normStatus = (status || "").toLowerCase().replace(/_/g, "-");
  const s = APT[normStatus] || APT[status || ""] || { label: status || "Scheduled", tone: "neutral" as Tone };
  return <Badge variant="outline" className={cn(TONE[s.tone || "neutral"], "font-medium", className)}>{s.label}</Badge>;
}

export function BillingBadge({ status, className }: { status?: string; className?: string }) {
  const normStatus = (status || "").toLowerCase();
  const s = BILL[normStatus] || BILL[status || ""] || { label: status || "Pending", tone: "warn" as Tone };
  return <Badge variant="outline" className={cn(TONE[s.tone || "warn"], "font-medium", className)}>{s.label}</Badge>;
}

export function AIBadge({ status, className }: { status?: string; className?: string }) {
  const normStatus = (status || "").toLowerCase().replace(/_/g, "-");
  const s = AI[normStatus] || AI[status || ""] || { label: status || "Analysis Complete", tone: "info" as Tone };
  return <Badge variant="outline" className={cn(TONE[s.tone || "info"], "font-medium", className)}>{s.label}</Badge>;
}

export function DocumentBadge({ status, className }: { status?: string; className?: string }) {
  const normStatus = (status || "").toLowerCase();
  const s = DOC[normStatus] || DOC[status || ""] || { label: status || "Available", tone: "success" as Tone };
  return <Badge variant="outline" className={cn(TONE[s.tone || "success"], "font-medium", className)}>{s.label}</Badge>;
}

