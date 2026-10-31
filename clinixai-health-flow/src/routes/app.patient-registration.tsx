import { useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { Check, Copy, Loader2 } from "lucide-react";
import { PageHeader } from "@/components/app-shell/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";
import { useClinix } from "@/lib/store/clinix-store";
import { apiClient } from "@/lib/api-client";

export const Route = createFileRoute("/app/patient-registration")({
  head: () => ({ meta: [{ title: "Register Patient — CliniXAI" }, { name: "robots", content: "noindex" }] }),
  component: RegisterPatientPage,
});

const emptyForm = { firstName: "", lastName: "", dob: "", gender: "Female", mobile: "", email: "", address: "", city: "", state: "", postal: "", emgName: "", emgRel: "", emgMobile: "", bloodGroup: "O+", allergies: "", conditions: "" };

function RegisterPatientPage() {
  const { registerPatient } = useClinix();
  const [submitting, setSubmitting] = useState(false);
  const [created, setCreated] = useState<{ id: string; name: string; date: string } | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => setForm({ ...form, [k]: e.target.value });

  const validate = () => {
    const e: Record<string, string> = {};
    if (!form.firstName.trim()) e.firstName = "Required";
    if (!form.lastName.trim()) e.lastName = "Required";
    if (!/^\d{10}$/.test(form.mobile.trim())) e.mobile = "Enter a valid 10-digit mobile number";
    if (form.email && !/^\S+@\S+\.\S+$/.test(form.email)) e.email = "Invalid email";
    if (!form.dob) e.dob = "Required";
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const submit = async (ev: React.FormEvent) => {
    ev.preventDefault();
    if (!validate()) { toast.error("Please fix the highlighted fields"); return; }
    setSubmitting(true);
    try {
      const payload: any = {
        first_name: form.firstName.trim(),
        last_name: form.lastName.trim(),
        date_of_birth: form.dob,
        gender: (form.gender || "Female").toLowerCase(),
        phone: form.mobile.trim(),
        email: form.email.trim() || undefined,
        blood_group: form.bloodGroup || undefined,
        allergies: form.allergies ? form.allergies.split(",").map((a) => a.trim()).filter(Boolean) : [],
      };
      if (form.address || form.city || form.state || form.postal) {
        payload.address = {
          street: form.address || undefined,
          city: form.city || undefined,
          state: form.state || undefined,
          postal_code: form.postal || undefined,
          country: "India",
        };
      }
      if (form.emgName && form.emgRel && form.emgMobile) {
        payload.emergency_contact = {
          name: form.emgName.trim(),
          relationship: form.emgRel.trim(),
          phone: form.emgMobile.trim(),
        };
      }
      const res = await apiClient.patients.create(payload);
      const newPatId = res?.data?.patient_id || res?.data?.id || `PAT-${Date.now().toString().slice(-6)}`;

      // Update in-memory fallback store as well
      registerPatient({
        firstName: form.firstName.trim(),
        lastName: form.lastName.trim(),
        dob: form.dob,
        gender: form.gender as "Male" | "Female" | "Other",
        mobile: form.mobile.trim(),
        email: form.email.trim(),
        address: form.address,
        city: form.city,
        state: form.state,
        postal: form.postal,
        bloodGroup: form.bloodGroup,
        allergies: form.allergies ? form.allergies.split(",").map((a) => a.trim()).filter(Boolean) : [],
        conditions: form.conditions ? form.conditions.split(",").map((a) => a.trim()).filter(Boolean) : [],
        medications: [],
        emergency: { name: form.emgName, relationship: form.emgRel, mobile: form.emgMobile },
      });

      setCreated({ id: newPatId, name: `${form.firstName.trim()} ${form.lastName.trim()}`, date: new Date().toLocaleDateString("en-IN") });
      toast.success("Patient registered successfully", { description: newPatId });
    } catch (err: any) {
      const msg = err?.message || "Patient registration failed";
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  };

  const registerAnother = () => { setForm(emptyForm); setErrors({}); setCreated(null); };

  if (created) {
    return (
      <div className="space-y-6">
        <PageHeader title="Registration complete" description="Patient added successfully." />
        <Card><CardContent className="p-6 text-center">
          <span className="mx-auto grid h-14 w-14 place-items-center rounded-full bg-success/15 text-success"><Check className="h-7 w-7" /></span>
          <p className="mt-3 font-display text-lg font-bold">{created.name}</p>
          <p className="mt-1 flex items-center justify-center gap-2 text-sm text-muted-foreground">
            {created.id}
            <button type="button" aria-label="Copy patient ID" onClick={() => { navigator.clipboard.writeText(created.id); toast.success("Copied"); }} className="text-primary"><Copy className="h-3.5 w-3.5" /></button>
          </p>
          <p className="mt-1 text-xs text-muted-foreground">Registered {created.date}</p>
          <div className="mt-6 flex flex-wrap justify-center gap-2">
            <Button asChild variant="outline"><Link to="/app/appointments">Book appointment</Link></Button>
            <Button asChild variant="outline"><Link to="/app/check-in">Check in now</Link></Button>
            <Button asChild variant="outline"><Link to="/app/patients">View directory</Link></Button>
            <Button onClick={registerAnother}>Register another</Button>
          </div>
        </CardContent></Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Register Walk-In Patient" description="Create a new patient record for a walk-in visitor." />
      <form onSubmit={submit} noValidate className="space-y-5">
        <Card><CardContent className="p-5 space-y-4">
          <p className="font-display text-sm font-semibold uppercase text-muted-foreground">Personal</p>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="First name*" error={errors.firstName}><Input value={form.firstName} onChange={set("firstName")} required aria-invalid={!!errors.firstName} /></Field>
            <Field label="Last name*" error={errors.lastName}><Input value={form.lastName} onChange={set("lastName")} required aria-invalid={!!errors.lastName} /></Field>
            <Field label="Date of birth*" error={errors.dob}><Input type="date" value={form.dob} onChange={set("dob")} aria-invalid={!!errors.dob} /></Field>
            <Field label="Gender">
              <Select value={form.gender} onValueChange={(v) => setForm({ ...form, gender: v })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent><SelectItem value="Female">Female</SelectItem><SelectItem value="Male">Male</SelectItem><SelectItem value="Other">Other</SelectItem></SelectContent>
              </Select>
            </Field>
            <Field label="Mobile*" error={errors.mobile}><Input value={form.mobile} onChange={set("mobile")} required aria-invalid={!!errors.mobile} placeholder="10-digit number" /></Field>
            <Field label="Email" error={errors.email}><Input type="email" value={form.email} onChange={set("email")} aria-invalid={!!errors.email} /></Field>
          </div>
        </CardContent></Card>
        <Card><CardContent className="p-5 space-y-4">
          <p className="font-display text-sm font-semibold uppercase text-muted-foreground">Address</p>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Street" className="sm:col-span-2"><Input value={form.address} onChange={set("address")} /></Field>
            <Field label="City"><Input value={form.city} onChange={set("city")} /></Field>
            <Field label="State"><Input value={form.state} onChange={set("state")} /></Field>
            <Field label="Postal code"><Input value={form.postal} onChange={set("postal")} /></Field>
          </div>
        </CardContent></Card>
        <Card><CardContent className="p-5 space-y-4">
          <p className="font-display text-sm font-semibold uppercase text-muted-foreground">Emergency contact</p>
          <div className="grid gap-3 sm:grid-cols-3">
            <Field label="Name"><Input value={form.emgName} onChange={set("emgName")} /></Field>
            <Field label="Relationship"><Input value={form.emgRel} onChange={set("emgRel")} /></Field>
            <Field label="Mobile"><Input value={form.emgMobile} onChange={set("emgMobile")} /></Field>
          </div>
        </CardContent></Card>
        <Card><CardContent className="p-5 space-y-4">
          <p className="font-display text-sm font-semibold uppercase text-muted-foreground">Basic medical (optional)</p>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Blood group">
              <Select value={form.bloodGroup} onValueChange={(v) => setForm({ ...form, bloodGroup: v })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>{["O+","O-","A+","A-","B+","B-","AB+","AB-"].map((b) => <SelectItem key={b} value={b}>{b}</SelectItem>)}</SelectContent>
              </Select>
            </Field>
            <Field label="Known allergies (comma separated)"><Textarea rows={2} value={form.allergies} onChange={set("allergies")} /></Field>
            <Field label="Existing conditions (comma separated)" className="sm:col-span-2"><Textarea rows={2} value={form.conditions} onChange={set("conditions")} /></Field>
          </div>
        </CardContent></Card>
        <div className="flex justify-end">
          <Button type="submit" size="lg" disabled={submitting}>
            {submitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Register patient
          </Button>
        </div>
      </form>
    </div>
  );
}

function Field({ label, children, className, error }: { label: string; children: React.ReactNode; className?: string; error?: string }) {
  return <div className={className}><Label className="mb-1 block text-xs">{label}</Label>{children}{error && <p className="mt-1 text-xs text-destructive">{error}</p>}</div>;
}
