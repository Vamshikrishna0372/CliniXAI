import { useState, useEffect } from "react";
import { createFileRoute, Link, useParams } from "@tanstack/react-router";
import { ArrowLeft, Info, Printer, RefreshCw, AlertCircle, CheckCircle2 } from "lucide-react";
import { PageHeader } from "@/components/app-shell/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { BillingBadge } from "@/components/domain/status-badge";
import { EmptyState } from "@/components/dashboard/states";
import { BrandMark } from "@/components/brand-mark";
import { inr, fmtDate } from "@/lib/mock/domain";
import { apiClient } from "@/lib/api-client";

export const Route = createFileRoute("/app/bills/$id")({
  head: () => ({ meta: [{ title: "Bill Details — CliniXAI" }, { name: "robots", content: "noindex" }] }),
  component: BillDetailPage,
});

function BillDetailPage() {
  const { id } = useParams({ from: "/app/bills/$id" });
  const [bill, setBill] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchBill = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await apiClient.billing.getDetail(id);
      setBill(res?.data);
    } catch (err: any) {
      setError(err?.message || "Bill not found or access denied.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchBill();
  }, [id]);

  if (loading) {
    return (
      <Card className="p-12 text-center">
        <RefreshCw className="mx-auto h-8 w-8 animate-spin text-primary" />
        <p className="mt-3 text-sm font-medium text-foreground">Loading bill details from server…</p>
      </Card>
    );
  }

  if (error || !bill) {
    return (
      <Card className="border-error/40 bg-error/5 p-8 text-center">
        <AlertCircle className="mx-auto h-10 w-10 text-error" />
        <p className="mt-3 font-semibold text-error text-base">Bill not found or access denied</p>
        <p className="mt-1 text-xs text-muted-foreground">{error || "You do not have permission to view this bill."}</p>
        <div className="mt-6">
          <Button asChild variant="outline">
            <Link to="/app/bills"><ArrowLeft className="mr-1.5 h-4 w-4" /> Back to My Bills</Link>
          </Button>
        </div>
      </Card>
    );
  }

  const activePayments = (bill.payments || []).filter(
    (p: any) => p.status === "completed" || p.status === "recorded"
  );
  const isPaid = bill.status === "paid" || bill.balance_due <= 0;

  return (
    <div className="space-y-6">
      <div>
        <Button asChild variant="ghost" size="sm" className="mb-2">
          <Link to="/app/bills"><ArrowLeft className="mr-1 h-4 w-4" /> All bills</Link>
        </Button>
        <PageHeader
          title={bill.bill_id}
          description={`Issued on ${fmtDate(bill.created_at)} • Encounter: ${bill.consultation_id || bill.appointment_id || "General"}`}
          actions={
            <div className="flex items-center gap-2">
              <BillingBadge status={bill.status} />
              {activePayments.length > 0 && (
                <Button variant="outline" size="sm" onClick={() => window.print()} className="gap-1.5 print:hidden">
                  <Printer className="h-3.5 w-3.5" /> Print
                </Button>
              )}
            </div>
          }
        />
      </div>

      {/* Overview Cards */}
      <div className="grid gap-3 sm:grid-cols-3">
        <Card className="p-4">
          <p className="text-[11px] uppercase tracking-wider text-muted-foreground">Total Bill</p>
          <p className="font-display text-xl font-bold mt-0.5">{inr(bill.grand_total)}</p>
        </Card>
        <Card className="p-4">
          <p className="text-[11px] uppercase tracking-wider text-muted-foreground">Amount Paid</p>
          <p className="font-display text-xl font-bold mt-0.5 text-success">{inr(bill.amount_paid)}</p>
        </Card>
        <Card className="p-4">
          <p className="text-[11px] uppercase tracking-wider text-muted-foreground">Outstanding Balance</p>
          <p className={`font-display text-xl font-bold mt-0.5 ${bill.balance_due > 0 ? "text-error" : "text-muted-foreground"}`}>
            {inr(bill.balance_due)}
          </p>
        </Card>
      </div>

      {/* Bill Items Table */}
      <Card>
        <CardContent className="p-5 space-y-4">
          <p className="font-display text-sm font-semibold uppercase tracking-wider text-muted-foreground">
            Charge Breakdown
          </p>

          <div className="overflow-hidden rounded-xl border border-border">
            <table className="w-full text-sm">
              <thead className="bg-muted/40 text-xs uppercase tracking-wider text-muted-foreground">
                <tr>
                  <th className="px-4 py-2.5 text-left font-medium">Service / Item</th>
                  <th className="px-4 py-2.5 text-right font-medium">Quantity</th>
                  <th className="px-4 py-2.5 text-right font-medium">Unit Price</th>
                  <th className="px-4 py-2.5 text-right font-medium">Amount</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {(bill.line_items || []).map((i: any, idx: number) => (
                  <tr key={idx}>
                    <td className="px-4 py-2.5 font-medium">{i.description}</td>
                    <td className="px-4 py-2.5 text-right">{i.quantity}</td>
                    <td className="px-4 py-2.5 text-right">{inr(i.unit_price)}</td>
                    <td className="px-4 py-2.5 text-right font-semibold">{inr(i.total || i.subtotal)}</td>
                  </tr>
                ))}
                <tr className="border-t border-border bg-muted/20">
                  <td colSpan={3} className="px-4 py-2 font-medium">Subtotal</td>
                  <td className="px-4 py-2 text-right font-medium">{inr(bill.subtotal)}</td>
                </tr>
                {bill.total_discount > 0 && (
                  <tr className="text-success bg-success/5">
                    <td colSpan={3} className="px-4 py-2 font-medium">Discount</td>
                    <td className="px-4 py-2 text-right font-semibold">− {inr(bill.total_discount)}</td>
                  </tr>
                )}
                <tr className="border-t border-border font-bold text-base bg-muted/40">
                  <td colSpan={3} className="px-4 py-3">Total Amount</td>
                  <td className="px-4 py-3 text-right font-display text-primary">{inr(bill.grand_total)}</td>
                </tr>
              </tbody>
            </table>
          </div>

          {!isPaid ? (
            <Alert className="border-primary/30 bg-primary/5">
              <Info className="h-4 w-4 text-primary" />
              <AlertTitle>Hospital Reception Payment</AlertTitle>
              <AlertDescription className="text-xs">
                Please pay the remaining balance of {inr(bill.balance_due)} at the CliniXAI hospital reception via Cash, UPI, or Card.
                The cashier will record the transaction and issue an official receipt.
              </AlertDescription>
            </Alert>
          ) : (
            <div className="rounded-xl border border-success/30 bg-success/10 p-3.5 flex items-center gap-3">
              <CheckCircle2 className="h-5 w-5 text-success shrink-0" />
              <div>
                <p className="text-sm font-semibold text-success">This bill is fully settled.</p>
                <p className="text-xs text-muted-foreground">Thank you. Your receipt is verified below.</p>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Official Receipt Card */}
      {activePayments.length > 0 && (
        <div className="mx-auto max-w-2xl rounded-2xl border border-border bg-card p-6 print:border-0 print:shadow-none space-y-4">
          <div className="flex flex-wrap items-start justify-between gap-4 border-b border-border pb-4">
            <div>
              <BrandMark size="sm" />
              <p className="mt-2 text-xs text-muted-foreground">
                CliniXAI Medical Hospital Centre<br />MG Road, Bengaluru 560001
              </p>
            </div>
            <div className="text-right">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">Official Receipt</p>
              <p className="font-display text-base font-bold text-foreground">
                {activePayments[activePayments.length - 1].payment_id}
              </p>
              <p className="text-xs text-muted-foreground">Bill: {bill.bill_id}</p>
            </div>
          </div>

          <div className="grid gap-2 sm:grid-cols-2 text-xs">
            <div>
              <p className="text-muted-foreground uppercase">Patient ID</p>
              <p className="font-semibold text-sm">{bill.patient_id}</p>
            </div>
            <div>
              <p className="text-muted-foreground uppercase">Payment Date</p>
              <p className="font-semibold text-sm">
                {fmtDate(activePayments[activePayments.length - 1].paid_at)}
              </p>
            </div>
            <div>
              <p className="text-muted-foreground uppercase">Payment Method</p>
              <p className="font-semibold text-sm uppercase">
                {activePayments[activePayments.length - 1].method}
              </p>
            </div>
            <div>
              <p className="text-muted-foreground uppercase">Hospital Reference</p>
              <p className="font-semibold text-sm">
                {activePayments[activePayments.length - 1].reference_number || "Desk Cashier"}
              </p>
            </div>
          </div>

          <div className="border-t border-border pt-3 flex justify-between items-center">
            <div>
              <span className="text-xs text-muted-foreground uppercase">Total Amount Paid</span>
              <p className="font-display text-xl font-bold text-success">{inr(bill.amount_paid)}</p>
            </div>
            <div className="text-right">
              <span className="text-xs text-muted-foreground uppercase">Remaining Balance</span>
              <p className="font-display text-xl font-bold text-foreground">{inr(bill.balance_due)}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
