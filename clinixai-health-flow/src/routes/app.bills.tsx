import { useMemo, useState, useEffect } from "react";
import { createFileRoute, Link, Outlet, useMatch } from "@tanstack/react-router";
import { ChevronRight, ReceiptText, RefreshCw, AlertCircle } from "lucide-react";
import { PageHeader } from "@/components/app-shell/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { BillingBadge } from "@/components/domain/status-badge";
import { EmptyState } from "@/components/dashboard/states";
import { inr, fmtDate } from "@/lib/mock/domain";
import { apiClient } from "@/lib/api-client";

export const Route = createFileRoute("/app/bills")({
  head: () => ({ meta: [{ title: "My Bills & Receipts — CliniXAI" }, { name: "robots", content: "noindex" }] }),
  component: BillsPage,
});

interface BillSummary {
  bill_id: string;
  patient_id: string;
  appointment_id?: string;
  consultation_id?: string;
  grand_total: number;
  total_amount?: number;
  amount_paid: number;
  paid_amount?: number;
  balance_due: number;
  balance_amount?: number;
  status: string;
  created_at: string;
}

function BillsPage() {
  const isDetail = useMatch({ from: "/app/bills/$id", shouldThrow: false });
  const [bills, setBills] = useState<BillSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<"pending" | "paid" | "all">("all");

  const fetchBills = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await apiClient.billing.list({ page_size: 100 });
      setBills(res?.data || []);
    } catch (err: any) {
      setError(err?.message || "Failed to load bills from clinical server.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchBills();
  }, []);

  const filtered = useMemo(() => {
    return bills.filter((b) => {
      if (tab === "all") return true;
      if (tab === "paid") return b.status === "paid";
      if (tab === "pending") {
        return b.status === "issued" || b.status === "partially_paid" || b.status === "draft" || b.status === "pending";
      }
      return true;
    });
  }, [bills, tab]);

  if (isDetail) {
    return <Outlet />;
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Bills & Receipts"
        description="View your hospital consultation charges and verified receipts."
        actions={
          <Button variant="outline" size="sm" onClick={fetchBills} disabled={loading} className="gap-1.5">
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} /> Refresh
          </Button>
        }
      />

      <Tabs value={tab} onValueChange={(v) => setTab(v as typeof tab)}>
        <TabsList className="grid w-full max-w-sm grid-cols-3">
          <TabsTrigger value="all">All ({bills.length})</TabsTrigger>
          <TabsTrigger value="pending">
            Pending ({bills.filter((b) => b.status !== "paid" && b.status !== "cancelled").length})
          </TabsTrigger>
          <TabsTrigger value="paid">
            Paid ({bills.filter((b) => b.status === "paid").length})
          </TabsTrigger>
        </TabsList>
      </Tabs>

      {loading ? (
        <Card className="p-10 text-center">
          <RefreshCw className="mx-auto h-6 w-6 animate-spin text-primary" />
          <p className="mt-2 text-sm text-foreground font-medium">Loading bills from hospital system…</p>
        </Card>
      ) : error ? (
        <Card className="border-error/40 bg-error/5 p-6 text-center">
          <AlertCircle className="mx-auto h-8 w-8 text-error" />
          <p className="mt-2 font-semibold text-error">Unable to load bills</p>
          <p className="mt-1 text-xs text-muted-foreground">{error}</p>
          <Button variant="outline" size="sm" onClick={fetchBills} className="mt-4">
            Retry
          </Button>
        </Card>
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={ReceiptText}
          title="No bills found"
          description="Your medical invoices and receipts will appear here after your consultations."
        />
      ) : (
        <div className="grid gap-3">
          {filtered.map((b) => (
            <Card key={b.bill_id} className="card-hover">
              <CardContent className="p-4 sm:p-5">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="font-display text-base font-semibold font-mono">{b.bill_id}</p>
                      <BillingBadge status={b.status} />
                    </div>
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      {b.consultation_id || b.appointment_id || "Hospital Encounter"} • {fmtDate(b.created_at)}
                    </p>
                  </div>
                  <div className="flex items-center gap-3 sm:gap-4">
                    <div className="text-right">
                      <p className="font-display text-lg font-bold">{inr(b.grand_total)}</p>
                      {b.balance_due > 0 ? (
                        <p className="text-xs text-error font-medium">Balance: {inr(b.balance_due)}</p>
                      ) : (
                        <p className="text-xs text-success font-medium">Paid in full</p>
                      )}
                    </div>
                    <Button asChild size="sm" variant="ghost">
                      <Link to="/app/bills/$id" params={{ id: b.bill_id }} id={`open-bill-${b.bill_id}`}>
                        View Details <ChevronRight className="ml-1 h-4 w-4" />
                      </Link>
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
