import { useMemo, useState, useEffect } from "react";
import { createFileRoute, Link, Outlet, useMatch } from "@tanstack/react-router";
import { ChevronRight, Plus, Trash2, RefreshCw, AlertCircle, ReceiptText, Search } from "lucide-react";
import { PageHeader } from "@/components/app-shell/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { BillingBadge } from "@/components/domain/status-badge";
import { EmptyState } from "@/components/dashboard/states";
import { inr, fmtDate } from "@/lib/mock/domain";
import { apiClient } from "@/lib/api-client";
import { toast } from "sonner";

export const Route = createFileRoute("/app/billing")({
  head: () => ({ meta: [{ title: "Billing — CliniXAI" }, { name: "robots", content: "noindex" }] }),
  component: BillingPage,
});

type LineItem = { description: string; unit_price: string; quantity: string };

interface BillItem {
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

function BillingPage() {
  const isDetail = useMatch({ from: "/app/billing/$id", shouldThrow: false });
  const [bills, setBills] = useState<BillItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<"all" | "draft" | "issued" | "partially_paid" | "paid" | "cancelled">("all");
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  // Bill creation form
  const [consultationId, setConsultationId] = useState("");
  const [consultations, setConsultations] = useState<any[]>([]);
  const [patientId, setPatientId] = useState("");
  const [patients, setPatients] = useState<any[]>([]);
  const [items, setItems] = useState<LineItem[]>([
    { description: "Consultation Fee", unit_price: "500", quantity: "1" }
  ]);
  const [discount, setDiscount] = useState("0");
  const [notes, setNotes] = useState("");

  const fetchBills = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await apiClient.billing.list({ page_size: 100 });
      const itemsList = res?.data || [];
      setBills(itemsList);
    } catch (err: any) {
      setError(err?.message || "Failed to load billing records from hospital server.");
    } finally {
      setLoading(false);
    }
  };

  const fetchConsultationsAndPatients = async () => {
    try {
      const [cRes, pRes] = await Promise.allSettled([
        apiClient.consultations.list({ page_size: 50 }),
        apiClient.patients.list({ page_size: 50 }),
      ]);
      if (cRes.status === "fulfilled" && cRes.value?.data) {
        setConsultations(cRes.value.data);
      }
      if (pRes.status === "fulfilled" && pRes.value?.data) {
        setPatients(pRes.value.data);
      }
    } catch {
      // non-fatal
    }
  };

  useEffect(() => {
    fetchBills();
    fetchConsultationsAndPatients();
  }, []);

  const resetForm = () => {
    setConsultationId("");
    setPatientId("");
    setItems([{ description: "Consultation Fee", unit_price: "500", quantity: "1" }]);
    setDiscount("0");
    setNotes("");
  };

  const filteredBills = useMemo(() => {
    return bills.filter((b) => {
      const matchesTab =
        tab === "all" ||
        b.status === tab ||
        (tab === "issued" && (b.status === "issued" || b.status === "pending"));
      const query = q.trim().toLowerCase();
      const matchesSearch =
        !query ||
        b.bill_id.toLowerCase().includes(query) ||
        b.patient_id.toLowerCase().includes(query) ||
        (b.consultation_id && b.consultation_id.toLowerCase().includes(query)) ||
        (b.appointment_id && b.appointment_id.toLowerCase().includes(query));
      return matchesTab && matchesSearch;
    });
  }, [bills, tab, q]);

  const submit = async () => {
    const validItems = items
      .filter((it) => it.description.trim() && Number(it.unit_price) >= 0 && Number(it.quantity) > 0)
      .map((it, idx) => ({
        item_code: "ITEM-" + String(idx + 1).padStart(3, "0"),
        description: it.description.trim(),
        quantity: Number(it.quantity) || 1.0,
        unit_price: Number(it.unit_price) || 0.0,
        tax_percent: 0.0,
        discount_amount: 0.0,
      }));

    if (validItems.length === 0) {
      toast.error("Please add at least one valid line item with positive quantity");
      return;
    }

    if (!consultationId && !patientId) {
      toast.error("Please select a consultation or specify a patient ID");
      return;
    }

    try {
      setSubmitting(true);
      const payload: any = {
        line_items: validItems,
        discount: Number(discount) || 0.0,
        notes: notes.trim() || undefined,
      };

      if (consultationId) {
        payload.consultation_id = consultationId;
      }
      if (patientId) {
        payload.patient_id = patientId;
      }

      const res = await apiClient.billing.create(payload);
      const createdBill = res?.data;
      toast.success("Bill generated successfully", { description: createdBill?.bill_id });
      setOpen(false);
      resetForm();
      await fetchBills();
    } catch (err: any) {
      toast.error(err?.message || "Failed to generate bill.");
    } finally {
      setSubmitting(false);
    }
  };

  if (isDetail) {
    return <Outlet />;
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Billing Workspace"
        description="Authoritative hospital billing, line items, and offline payment recording."
        actions={
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={fetchBills} disabled={loading} className="gap-1.5">
              <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} /> Refresh
            </Button>
            <Dialog open={open} onOpenChange={(o) => { setOpen(o); if (!o) resetForm(); }}>
              <DialogTrigger asChild>
                <Button id="btn-generate-bill"><Plus className="mr-1 h-4 w-4" /> Generate bill</Button>
              </DialogTrigger>
              <DialogContent className="max-w-lg">
                <DialogHeader><DialogTitle>Generate Hospital Bill</DialogTitle></DialogHeader>
                <div className="space-y-4">
                  <div>
                    <Label className="mb-1 block text-xs">Consultation Encounter (Optional)</Label>
                    <Select
                      value={consultationId}
                      onValueChange={(val) => {
                        setConsultationId(val);
                        const c = consultations.find((item) => item.consultation_id === val);
                        if (c?.patient_id) setPatientId(c.patient_id);
                      }}
                    >
                      <SelectTrigger id="select-consultation">
                        <SelectValue placeholder="Select consultation encounter" />
                      </SelectTrigger>
                      <SelectContent>
                        {consultations.length === 0 && (
                          <div className="px-2 py-1.5 text-xs text-muted-foreground">No recent consultations</div>
                        )}
                        {consultations.map((c) => (
                          <SelectItem key={c.consultation_id} value={c.consultation_id}>
                            {c.consultation_id} — Patient: {c.patient_id} ({c.status})
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <div>
                    <Label className="mb-1 block text-xs">Patient ID *</Label>
                    <Input
                      id="input-patient-id"
                      placeholder="e.g. PAT-2026-XXXXXX"
                      value={patientId}
                      onChange={(e) => setPatientId(e.target.value)}
                    />
                  </div>

                  <div className="space-y-2">
                    <Label className="text-xs">Line Items</Label>
                    {items.map((it, idx) => (
                      <div key={idx} className="flex gap-2">
                        <Input
                          placeholder="Description"
                          value={it.description}
                          onChange={(e) => setItems((xs) => xs.map((x, i) => i === idx ? { ...x, description: e.target.value } : x))}
                          className="flex-1"
                        />
                        <Input
                          type="number"
                          placeholder="Qty"
                          className="w-16"
                          value={it.quantity}
                          onChange={(e) => setItems((xs) => xs.map((x, i) => i === idx ? { ...x, quantity: e.target.value } : x))}
                        />
                        <Input
                          type="number"
                          placeholder="Unit Price"
                          className="w-24"
                          value={it.unit_price}
                          onChange={(e) => setItems((xs) => xs.map((x, i) => i === idx ? { ...x, unit_price: e.target.value } : x))}
                        />
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          aria-label="Remove item"
                          onClick={() => setItems((xs) => xs.filter((_, i) => i !== idx))}
                          disabled={items.length <= 1}
                        >
                          <Trash2 className="h-4 w-4 text-muted-foreground" />
                        </Button>
                      </div>
                    ))}
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => setItems((xs) => [...xs, { description: "", unit_price: "", quantity: "1" }])}
                    >
                      <Plus className="mr-1 h-3.5 w-3.5" /> Add item
                    </Button>
                  </div>

                  <div>
                    <Label className="mb-1 block text-xs">Discount (₹)</Label>
                    <Input
                      id="input-discount"
                      type="number"
                      value={discount}
                      onChange={(e) => setDiscount(e.target.value)}
                    />
                  </div>

                  <div>
                    <Label className="mb-1 block text-xs">Notes (Optional)</Label>
                    <Input
                      id="input-notes"
                      placeholder="Hospital bill notes"
                      value={notes}
                      onChange={(e) => setNotes(e.target.value)}
                    />
                  </div>
                </div>
                <DialogFooter>
                  <Button id="btn-submit-bill" onClick={submit} disabled={submitting}>
                    {submitting ? "Generating…" : "Generate Bill"}
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>
        }
      />

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <Tabs value={tab} onValueChange={(v) => setTab(v as typeof tab)}>
          <TabsList className="grid grid-cols-6 w-full sm:w-auto">
            <TabsTrigger value="all">All ({bills.length})</TabsTrigger>
            <TabsTrigger value="draft">Draft</TabsTrigger>
            <TabsTrigger value="issued">Issued</TabsTrigger>
            <TabsTrigger value="partially_paid">Partial</TabsTrigger>
            <TabsTrigger value="paid">Paid</TabsTrigger>
            <TabsTrigger value="cancelled">Cancelled</TabsTrigger>
          </TabsList>
        </Tabs>
        <div className="relative flex-1">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            id="search-bills"
            placeholder="Search by Bill ID, Patient ID, Consultation ID…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            className="pl-9"
          />
        </div>
      </div>

      {loading ? (
        <Card className="p-8 text-center">
          <RefreshCw className="mx-auto h-6 w-6 animate-spin text-primary" />
          <p className="mt-2 text-sm font-medium text-foreground">Loading bills from hospital database…</p>
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
      ) : filteredBills.length === 0 ? (
        <EmptyState
          icon={ReceiptText}
          title="No bills found"
          description={q ? "No bills match your search criteria." : "No bills recorded in this category."}
        />
      ) : (
        <Card>
          <CardContent className="p-0">
            <ul className="divide-y divide-border">
              {filteredBills.map((b) => (
                <li
                  key={b.bill_id}
                  className="grid grid-cols-1 gap-2 p-4 sm:grid-cols-[1.2fr_1fr_120px_120px_100px_auto] sm:items-center hover:bg-muted/30 transition-colors"
                >
                  <div>
                    <p className="text-sm font-semibold font-mono text-foreground">{b.bill_id}</p>
                    <p className="text-xs text-muted-foreground">{fmtDate(b.created_at)}</p>
                  </div>
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">Patient: {b.patient_id}</p>
                    <p className="truncate text-xs text-muted-foreground">
                      {b.consultation_id || b.appointment_id || "Encounter"}
                    </p>
                  </div>
                  <div className="text-right sm:text-left">
                    <p className="text-[11px] uppercase tracking-wider text-muted-foreground">Total</p>
                    <p className="font-display text-sm font-bold text-foreground">{inr(b.grand_total)}</p>
                  </div>
                  <div className="text-right sm:text-left">
                    <p className="text-[11px] uppercase tracking-wider text-muted-foreground">Balance</p>
                    <p className="font-display text-sm font-bold text-foreground">{inr(b.balance_due)}</p>
                  </div>
                  <div>
                    <BillingBadge status={b.status} />
                  </div>
                  <div className="text-right">
                    <Button asChild size="sm" variant="ghost">
                      <Link to="/app/billing/$id" params={{ id: b.bill_id }} id={`open-${b.bill_id}`}>
                        Open <ChevronRight className="ml-1 h-4 w-4" />
                      </Link>
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
