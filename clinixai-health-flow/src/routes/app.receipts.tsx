import { useMemo, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Search, ArrowLeft, Printer } from "lucide-react";
import { PageHeader } from "@/components/app-shell/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { EmptyState } from "@/components/dashboard/states";
import { ReceiptView } from "@/components/domain/receipt-view";
import { getDoctor, inr, fmtDate, type PaymentMethod } from "@/lib/mock/domain";
import { useClinix } from "@/lib/store/clinix-store";

export const Route = createFileRoute("/app/receipts")({
  head: () => ({ meta: [{ title: "Receipts — CliniXAI" }, { name: "robots", content: "noindex" }] }),
  component: ReceiptsPage,
});

function ReceiptsPage() {
  const { receipts, getPatient } = useClinix();
  const [q, setQ] = useState("");
  const [method, setMethod] = useState<"all" | PaymentMethod>("all");
  const [selected, setSelected] = useState<string | null>(null);

  const list = useMemo(() => receipts.filter((r) => {
    if (method !== "all" && r.method !== method) return false;
    if (!q) return true;
    const p = getPatient(r.patientId);
    const hay = [r.id, r.billId, p?.firstName, p?.lastName, p?.id].filter(Boolean).join(" ").toLowerCase();
    return hay.includes(q.toLowerCase());
  }), [receipts, q, method, getPatient]);

  const selectedReceipt = selected ? receipts.find((r) => r.id === selected) : null;

  if (selectedReceipt) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between print:hidden">
          <Button variant="ghost" size="sm" onClick={() => setSelected(null)}><ArrowLeft className="mr-1 h-4 w-4" /> Receipts</Button>
          <Button variant="outline" size="sm" onClick={() => window.print()}><Printer className="mr-1 h-3.5 w-3.5" /> Print</Button>
        </div>
        <ReceiptView receipt={selectedReceipt} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Receipts" description="Issued payment receipts." />
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative flex-1"><Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" /><Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search receipt, bill or patient…" className="pl-9" aria-label="Search receipts" /></div>
        <Select value={method} onValueChange={(v) => setMethod(v as typeof method)}>
          <SelectTrigger className="sm:w-40"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All methods</SelectItem>
            <SelectItem value="cash">Cash</SelectItem>
            <SelectItem value="upi">UPI</SelectItem>
            <SelectItem value="card">Card</SelectItem>
          </SelectContent>
        </Select>
      </div>
      {list.length === 0 ? <EmptyState title="No receipts found" /> : (
        <Card><CardContent className="p-0"><ul className="divide-y divide-border">
          {list.map((r) => { const p = getPatient(r.patientId); const d = getDoctor(r.doctorId); return (
            <li key={r.id} className="grid grid-cols-1 gap-2 p-4 sm:grid-cols-[1fr_1fr_120px_100px_auto] sm:items-center">
              <div><p className="text-sm font-semibold">{r.id}</p><p className="text-xs text-muted-foreground">Bill {r.billId} • {fmtDate(r.date)}</p></div>
              <div className="min-w-0"><p className="truncate text-sm">{p?.firstName} {p?.lastName}</p><p className="truncate text-xs text-muted-foreground">{d?.name}</p></div>
              <div className="font-semibold">{inr(r.amount)}</div>
              <div className="text-xs uppercase text-muted-foreground">{r.method}</div>
              <Button size="sm" variant="ghost" onClick={() => setSelected(r.id)}>View</Button>
            </li>
          );})}
        </ul></CardContent></Card>
      )}
    </div>
  );
}
