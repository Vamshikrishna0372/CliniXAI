import test from "node:test";
import assert from "node:assert/strict";

function validateAppointmentInput(input: {
  doctorId?: string;
  date?: string;
  startTime?: string;
  reason?: string;
}): { valid: boolean; errors: string[] } {
  const errors: string[] = [];
  if (!input.doctorId || input.doctorId.trim() === "") errors.push("Doctor is required");
  if (!input.date || !/^\d{4}-\d{2}-\d{2}$/.test(input.date)) errors.push("Valid date (YYYY-MM-DD) is required");
  if (!input.startTime || !/^\d{2}:\d{2}$/.test(input.startTime)) errors.push("Valid start time (HH:MM) is required");
  if (!input.reason || input.reason.trim().length < 3) errors.push("Reason must be at least 3 characters");
  return { valid: errors.length === 0, errors };
}

function validateBillingPayment(amountPaid: number, balanceDue: number): { valid: boolean; error?: string } {
  if (amountPaid <= 0) return { valid: false, error: "Payment amount must be greater than zero" };
  if (amountPaid > balanceDue) return { valid: false, error: "Payment amount cannot exceed balance due" };
  return { valid: true };
}

test("Appointment validation passes for valid booking input", () => {
  const res = validateAppointmentInput({
    doctorId: "DOC-RAO-001",
    date: "2026-11-20",
    startTime: "10:00",
    reason: "Routine cardiology follow-up",
  });
  assert.equal(res.valid, true);
  assert.equal(res.errors.length, 0);
});

test("Appointment validation rejects invalid dates, missing times, and short reasons", () => {
  const res = validateAppointmentInput({
    doctorId: "",
    date: "20-11-2026",
    startTime: "9am",
    reason: "Hi",
  });
  assert.equal(res.valid, false);
  assert.equal(res.errors.length, 4);
});

test("Billing payment validation enforces positive amount within balance", () => {
  assert.equal(validateBillingPayment(500, 1000).valid, true);
  assert.equal(validateBillingPayment(1000, 1000).valid, true);
  assert.equal(validateBillingPayment(0, 1000).valid, false);
  assert.equal(validateBillingPayment(-50, 1000).valid, false);
  assert.equal(validateBillingPayment(1200, 1000).valid, false);
});
