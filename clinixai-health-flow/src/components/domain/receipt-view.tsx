import { BrandMark } from "@/components/brand-mark";
import { QRPlaceholder } from "./qr-placeholder";
import { inr, fmtDate, type Receipt } from "@/lib/mock/domain";
import { useClinix } from "@/lib/store/clinix-store";

export function ReceiptView({ receipt }: { receipt: Receipt }) {
  const { getBill, getPatient, getDoctor, getAppointment } = useClinix();
  const bill = getBill(receipt.billId);
  const patient = getPatient(receipt.patientId);
  const doctor = getDoctor(receipt.doctorId);
  const apt = getAppointment(receipt.appointmentId);
  return (
    <div className="mx-auto max-w-2xl rounded-2xl border border-border bg-card p-6 print:border-0 print:shadow-none">
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-border pb-4">
        <div>
          <BrandMark size="sm" />
          <p className="mt-2 text-xs text-muted-foreground">CliniXAI Medical Centre<br />MG Road, Bengaluru 560001</p>
        </div>
        <div className="text-right">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Receipt</p>
          <p className="font-display text-lg font-bold text-foreground">{receipt.id}</p>
          <p className="text-xs text-muted-foreground">Bill: {receipt.billId}</p>
        </div>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <div>
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Patient</p>
          <p className="font-semibold text-foreground">{patient?.firstName} {patient?.lastName}</p>
          <p className="text-xs text-muted-foreground">{patient?.id}</p>
        </div>
        <div>
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Doctor</p>
          <p className="font-semibold text-foreground">{doctor?.name}</p>
          <p className="text-xs text-muted-foreground">{doctor?.department}</p>
        </div>
        <div>
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Appointment</p>
          <p className="text-sm text-foreground">{apt?.id}</p>
        </div>
        <div>
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Date</p>
          <p className="text-sm text-foreground">{fmtDate(receipt.date)}</p>
        </div>
      </div>

      <div className="mt-6 overflow-hidden rounded-xl border border-border">
        <table className="w-full text-sm">
          <thead className="bg-muted/40 text-xs uppercase tracking-wide text-muted-foreground">
            <tr><th className="px-3 py-2 text-left">Item</th><th className="px-3 py-2 text-right">Amount</th></tr>
          </thead>
          <tbody>
            {bill?.items.map((i) => (
              <tr key={i.label} className="border-t border-border"><td className="px-3 py-2">{i.label}</td><td className="px-3 py-2 text-right">{inr(i.amount)}</td></tr>
            ))}
            {bill && bill.discount > 0 && (
              <tr className="border-t border-border text-success"><td className="px-3 py-2">Discount</td><td className="px-3 py-2 text-right">− {inr(bill.discount)}</td></tr>
            )}
            <tr className="border-t border-border bg-muted/40 font-semibold"><td className="px-3 py-2">Total paid</td><td className="px-3 py-2 text-right">{inr(receipt.amount)}</td></tr>
          </tbody>
        </table>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <div className="rounded-xl border border-border p-3">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Payment</p>
          <p className="text-sm font-semibold capitalize text-foreground">{receipt.method}</p>
          {receipt.reference && <p className="text-xs text-muted-foreground">Ref: {receipt.reference}</p>}
        </div>
        <div className="flex items-center justify-end">
          <QRPlaceholder value={receipt.id} size={96} />
        </div>
      </div>

      <p className="mt-4 text-[11px] text-muted-foreground">
        This is a computer-generated mock receipt for demonstration only.
      </p>
    </div>
  );
}
