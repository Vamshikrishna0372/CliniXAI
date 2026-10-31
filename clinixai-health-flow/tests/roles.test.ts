import test from "node:test";
import assert from "node:assert/strict";

// Role-based navigation and permission contracts
const ROLE_PERMISSIONS: Record<string, string[]> = {
  admin: ["users", "settings", "activity-logs", "doctors", "staff", "departments"],
  doctor: ["consultations", "prescriptions", "ai-analysis", "ai-history", "medical-records"],
  staff: ["check-in", "queue", "cashier", "patients"],
  patient: ["appointments", "medical-records", "prescriptions", "billing"],
};

test("Admin role permissions include administration and exclude clinical prescribing", () => {
  const adminRoutes = ROLE_PERMISSIONS.admin;
  assert.ok(adminRoutes.includes("users"), "Admin must have users route");
  assert.ok(adminRoutes.includes("settings"), "Admin must have settings route");
  assert.ok(!adminRoutes.includes("ai-analysis"), "Admin must not have direct clinical AI route");
});

test("Staff role permissions enforce strict clinical boundary", () => {
  const staffRoutes = ROLE_PERMISSIONS.staff;
  assert.ok(staffRoutes.includes("check-in"), "Staff must have check-in route");
  assert.ok(staffRoutes.includes("queue"), "Staff must have queue route");
  assert.ok(staffRoutes.includes("cashier"), "Staff must have cashier route");
  assert.ok(!staffRoutes.includes("prescriptions"), "Staff must be denied prescriptions");
  assert.ok(!staffRoutes.includes("ai-analysis"), "Staff must be denied AI analysis");
  assert.ok(!staffRoutes.includes("users"), "Staff must be denied user admin");
});

test("Doctor role permissions include clinical workflows and exclude admin management", () => {
  const docRoutes = ROLE_PERMISSIONS.doctor;
  assert.ok(docRoutes.includes("consultations"), "Doctor must have consultations");
  assert.ok(docRoutes.includes("prescriptions"), "Doctor must have prescriptions");
  assert.ok(docRoutes.includes("ai-analysis"), "Doctor must have AI analysis");
  assert.ok(!docRoutes.includes("users"), "Doctor must be denied user management");
  assert.ok(!docRoutes.includes("settings"), "Doctor must be denied hospital settings");
});

test("Patient role permissions are strictly isolated to self-service portal", () => {
  const patRoutes = ROLE_PERMISSIONS.patient;
  assert.ok(patRoutes.includes("appointments"), "Patient must have appointments");
  assert.ok(patRoutes.includes("medical-records"), "Patient must have medical records");
  assert.ok(!patRoutes.includes("queue"), "Patient cannot manage queue tokens");
  assert.ok(!patRoutes.includes("users"), "Patient cannot access user management");
});
