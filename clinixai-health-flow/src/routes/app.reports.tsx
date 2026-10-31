import { useMemo, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { FileText, Printer, Download, FileSpreadsheet } from "lucide-react";
import { PageHeader } from "@/components/app-shell/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { useClinix } from "@/lib/store/clinix-store";
import { billTotal, inr, fmtDate, type Appointment, type Bill, type Consultation, type AIReport, type Patient, type Doctor } from "@/lib/mock/domain";
import { toast } from "sonner";

export const Route = createFileRoute("/app/reports")({
  head: () => ({ meta: [{ title: "Reports Center — CliniXAI Admin" }, { name: "robots", content: "noindex" }] }),
  component: ReportsPage,
});

type ReportKey = "appointments" | "patient-registrations" | "doctor-activity" | "consultations" | "billing" | "payments" | "ai-usage";

const REPORTS: { key: ReportKey; title: string; description: string }[] = [
  { key: "appointments", title: "Appointment Report", description: "Appointments across the hospital by date & status." },
  { key: "patient-registrations", title: "Patient Registration Report", description: "New patients registered per period." },
  { key: "doctor-activity", title: "Doctor Activity Report", description: "Appointments & consultations handled per doctor." },
  { key: "consultations", title: "Consultation Report", description: "Consultations with operational status and AI usage." },
  { key: "billing", title: "Billing Report", description: "Bills generated with amount and payment status." },
  { key: "payments", title: "Payment Report", description: "Payments received by method and date." },
  { key: "ai-usage", title: "AI Usage Report", description: "AI analyses generated and doctor review status." },
];

function inRange(date: string, from: string, to: string) {
  if (from && date < from) return false;
  if (to && date > to) return false;
  return true;
}

function ReportsPage() {
  const clinix = useClinix();
  const [active, setActive] = useState<ReportKey>("appointments");
  const [dept, setDept] = useState("All");
  const [status, setStatus] = useState("All");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");

  const { rows, headers, summary } = useMemo(
    () => buildReport(active, clinix, { dept, status, from, to }),
    [active, clinix, dept, status, from, to],
  );

  const report = REPORTS.find((r) => r.key === active)!;

  const exportCsv = () => {
    if (rows.length === 0) { toast.error("No records to export for the current filters."); return; }
    const escape = (v: string | number) => {
      const s = String(v);
      return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
    };
    const csv = [headers.map(escape).join(","), ...rows.map((r) => r.map(escape).join(","))].join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${report.key}-report-${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.appendChild(a); a.click(); a.remove();
    URL.revokeObjectURL(url);
    toast.success("CSV report downloaded");
  };

  const exportPdf = () => {
    if (rows.length === 0) { toast.error("No records to export for the current filters."); return; }
    toast.success("Opening print dialog — choose \"Save as PDF\" as the destination");
    window.setTimeout(() => window.print(), 200);
  };

  const printReport = () => {
    toast.success("Preparing report for printing");
    window.setTimeout(() => window.print(), 150);
  };

  return (
    <div className="space-y-6">
      <PageHeader title="Reports Center" description="Generate operational reports across appointments, billing, doctors, and AI usage." />

      <Card className="print:hidden"><CardContent className="p-4">
        <p className="mb-3 text-xs font-semibold uppercase text-muted-foreground">Report Type</p>
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {REPORTS.map((r) => (
            <button
              key={r.key}
              onClick={() => setActive(r.key)}
              className={`min-h-16 rounded-xl border p-3 text-left transition ${active === r.key ? "border-primary bg-primary/5" : "border-border hover:bg-muted/40"}`}
            >
              <p className="text-sm font-semibold text-foreground">{r.title}</p>
              <p className="mt-1 text-xs text-muted-foreground">{r.description}</p>
            </button>
          ))}
        </div>
      </CardContent></Card>

      <Card className="print:hidden"><CardContent className="grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-4">
        <div><Label htmlFor="rep-from">From</Label><Input id="rep-from" type="date" value={from} onChange={(e) => setFrom(e.target.value)} /></div>
        <div><Label htmlFor="rep-to">To</Label><Input id="rep-to" type="date" value={to} onChange={(e) => setTo(e.target.value)} /></div>
        <div><Label htmlFor="rep-dept">Department</Label>
          <Select value={dept} onValueChange={setDept}>
            <SelectTrigger id="rep-dept"><SelectValue /></SelectTrigger>
            <SelectContent>{["All", ...clinix.departments.map((d) => d.name)].map((d) => <SelectItem key={d} value={d}>{d}</SelectItem>)}</SelectContent>
          </Select>
        </div>
        <div><Label htmlFor="rep-status">Status</Label>
          <Select value={status} onValueChange={setStatus}>
            <SelectTrigger id="rep-status"><SelectValue /></SelectTrigger>
            <SelectContent>{["All","completed","pending","cancelled","paid"].map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
          </Select>
        </div>
      </CardContent></Card>

      <ReportPreview report={report} filters={{ dept, status, from, to }} headers={headers} rows={rows} summary={summary} onCsv={exportCsv} onPdf={exportPdf} onPrint={printReport} />
    </div>
  );
}

function ReportPreview({
  report, filters, headers, rows, summary, onCsv, onPdf, onPrint,
}: {
  report: typeof REPORTS[number];
  filters: { dept: string; status: string; from: string; to: string };
  headers: string[];
  rows: (string | number)[][];
  summary: { label: string; value: string }[];
  onCsv: () => void;
  onPdf: () => void;
  onPrint: () => void;
}) {
  const generated = new Date().toLocaleString("en-IN", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });

  return (
    <Card id="report-printable"><CardContent className="p-0">
      <div className="flex flex-col gap-3 border-b border-border p-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="font-display text-base font-semibold">{report.title}</p>
          <p className="text-xs text-muted-foreground">Generated {generated}</p>
        </div>
        <div className="flex flex-wrap gap-2 print:hidden">
          <Button variant="outline" size="sm" className="min-h-10" onClick={onCsv}><FileSpreadsheet className="mr-1 h-4 w-4" /> CSV</Button>
          <Button variant="outline" size="sm" className="min-h-10" onClick={onPdf}><Download className="mr-1 h-4 w-4" /> PDF</Button>
          <Button variant="outline" size="sm" className="min-h-10" onClick={onPrint}><Printer className="mr-1 h-4 w-4" /> Print</Button>
        </div>
      </div>

      <div className="flex flex-wrap gap-2 border-b border-border p-4 text-xs">
        <Badge variant="outline">Dept: {filters.dept}</Badge>
        <Badge variant="outline">Status: {filters.status}</Badge>
        <Badge variant="outline">From: {filters.from || "—"}</Badge>
        <Badge variant="outline">To: {filters.to || "—"}</Badge>
      </div>

      <div className="grid gap-3 border-b border-border p-4 sm:grid-cols-3">
        {summary.map((s) => (
          <div key={s.label} className="rounded-lg border border-border p-3">
            <p className="text-xs text-muted-foreground">{s.label}</p>
            <p className="font-display text-lg font-bold">{s.value}</p>
          </div>
        ))}
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] text-sm">
          <thead className="bg-muted/40 text-xs uppercase text-muted-foreground">
            <tr>{headers.map((h) => <th key={h} className="p-3 text-left">{h}</th>)}</tr>
          </thead>
          <tbody>
            {rows.slice(0, 12).map((r, i) => (
              <tr key={i} className="border-b border-border">{r.map((c, j) => <td key={j} className="p-3">{c}</td>)}</tr>
            ))}
          </tbody>
        </table>
      </div>
      {rows.length === 0 && <div className="p-6 text-center text-sm text-muted-foreground"><FileText className="mx-auto mb-2 h-6 w-6" /> No records match these filters.</div>}
      {rows.length > 12 && <p className="p-3 text-center text-xs text-muted-foreground">Showing 12 of {rows.length} records — export CSV or PDF for the full report.</p>}
    </CardContent></Card>
  );
}

type Store = ReturnType<typeof useClinix>;

function buildReport(
  key: ReportKey,
  store: Store,
  filters: { dept: string; status: string; from: string; to: string },
): { headers: string[]; rows: (string | number)[][]; summary: { label: string; value: string }[] } {
  const { dept, status, from, to } = filters;
  const patientName = (p?: Patient) => (p ? `${p.firstName} ${p.lastName}` : "-");
  const doctorMatchesDept = (d?: Doctor) => dept === "All" || d?.department === dept;

  if (key === "appointments") {
    const filtered: Appointment[] = store.appointments.filter((a) => {
      const d = store.getDoctor(a.doctorId);
      return inRange(a.date, from, to) && doctorMatchesDept(d) && (status === "All" || a.status === status);
    });
    const rows = filtered.map((a) => {
      const p = store.getPatient(a.patientId); const d = store.getDoctor(a.doctorId);
      return [a.id, patientName(p), d?.name ?? "-", d?.department ?? "-", fmtDate(a.date), a.time, a.status];
    });
    return {
      headers: ["Appt ID", "Patient", "Doctor", "Department", "Date", "Time", "Status"],
      rows,
      summary: [
        { label: "Total", value: String(filtered.length) },
        { label: "Completed", value: String(filtered.filter((a) => a.status === "completed").length) },
        { label: "Cancelled/No-show", value: String(filtered.filter((a) => a.status === "cancelled" || a.status === "no-show").length) },
      ],
    };
  }
  if (key === "patient-registrations") {
    const filtered = store.patients.filter((p) => inRange(p.registeredOn, from, to));
    return {
      headers: ["Patient ID", "Name", "Gender", "Mobile", "Registered"],
      rows: filtered.map((p) => [p.id, patientName(p), p.gender, p.mobile, fmtDate(p.registeredOn)]),
      summary: [
        { label: "Total registered", value: String(filtered.length) },
        { label: "With last visit", value: String(filtered.filter((p) => p.lastVisit).length) },
        { label: "New (period)", value: String(filtered.length) },
      ],
    };
  }
  if (key === "doctor-activity") {
    const doctors = store.doctors.filter((d) => doctorMatchesDept(d));
    return {
      headers: ["Doctor", "Department", "Appointments", "Completed", "Fee"],
      rows: doctors.map((d) => {
        const appts = store.appointments.filter((a) => a.doctorId === d.id && inRange(a.date, from, to) && (status === "All" || a.status === status));
        return [d.name, d.department, appts.length, appts.filter((a) => a.status === "completed").length, inr(d.consultationFee)];
      }),
      summary: [
        { label: "Doctors", value: String(doctors.length) },
        { label: "Total appts", value: String(store.appointments.filter((a) => inRange(a.date, from, to)).length) },
        { label: "Avg fee", value: doctors.length ? inr(Math.round(doctors.reduce((s, d) => s + d.consultationFee, 0) / doctors.length)) : inr(0) },
      ],
    };
  }
  if (key === "consultations") {
    const filtered: Consultation[] = store.consultations.filter((c) => {
      const d = store.getDoctor(c.doctorId);
      return inRange(c.date, from, to) && doctorMatchesDept(d) && (status === "All" || c.status === status);
    });
    return {
      headers: ["Consultation", "Appt", "Doctor", "Date", "Status", "AI", "Follow-Up"],
      rows: filtered.map((c) => {
        const d = store.getDoctor(c.doctorId);
        return [c.id, c.appointmentId, d?.name ?? "-", fmtDate(c.date), c.status, c.aiUsed ? "Yes" : "No", c.followUpRecommended ? "Yes" : "No"];
      }),
      summary: [
        { label: "Total", value: String(filtered.length) },
        { label: "Completed", value: String(filtered.filter((c) => c.status === "completed").length) },
        { label: "AI used", value: String(filtered.filter((c) => c.aiUsed).length) },
      ],
    };
  }
  if (key === "billing") {
    const filtered: Bill[] = store.bills.filter((b) => {
      const d = store.getDoctor(b.doctorId);
      return inRange(b.date, from, to) && doctorMatchesDept(d) && (status === "All" || b.status === status);
    });
    return {
      headers: ["Bill", "Patient", "Doctor", "Date", "Amount", "Status"],
      rows: filtered.map((b) => {
        const p = store.getPatient(b.patientId); const d = store.getDoctor(b.doctorId);
        return [b.id, patientName(p), d?.name ?? "-", fmtDate(b.date), inr(billTotal(b)), b.status];
      }),
      summary: [
        { label: "Total billed", value: inr(filtered.reduce((s, b) => s + billTotal(b), 0)) },
        { label: "Paid", value: inr(filtered.filter((b) => b.status === "paid").reduce((s, b) => s + billTotal(b), 0)) },
        { label: "Pending", value: inr(filtered.filter((b) => b.status === "pending").reduce((s, b) => s + billTotal(b), 0)) },
      ],
    };
  }
  if (key === "payments") {
    const filtered = store.bills.filter((b) => b.status === "paid" && b.paidOn && inRange(b.paidOn, from, to));
    return {
      headers: ["Bill", "Method", "Reference", "Paid On", "Amount"],
      rows: filtered.map((b) => [b.id, b.method ?? "cash", b.reference ?? "—", fmtDate(b.paidOn!), inr(billTotal(b))]),
      summary: [
        { label: "Cash", value: String(filtered.filter((b) => b.method === "cash").length) },
        { label: "UPI", value: String(filtered.filter((b) => b.method === "upi").length) },
        { label: "Card", value: String(filtered.filter((b) => b.method === "card").length) },
      ],
    };
  }
  // ai-usage
  const filtered: AIReport[] = store.aiReports.filter((r) => inRange(r.date, from, to) && (status === "All" || r.status === status));
  return {
    headers: ["Analysis", "Patient", "Doctor", "Image Type", "Date", "Status"],
    rows: filtered.map((r) => [r.id, r.patientId, r.doctorId ? store.getDoctor(r.doctorId)?.name ?? "-" : "-", r.imageType, fmtDate(r.date), r.status]),
    summary: [
      { label: "Total", value: String(filtered.length) },
      { label: "Reviewed", value: String(filtered.filter((r) => r.status === "doctor-reviewed" || r.status === "finalized").length) },
      { label: "Pending", value: String(filtered.filter((r) => r.status === "analysis-completed").length) },
    ],
  };
}
