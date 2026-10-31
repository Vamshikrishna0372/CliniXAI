import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { BarChart3, Calendar } from "lucide-react";
import { PageHeader } from "@/components/app-shell/page-header";
import { ResponsiveGrid } from "@/components/dashboard/cards";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { BarSeries, LineSeries, DonutChart, HBarSeries } from "@/components/dashboard/mini-chart";
import { useClinix } from "@/lib/store/clinix-store";
import { billTotal, inr } from "@/lib/mock/domain";
import { AI_USAGE_DAILY, AI_USAGE_MONTHLY, AI_USAGE_BY_MODULE } from "@/lib/mock/ai-models";

export const Route = createFileRoute("/app/analytics")({
  head: () => ({ meta: [{ title: "Analytics — CliniXAI Admin" }, { name: "robots", content: "noindex" }] }),
  component: AnalyticsPage,
});

function AnalyticsPage() {
  const clinix = useClinix();
  const [aiRange, setAiRange] = useState<"daily" | "monthly">("daily");
  const [timeRangeDays, setTimeRangeDays] = useState<number>(7);

  const { appointments, bills, patients, doctors, departments, aiReports } = clinix;

  // 1. Time series calculations based on live appointments
  const days = Array.from({ length: timeRangeDays }, (_, i) => {
    const d = new Date();
    d.setDate(d.getDate() - (timeRangeDays - 1 - i));
    return d.toISOString().slice(0, 10);
  });

  const apptSeries = days.map((day) => ({
    label: new Date(day + "T00:00:00").toLocaleDateString("en-IN", { weekday: "short", day: "numeric" }),
    value: appointments.filter((a) => a.date === day).length,
  }));

  const registrationsSeries = days.map((day) => ({
    label: new Date(day + "T00:00:00").toLocaleDateString("en-IN", { weekday: "short" }),
    value: patients.filter((p) => p.registeredOn === day).length,
  }));

  const aiSeries = days.map((day) => ({
    label: new Date(day + "T00:00:00").toLocaleDateString("en-IN", { weekday: "short" }),
    value: aiReports.filter((r) => r.date === day).length,
  }));

  // 2. Status mix from live appointments
  const statusCounts: Record<string, number> = {};
  appointments.forEach((a) => {
    statusCounts[a.status] = (statusCounts[a.status] || 0) + 1;
  });
  const apptStatusData = Object.entries(statusCounts).map(([st, count]) => ({
    label: st.replace("-", " ").toUpperCase(),
    value: count,
  }));

  // 3. Appointments by department
  const deptApptCounts: Record<string, number> = {};
  appointments.forEach((a) => {
    const doc = doctors.find((d) => d.id === a.doctorId);
    const deptName = doc ? doc.department : "Unassigned";
    deptApptCounts[deptName] = (deptApptCounts[deptName] || 0) + 1;
  });
  const apptsByDeptData = Object.entries(deptApptCounts).map(([name, val]) => ({
    label: name,
    value: val,
  }));

  // 4. Appointments by doctor
  const docApptData = doctors.map((d) => ({
    label: d.name.replace("Dr. ", ""),
    value: appointments.filter((a) => a.doctorId === d.id).length,
  }));

  // 5. Billing & Revenue metrics
  const paidTotal = bills
    .filter((b) => b.status === "paid")
    .reduce((sum, b) => sum + billTotal(b), 0);
  const pendingTotal = bills
    .filter((b) => b.status === "pending" || (b.status as string) === "unpaid" || (b.status as string) === "issued")
    .reduce((sum, b) => sum + billTotal(b), 0);

  const deptRevCounts: Record<string, number> = {};
  bills.forEach((b) => {
    const doc = doctors.find((d) => d.id === b.doctorId);
    const deptName = doc ? doc.department : "General Medicine";
    deptRevCounts[deptName] = (deptRevCounts[deptName] || 0) + billTotal(b);
  });
  const revenueByDeptData = Object.entries(deptRevCounts).map(([name, val]) => ({
    label: name,
    value: val,
  }));

  const paymentMethodsCount: Record<string, number> = { cash: 0, upi: 0, card: 0 };
  bills.forEach((b) => {
    if (b.method) {
      paymentMethodsCount[b.method] = (paymentMethodsCount[b.method] || 0) + 1;
    }
  });
  const paymentMixData = Object.entries(paymentMethodsCount).map(([m, count]) => ({
    label: m.toUpperCase(),
    value: count,
  }));

  // 6. AI usage metrics
  const deptAiCounts: Record<string, number> = {};
  aiReports.forEach((r) => {
    const doc = r.doctorId ? doctors.find((d) => d.id === r.doctorId) : undefined;
    const deptName = doc ? doc.department : "Radiology";
    deptAiCounts[deptName] = (deptAiCounts[deptName] || 0) + 1;
  });
  const aiByDeptData = Object.entries(deptAiCounts).map(([name, val]) => ({
    label: name,
    value: val,
  }));

  const noShowCount = appointments.filter((a) => a.status === "no-show" || a.status === "cancelled").length;
  const noShowRate = Math.round((noShowCount / Math.max(1, appointments.length)) * 100);

  const aiUsageSeries = aiRange === "daily" ? AI_USAGE_DAILY : AI_USAGE_MONTHLY;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Hospital Analytics"
        description="Live operational, financial, and clinical AI analytics aggregated from MongoDB."
        status={{ label: "Live MongoDB Data", tone: "success" }}
      />

      {/* Date Range Selector Bar */}
      <div className="flex items-center gap-2 rounded-xl border border-border bg-card p-3">
        <Calendar className="h-4 w-4 text-muted-foreground" />
        <span className="text-xs font-semibold text-muted-foreground uppercase">Range:</span>
        <Button
          size="sm"
          variant={timeRangeDays === 7 ? "default" : "outline"}
          onClick={() => setTimeRangeDays(7)}
        >
          Last 7 Days
        </Button>
        <Button
          size="sm"
          variant={timeRangeDays === 30 ? "default" : "outline"}
          onClick={() => setTimeRangeDays(30)}
        >
          Last 30 Days
        </Button>
      </div>

      <Section title="Appointment analytics" subtitle="Volume, distribution, and workflow health.">
        <ResponsiveGrid cols={{ base: 1, lg: 2 }}>
          <ChartCard title={`Appointments over time (${timeRangeDays} days)`}>
            <LineSeries data={apptSeries} />
          </ChartCard>
          <ChartCard title="Status distribution">
            <DonutChart data={apptStatusData.length > 0 ? apptStatusData : [{ label: "No data", value: 1 }]} />
          </ChartCard>
          <ChartCard title="Appointments by department">
            <BarSeries data={apptsByDeptData.length > 0 ? apptsByDeptData : [{ label: "General", value: 0 }]} />
          </ChartCard>
          <ChartCard title="Appointments by doctor">
            <HBarSeries data={docApptData.length > 0 ? docApptData : [{ label: "Unassigned", value: 0 }]} />
          </ChartCard>
        </ResponsiveGrid>
        <StatRow items={[
          { label: "Total appointments", value: String(appointments.length) },
          { label: "Cancellation / No-show rate", value: `${noShowRate}%` },
          { label: "Active departments", value: String(departments.length) },
        ]} />
      </Section>

      <Section title="Patient analytics" subtitle="Registrations and visit patterns.">
        <ResponsiveGrid cols={{ base: 1, lg: 2 }}>
          <ChartCard title={`New registrations (${timeRangeDays} days)`}>
            <LineSeries data={registrationsSeries} />
          </ChartCard>
          <ChartCard title="Returning vs new">
            <DonutChart data={[
              { label: "Active Patients", value: patients.filter((p) => p.lastVisit).length },
              { label: "New Patients", value: patients.filter((p) => !p.lastVisit).length || patients.length },
            ]} />
          </ChartCard>
        </ResponsiveGrid>
      </Section>

      <Section title="Doctor analytics" subtitle="Operational metrics per doctor.">
        <ChartCard title="Appointments handled by doctor">
          <HBarSeries data={docApptData} />
        </ChartCard>
      </Section>

      <Section title="Billing analytics" subtitle="Revenue distribution and payment mix.">
        <ResponsiveGrid cols={{ base: 1, lg: 2 }}>
          <ChartCard title="Revenue by department">
            <HBarSeries data={revenueByDeptData.length > 0 ? revenueByDeptData : [{ label: "General", value: 0 }]} formatValue={(v) => inr(v)} />
          </ChartCard>
          <ChartCard title="Payment method mix">
            <DonutChart data={paymentMixData} />
          </ChartCard>
        </ResponsiveGrid>
        <StatRow items={[
          { label: "Collected revenue", value: inr(paidTotal) },
          { label: "Outstanding balance", value: inr(pendingTotal) },
          { label: "Total bills", value: String(bills.length) },
        ]} />
      </Section>

      <Section title="AI usage analytics" subtitle="Analyses generated and doctor review status.">
        <ResponsiveGrid cols={{ base: 1, lg: 2 }}>
          <ChartCard title={`AI analyses over time (${timeRangeDays} days)`}>
            <LineSeries data={aiSeries} />
          </ChartCard>
          <ChartCard title="AI usage by department">
            <HBarSeries data={aiByDeptData.length > 0 ? aiByDeptData : [{ label: "Radiology", value: 0 }]} />
          </ChartCard>
        </ResponsiveGrid>
        <StatRow items={[
          { label: "Total AI analyses", value: String(aiReports.length) },
          { label: "Doctor reviewed", value: String(aiReports.filter((r) => r.status === "doctor-reviewed" || r.status === "finalized").length) },
          { label: "Pending review", value: String(aiReports.filter((r) => r.status === "analysis-completed").length) },
        ]} />
      </Section>

      <Section title="AI model usage analytics" subtitle="Scan volume, acceptance rate and confidence trend across registered AI models.">
        <div className="flex items-center gap-2">
          <Button size="sm" variant={aiRange === "daily" ? "default" : "outline"} onClick={() => setAiRange("daily")}>Daily</Button>
          <Button size="sm" variant={aiRange === "monthly" ? "default" : "outline"} onClick={() => setAiRange("monthly")}>Monthly</Button>
        </div>
        <ResponsiveGrid cols={{ base: 1, lg: 2 }}>
          <ChartCard title={`Scans over time (${aiRange})`}>
            <LineSeries data={aiUsageSeries.map((d) => ({ label: d.label, value: d.scans }))} />
          </ChartCard>
          <ChartCard title="Accepted vs rejected">
            <DonutChart data={[
              { label: "Accepted", value: aiUsageSeries.reduce((s, d) => s + d.accepted, 0) },
              { label: "Rejected", value: aiUsageSeries.reduce((s, d) => s + d.rejected, 0) },
            ]} />
          </ChartCard>
          <ChartCard title="Average confidence trend">
            <LineSeries data={aiUsageSeries.map((d) => ({ label: d.label, value: Math.round(d.avgConfidence * 100) }))} />
          </ChartCard>
          <ChartCard title="Usage by model">
            <HBarSeries data={AI_USAGE_BY_MODULE.map((m) => ({ label: m.model, value: m.scans }))} />
          </ChartCard>
        </ResponsiveGrid>
        <StatRow items={[
          { label: "Total scans", value: String(aiUsageSeries.reduce((s, d) => s + d.scans, 0)) },
          { label: "Avg confidence", value: `${Math.round((aiUsageSeries.reduce((s, d) => s + d.avgConfidence, 0) / aiUsageSeries.length) * 100)}%` },
          { label: "Registered models", value: String(AI_USAGE_BY_MODULE.length) },
        ]} />
      </Section>
    </div>
  );
}

function Section({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <section className="space-y-3">
      <div className="flex items-center gap-2">
        <BarChart3 className="h-4 w-4 text-primary" />
        <h2 className="font-display text-base font-semibold text-foreground">{title}</h2>
      </div>
      {subtitle && <p className="text-xs text-muted-foreground">{subtitle}</p>}
      {children}
    </section>
  );
}

function ChartCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Card>
      <CardContent className="p-5">
        <p className="mb-3 text-sm font-semibold text-foreground">{title}</p>
        {children}
      </CardContent>
    </Card>
  );
}

function StatRow({ items }: { items: { label: string; value: string }[] }) {
  return (
    <div className="grid gap-3 sm:grid-cols-3">
      {items.map((s) => (
        <div key={s.label} className="rounded-xl border border-border bg-card p-3">
          <p className="text-xs text-muted-foreground">{s.label}</p>
          <p className="mt-1 font-display text-lg font-bold text-foreground">{s.value}</p>
        </div>
      ))}
    </div>
  );
}
