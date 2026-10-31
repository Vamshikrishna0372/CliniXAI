import { useState, useEffect } from "react";
import { createFileRoute, Link, useParams } from "@tanstack/react-router";
import {
  ArrowLeft, Check, Printer, RefreshCw, AlertCircle, Ban, ReceiptText, ShieldCheck
} from "lucide-react";
import { PageHeader } from "@/components/app-shell/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { BillingBadge } from "@/components/domain/status-badge";
import { EmptyState } from "@/components/dashboard/states";
import { BrandMark } from "@/components/brand-mark";
import { inr, fmtDate } from "@/lib/mock/domain";
import { apiClient } from "@/lib/api-client";
import { toast } from "sonner";

export const Route = createFileRoute("/app/billing/$id")({
  head: () => ({ meta: [{ title: "Bill Detail — CliniXAI" }, { name: "robots", content: "noindex" }] }),
  component: StaffBillDetail,
});

type PaymentMethodType = "cash" | "upi" | "card";

function StaffBillDetail() {
  const { id } = useParams({ from: "/app/billing/$id" });
  const [bill, setBill] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Payment recording state
  const [method, setMethod] = useState<PaymentMethodType>("cash");
  const [amount, setAmount] = useState<string>("");
  const [ref, setRef] = useState("");
  const [notes, setNotes] = useState("");
  const [recording, setRecording] = useState(false);

  // Cancellation state
  const [cancelReason, setCancelReason] = useState("");
  const [cancelling, setCancelling] = useState(false);

  // Voiding state
  const [voidingId, setVoidingId] = useState<string | null>(null);
  const [voidReason, setVoidReason] = useState("");

  const fetchBill = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await apiClient.billing.getDetail(id);
      const data = res?.data;
      setBill(data);
      if (data?.balance_due !== undefined) {
        setAmount(String(data.balance_due));
      }
    } catch (err: any) {
      setError(err?.message || "Failed to load bill detail from server.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchBill();
  }, [id]);

  const handleRecordPayment = async () => {
    const numAmount = Number(amount);
    if (!numAmount || numAmount <= 0) {
      toast.error("Enter a valid payment amount greater than zero");
      return;
    }

    if (bill && numAmount > roundToTwo(bill.balance_due + 0.005)) {
      toast.error(`Payment amount exceeds balance due (${inr(bill.balance_due)})`);
      return;
    }

    try {
      setRecording(true);
      const payload: any = {
        amount: numAmount,
        method,
        reference_number: ref.trim() || undefined,
        notes: notes.trim() || undefined,
      };

      const res = await apiClient.billing.recordPayment(id, payload);
      const updated = res?.data;
      setBill(updated);
      toast.success("Payment recorded successfully", {
        description: `Balance: ${inr(updated?.balance_due || 0)}`,
      });
      setRef("");
      setNotes("");
      setAmount(String(updated?.balance_due || 0));
    } catch (err: any) {
      toast.error(err?.message || "Failed to record payment.");
      fetchBill();
    } finally {
      setRecording(false);
    }
  };

  const handleVoidPayment = async (paymentId: string) => {
    const reason = voidReason.trim() || "Voided by hospital staff";
    try {
      const res = await apiClient.billing.voidPayment(id, paymentId, { reason });
      setBill(res?.data);
      toast.success("Payment transaction voided successfully");
      setVoidingId(null);
      setVoidReason("");
    } catch (err: any) {
      toast.error(err?.message || "Failed to void payment.");
    }
  };

  const handleCancelBill = async () => {
    try {
      setCancelling(true);
      const res = await apiClient.billing.cancel(id, { reason: cancelReason.trim() || undefined });
      setBill(res?.data);
      toast.success("Bill cancelled successfully");
    } catch (err: any) {
      toast.error(err?.message || "Failed to cancel bill.");
    } finally {
      setCancelling(false);
    }
  };

  const handleIssueBill = async () => {
    try {
      const res = await apiClient.billing.issue(id);
      setBill(res?.data);
      toast.success("Bill issued successfully to patient");
    } catch (err: any) {
      toast.error(err?.message || "Failed to issue bill.");
    }
  };

  const roundToTwo = (num: number) => Math.round(num * 100) / 100;

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
        <p className="mt-1 text-xs text-muted-foreground">{error || "The requested bill record is unavailable."}</p>
        <div className="mt-6">
          <Button asChild variant="outline">
            <Link to="/app/billing"><ArrowLeft className="mr-1.5 h-4 w-4" /> Back to Billing</Link>
          </Button>
        </div>
      </Card>
    );
  }

  const activePayments = (bill.payments || []).filter(
    (p: any) => p.status === "completed" || p.status === "recorded"
  );

  return (
    <div className="space-y-6">
      <div>
        <Button asChild variant="ghost" size="sm" className="mb-2">
          <Link to="/app/billing"><ArrowLeft className="mr-1 h-4 w-4" /> Billing Dashboard</Link>
        </Button>
        <PageHeader
          title={bill.bill_id}
          description={`Patient: ${bill.patient_id} • Created ${fmtDate(bill.created_at)}`}
          actions={
            <div className="flex items-center gap-2">
              <BillingBadge status={bill.status} />
              {bill.status === "draft" && (
                <Button size="sm" onClick={handleIssueBill}>
                  Issue Bill
                </Button>
              )}
            </div>
          }
        />
      </div>

      {/* Financial Summary Cards */}
      <div className="grid gap-4 sm:grid-cols-3">
        <Card className="p-4 bg-card/60">
          <p className="text-xs uppercase tracking-wider text-muted-foreground font-medium">Grand Total</p>
          <p className="font-display text-2xl font-bold mt-1 text-foreground" id="text-grand-total">
            {inr(bill.grand_total)}
          </p>
          <p className="text-[11px] text-muted-foreground mt-0.5">Authoritative invoice amount</p>
        </Card>
        <Card className="p-4 bg-card/60">
          <p className="text-xs uppercase tracking-wider text-muted-foreground font-medium">Amount Paid</p>
          <p className="font-display text-2xl font-bold mt-1 text-success" id="text-amount-paid">
            {inr(bill.amount_paid)}
          </p>
          <p className="text-[11px] text-muted-foreground mt-0.5">{activePayments.length} recorded payment(s)</p>
        </Card>
        <Card className="p-4 bg-card/60">
          <p className="text-xs uppercase tracking-wider text-muted-foreground font-medium">Outstanding Balance</p>
          <p
            className={`font-display text-2xl font-bold mt-1 ${bill.balance_due > 0 ? "text-error" : "text-muted-foreground"}`}
            id="text-balance-due"
          >
            {inr(bill.balance_due)}
          </p>
          <p className="text-[11px] text-muted-foreground mt-0.5">
            {bill.balance_due <= 0 ? "Fully settled" : "Due from patient"}
          </p>
        </Card>
      </div>

      {/* Bill Line Items Table */}
      <Card>
        <CardContent className="p-5 space-y-4">
          <div className="flex items-center justify-between">
            <p className="font-display text-sm font-semibold uppercase tracking-wider text-muted-foreground">
              Bill Line Items
            </p>
            {bill.notes && <span className="text-xs text-muted-foreground italic">{bill.notes}</span>}
          </div>

          <div className="overflow-hidden rounded-xl border border-border">
            <table className="w-full text-sm">
              <thead className="bg-muted/40 text-xs uppercase tracking-wider text-muted-foreground">
                <tr>
                  <th className="px-4 py-2.5 text-left font-medium">Item Code</th>
                  <th className="px-4 py-2.5 text-left font-medium">Description</th>
                  <th className="px-4 py-2.5 text-right font-medium">Quantity</th>
                  <th className="px-4 py-2.5 text-right font-medium">Unit Price</th>
                  <th className="px-4 py-2.5 text-right font-medium">Amount</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {(bill.line_items || []).map((i: any, idx: number) => (
                  <tr key={idx} className="hover:bg-muted/20">
                    <td className="px-4 py-2.5 font-mono text-xs text-muted-foreground">{i.item_code}</td>
                    <td className="px-4 py-2.5 font-medium">{i.description}</td>
                    <td className="px-4 py-2.5 text-right">{i.quantity}</td>
                    <td className="px-4 py-2.5 text-right">{inr(i.unit_price)}</td>
                    <td className="px-4 py-2.5 text-right font-semibold">{inr(i.total || i.subtotal)}</td>
                  </tr>
                ))}
                <tr className="border-t-2 border-border bg-muted/30">
                  <td colSpan={4} className="px-4 py-2 font-medium">Subtotal</td>
                  <td className="px-4 py-2 text-right font-medium">{inr(bill.subtotal)}</td>
                </tr>
                {bill.total_discount > 0 && (
                  <tr className="text-success bg-success/5">
                    <td colSpan={4} className="px-4 py-2 font-medium">Discount</td>
                    <td className="px-4 py-2 text-right font-semibold">− {inr(bill.total_discount)}</td>
                  </tr>
                )}
                <tr className="border-t border-border font-bold text-base bg-muted/40">
                  <td colSpan={4} className="px-4 py-3">Total Payable</td>
                  <td className="px-4 py-3 text-right font-display text-primary">{inr(bill.grand_total)}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Record Payment Section */}
      {bill.status !== "paid" && bill.status !== "cancelled" && bill.balance_due > 0 && (
        <Card className="border-primary/40 bg-card">
          <CardContent className="p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-border pb-3">
              <div>
                <p className="font-display text-base font-semibold text-foreground">Record Offline Payment</p>
                <p className="text-xs text-muted-foreground">
                  Record Cash, UPI, or Card payment collected at the hospital desk.
                </p>
              </div>
              <div className="text-right">
                <span className="text-xs text-muted-foreground">Balance Due</span>
                <p className="font-display text-lg font-bold text-error">{inr(bill.balance_due)}</p>
              </div>
            </div>

            <div>
              <Label className="mb-2 block text-xs font-semibold uppercase text-muted-foreground">
                Payment Method
              </Label>
              <RadioGroup
                value={method}
                onValueChange={(v) => setMethod(v as PaymentMethodType)}
                className="grid grid-cols-3 gap-3"
              >
                {(["cash", "upi", "card"] as const).map((m) => (
                  <label
                    key={m}
                    className={`flex items-center gap-2 rounded-lg border p-3.5 text-sm capitalize font-medium cursor-pointer transition-colors ${
                      method === m
                        ? "border-primary bg-primary/10 text-primary"
                        : "border-border hover:bg-muted/40"
                    }`}
                  >
                    <RadioGroupItem value={m} id={`radio-method-${m}`} />
                    <span>{m.toUpperCase()}</span>
                  </label>
                ))}
              </RadioGroup>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <Label className="mb-1 block text-xs">Payment Amount (₹) *</Label>
                <Input
                  id="input-payment-amount"
                  type="number"
                  placeholder="Amount"
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                />
              </div>
              <div>
                <Label className="mb-1 block text-xs">
                  {method === "cash" ? "Receipt Reference (Optional)" : `${method.toUpperCase()} Reference / UTR Number`}
                </Label>
                <Input
                  id="input-payment-ref"
                  placeholder={method === "upi" ? "e.g. UPI-UTR-12345678" : method === "card" ? "e.g. CARD-AUTH-9999" : "Receipt / Memo ref"}
                  value={ref}
                  onChange={(e) => setRef(e.target.value)}
                />
              </div>
            </div>

            <div>
              <Label className="mb-1 block text-xs">Staff Notes (Optional)</Label>
              <Input
                id="input-payment-notes"
                placeholder="Hospital notes for payment"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
              />
            </div>

            <div className="flex justify-end pt-2">
              <Button
                id="btn-record-payment"
                onClick={handleRecordPayment}
                disabled={recording}
                className="gap-1.5"
              >
                <Check className="h-4 w-4" />
                {recording ? "Recording Payment…" : `Record ${method.toUpperCase()} Payment`}
              </Button>
            </div>
            <p className="text-[11px] text-muted-foreground">
              CliniXAI offline billing records payments received in-person at the hospital reception.
            </p>
          </CardContent>
        </Card>
      )}

      {/* Payment History & Voiding Section */}
      <Card>
        <CardContent className="p-5 space-y-4">
          <div className="flex items-center justify-between border-b border-border pb-3">
            <p className="font-display text-sm font-semibold uppercase tracking-wider text-muted-foreground">
              Payment Transaction History ({bill.payments?.length || 0})
            </p>
            <div className="flex gap-2">
              {activePayments.length > 0 && (
                <Button variant="outline" size="sm" onClick={() => window.print()} className="gap-1.5">
                  <Printer className="h-3.5 w-3.5" /> Print Receipt
                </Button>
              )}
            </div>
          </div>

          {!bill.payments || bill.payments.length === 0 ? (
            <div className="py-6 text-center text-sm text-muted-foreground">
              No payments have been recorded for this bill yet.
            </div>
          ) : (
            <div className="overflow-hidden rounded-xl border border-border">
              <table className="w-full text-sm">
                <thead className="bg-muted/40 text-xs uppercase tracking-wider text-muted-foreground">
                  <tr>
                    <th className="px-4 py-2.5 text-left font-medium">Payment ID</th>
                    <th className="px-4 py-2.5 text-left font-medium">Date</th>
                    <th className="px-4 py-2.5 text-left font-medium">Method</th>
                    <th className="px-4 py-2.5 text-right font-medium">Amount</th>
                    <th className="px-4 py-2.5 text-left font-medium">Reference</th>
                    <th className="px-4 py-2.5 text-center font-medium">Status</th>
                    <th className="px-4 py-2.5 text-right font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {bill.payments.map((p: any) => {
                    const isVoided = p.status === "voided";
                    return (
                      <tr key={p.payment_id} className={isVoided ? "opacity-60 bg-muted/20" : ""}>
                        <td className="px-4 py-2.5 font-mono text-xs font-semibold">{p.payment_id}</td>
                        <td className="px-4 py-2.5 text-xs text-muted-foreground">{fmtDate(p.paid_at || p.recorded_at)}</td>
                        <td className="px-4 py-2.5 font-medium uppercase text-xs">{p.method}</td>
                        <td className="px-4 py-2.5 text-right font-bold font-display">{inr(p.amount)}</td>
                        <td className="px-4 py-2.5 text-xs text-muted-foreground">{p.reference_number || p.reference || "—"}</td>
                        <td className="px-4 py-2.5 text-center">
                          <span
                            className={`inline-block px-2 py-0.5 text-[11px] rounded font-semibold uppercase ${
                              isVoided
                                ? "bg-error/15 text-error"
                                : "bg-success/15 text-success"
                            }`}
                          >
                            {p.status}
                          </span>
                        </td>
                        <td className="px-4 py-2.5 text-right">
                          {!isVoided && bill.status !== "cancelled" && (
                            <Button
                              variant="ghost"
                              size="sm"
                              className="text-xs text-error hover:text-error"
                              onClick={() => setVoidingId(p.payment_id)}
                            >
                              Void
                            </Button>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {/* Void Dialog */}
          {voidingId && (
            <div className="rounded-xl border border-error/30 bg-error/5 p-4 space-y-3">
              <p className="text-sm font-semibold text-error">Void Payment Transaction: {voidingId}</p>
              <Input
                placeholder="Reason for voiding payment (required)"
                value={voidReason}
                onChange={(e) => setVoidReason(e.target.value)}
              />
              <div className="flex justify-end gap-2">
                <Button variant="ghost" size="sm" onClick={() => { setVoidingId(null); setVoidReason(""); }}>
                  Cancel
                </Button>
                <Button variant="destructive" size="sm" onClick={() => handleVoidPayment(voidingId)}>
                  Confirm Void
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Receipt Printable Card */}
      {activePayments.length > 0 && (
        <div className="mx-auto max-w-2xl rounded-2xl border border-border bg-card p-6 print:border-0 print:shadow-none space-y-4">
          <div className="flex flex-wrap items-start justify-between gap-4 border-b border-border pb-4">
            <div>
              <BrandMark size="sm" />
              <p className="mt-2 text-xs text-muted-foreground">
                CliniXAI Hospital Medical Centre<br />MG Road, Bengaluru 560001
              </p>
            </div>
            <div className="text-right">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">Official Receipt</p>
              <p className="font-display text-base font-bold text-foreground">
                {activePayments[activePayments.length - 1].payment_id}
              </p>
              <p className="text-xs text-muted-foreground">Bill ID: {bill.bill_id}</p>
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
              <p className="text-muted-foreground uppercase">Reference</p>
              <p className="font-semibold text-sm">
                {activePayments[activePayments.length - 1].reference_number || "Hospital Cashier"}
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

      {/* Bill Cancellation (Allowed only if no active payments) */}
      {bill.status !== "paid" && bill.status !== "cancelled" && activePayments.length === 0 && (
        <Card className="border-border">
          <CardContent className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <p className="text-sm font-semibold">Cancel this Bill</p>
              <p className="text-xs text-muted-foreground">
                Unpaid bills can be cancelled if created erroneously.
              </p>
            </div>
            <div className="flex gap-2">
              <Input
                placeholder="Cancellation reason"
                value={cancelReason}
                onChange={(e) => setCancelReason(e.target.value)}
                className="max-w-xs"
              />
              <Button
                variant="outline"
                size="sm"
                onClick={handleCancelBill}
                disabled={cancelling}
                className="text-error border-error/30 hover:bg-error/10"
              >
                <Ban className="h-4 w-4 mr-1" />
                {cancelling ? "Cancelling…" : "Cancel Bill"}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
