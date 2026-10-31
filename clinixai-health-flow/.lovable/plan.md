# Phase 3 — Patient Portal & Hospital Staff Operations

Building on the Phase 2 app shell, roles, sidebar nav, cards, tables, upload, and states. No redesign, no backend, no doctor/admin workspaces.

## Approach

- **Shared mock domain** in `src/lib/mock/` — one source of truth: patients, doctors, appointments, prescriptions, AI reports, bills, receipts, documents, notifications, queue. Consistent IDs (`PAT-2026-00124`, `APT-...`, `BILL-...`, `RCT-...`) referenced across both Patient and Staff views so the workflow feels connected.
- **Shared UI primitives** in `src/components/domain/`: `StatusBadge` (appointment/billing/AI/document tokens), `AppointmentCard`, `BillCard`, `PrescriptionCard`, `DoctorCard`, `TimelineItem`, `QueueTokenCard`, `Stepper`, `MedicationTable`, `ReceiptView` — reused by both roles.
- **Route layer** replaces the `/app/$section` placeholder with per-slug real routes matching the Phase 2 nav slugs. Uses TanStack file-based routes: `app.appointments.tsx`, `app.appointments.$id.tsx`, `app.book.tsx`, `app.doctors.tsx`, `app.doctors.$id.tsx`, `app.medical-records.tsx`, `app.prescriptions.tsx`, `app.prescriptions.$id.tsx`, `app.ai-reports.tsx`, `app.ai-reports.$id.tsx`, `app.bills.tsx`, `app.bills.$id.tsx`, `app.timeline.tsx`, `app.qr-card.tsx`, `app.notifications.tsx`, `app.profile.tsx`, `app.settings.tsx`, plus staff: `app.patients.tsx`, `app.patients.$id.tsx`, `app.patient-registration.tsx`, `app.check-in.tsx`, `app.queue.tsx`, `app.billing.tsx`, `app.billing.$id.tsx`, `app.receipts.tsx`, `app.documents.tsx`. Fallback `$section` route stays for slugs not yet routed.
- **Dashboards** — replace generic Phase 2 dashboard content with role-specific patient and staff dashboards (real widget layouts per spec; existing admin/doctor content preserved).
- **Command palette & notifications** extended with Phase 3 entities and categories — same components.
- **Mobile-first** — bottom-sheet filters (`Sheet`), responsive card fallbacks for tables (already in `DataTable`), sticky mobile actions on booking, prominent tokens on queue cards.
- **No online payment**, no Razorpay. Billing UI records Cash/UPI/Card taken at reception + optional reference field.
- **AI screens** UI-only, with the required disclaimer banner. Mock Grad-CAM images use generated placeholders/gradients — no inference.

## File plan (high-level)

```text
src/lib/mock/
  ids.ts              # id generators & formatters
  patients.ts         # 6-8 realistic fictional patients
  doctors.ts          # 8-10 doctors with departments, slots
  appointments.ts     # cross-referenced with patients/doctors
  prescriptions.ts
  ai-reports.ts
  bills.ts + receipts.ts
  documents.ts
  timeline.ts         # derived from other collections
  queue.ts
  notifications-patient.ts + notifications-staff.ts
  index.ts

src/components/domain/
  status-badge.tsx
  appointment-card.tsx
  bill-card.tsx
  prescription-card.tsx
  doctor-card.tsx
  timeline.tsx
  queue-token.tsx
  stepper.tsx
  medication-table.tsx
  receipt-view.tsx
  qr-placeholder.tsx  # SVG QR-like pattern (no lib)
  filter-sheet.tsx    # mobile bottom-sheet wrapper

src/routes/  (new files listed above)
src/routes/app.index.tsx  (extend patient/staff branches)
src/routes/app.$section.tsx  (kept as fallback)
src/lib/notifications-mock.ts  (extend categories)
src/components/app-shell/command-palette.tsx  (extend actions per role)
```

## Scope boundaries

- Doctor and Admin sections remain as-is (their nav still works via the fallback placeholder). Only Patient + Staff slugs get real pages.
- No real QR generation library — use a deterministic SVG "QR-like" module pattern placeholder inside a bordered card. Clearly a mock.
- No PDF generation — Print/Download buttons trigger `window.print()`-friendly views only.
- No real camera scanner — QR check-in shows a styled scanner viewport placeholder + manual code input.
- Bills totals compute client-side from mock line items.
- Reused: existing `DataTable`, `FileUpload`, `KpiCard`, `ChartContainer`, `ListCard`, `PageHeader`, `EmptyState`, `Skeleton`, `Sheet`, `Dialog`, `Tabs`, `Command`.

## Delivery order (single response, parallel writes)

1. Mock domain + shared domain components.
2. Patient routes (dashboard content update, book flow, appointments, records, prescriptions, AI reports, bills, timeline, QR card, notifications, profile, settings).
3. Staff routes (dashboard content, patients, registration, check-in, queue, billing, receipts, documents, notifications, profile).
4. Command palette + notifications extension.
5. Mobile pass verification.

Because this is a large but well-scoped scaffolding effort with realistic mock data (no logic risk), I'll build it in one implementation pass rather than iterating page-by-page.
