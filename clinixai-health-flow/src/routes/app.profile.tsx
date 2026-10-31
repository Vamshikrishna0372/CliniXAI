import { useEffect, useMemo, useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { Camera, Check, Edit3, Settings as SettingsIcon, X } from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/app-shell/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Progress } from "@/components/ui/progress";
import { useAuth } from "@/lib/auth-context";
import { useClinix } from "@/lib/store/clinix-store";
import { apiClient } from "@/lib/api-client";
import { ageFromDob } from "@/lib/mock/domain";

export const Route = createFileRoute("/app/profile")({
  head: () => ({ meta: [{ title: "Profile — CliniXAI" }, { name: "robots", content: "noindex" }] }),
  component: ProfilePage,
});

function initialsOf(a?: string, b?: string) {
  return `${a?.[0] ?? ""}${b?.[0] ?? ""}`.toUpperCase() || "U";
}

function ProfilePage() {
  const { user } = useAuth();
  const clinix = useClinix();
  const role = user?.role ?? "patient";

  if (role === "patient") return <PatientProfile />;
  if (role === "doctor") return <DoctorProfile />;
  if (role === "staff") return <StaffProfile />;
  return <AdminProfile />;
}

function ProfileFrame({ title, description, children }: { title: string; description: string; children: React.ReactNode }) {
  return (
    <div className="space-y-6">
      <PageHeader
        title={title}
        description={description}
        actions={
          <Button variant="outline" size="sm" className="min-h-10" asChild>
            <Link to="/app/settings"><SettingsIcon className="mr-1 h-4 w-4" /> Settings</Link>
          </Button>
        }
      />
      {children}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Patient                                                              */
/* ------------------------------------------------------------------ */
/* ------------------------------------------------------------------ */
/* Patient                                                              */
/* ------------------------------------------------------------------ */
function PatientProfile() {
  const { user } = useAuth();
  const clinix = useClinix();
  const [profile, setProfile] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);

  const [form, setForm] = useState({
    firstName: "",
    lastName: "",
    mobile: "",
    street: "",
    city: "",
    allergies: "",
    bloodGroup: "",
    emergencyName: "",
    emergencyRel: "",
    emergencyPhone: "",
  });

  const loadPatientProfile = async () => {
    try {
      const res = await apiClient.patients.getMe();
      if (res?.data) {
        setProfile(res.data);
        setForm({
          firstName: res.data.first_name || "",
          lastName: res.data.last_name || "",
          mobile: res.data.phone || "",
          street: res.data.address?.street || "",
          city: res.data.address?.city || "",
          allergies: Array.isArray(res.data.allergies) ? res.data.allergies.join(", ") : "",
          bloodGroup: res.data.blood_group || "",
          emergencyName: res.data.emergency_contact?.name || "",
          emergencyRel: res.data.emergency_contact?.relationship || "",
          emergencyPhone: res.data.emergency_contact?.phone || "",
        });
      }
    } catch (err: any) {
      toast.error(err.message || "Failed to load patient profile");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPatientProfile();
  }, []);

  const patientData = profile || {
    patient_id: user?.patientId || "PAT-ME",
    first_name: user?.firstName || "Patient",
    last_name: user?.lastName || "",
    full_name: user?.fullName || "Patient",
    email: user?.email || "",
    phone: "Not provided",
    address: { street: "Not provided", city: "Not provided" },
    blood_group: "Not provided",
    date_of_birth: "1995-01-01",
    gender: "Not specified",
    emergency_contact: { name: "Not provided", relationship: "Not provided", phone: "Not provided" },
    allergies: [],
    status: "active",
  };

  const completion = useMemo(() => {
    const fields = [
      patientData.first_name,
      patientData.last_name,
      patientData.phone && patientData.phone !== "Not provided",
      patientData.email,
      patientData.address?.street && patientData.address.street !== "Not provided",
      patientData.blood_group && patientData.blood_group !== "Not provided",
      patientData.emergency_contact?.name && patientData.emergency_contact.name !== "Not provided",
      (patientData.allergies?.length || 0) > 0,
    ];
    return Math.round((fields.filter(Boolean).length / fields.length) * 100);
  }, [patientData]);

  const save = async () => {
    setSaving(true);
    try {
      const allergyList = form.allergies.split(",").map((s: string) => s.trim()).filter(Boolean);
      const payload: any = {
        first_name: form.firstName.trim() || undefined,
        last_name: form.lastName.trim() || undefined,
        phone: form.mobile.trim() || undefined,
        address: {
          street: form.street.trim() || undefined,
          city: form.city.trim() || undefined,
        },
        allergies: allergyList,
      };

      if (form.emergencyName.trim() || form.emergencyRel.trim() || form.emergencyPhone.trim()) {
        payload.emergency_contact = {
          name: form.emergencyName.trim() || "Emergency Contact",
          relationship: form.emergencyRel.trim() || "Family",
          phone: form.emergencyPhone.trim() || "Not provided",
        };
      }

      const res = await apiClient.patients.updateMe(payload);
      if (res?.data) {
        setProfile(res.data);
      }
      setEditing(false);
      toast.success("Patient profile updated successfully");
    } catch (err: any) {
      toast.error(err.message || "Failed to update profile on server");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <ProfileFrame title="Profile" description="Your personal, contact, and basic medical information.">
        <Card><CardContent className="p-8 text-center text-sm text-muted-foreground">Loading patient profile from server...</CardContent></Card>
      </ProfileFrame>
    );
  }

  return (
    <ProfileFrame title="Profile" description="Your personal, contact, and basic medical information.">
      <div className="flex justify-end">
        {editing ? (
          <div className="flex gap-2">
            <Button variant="ghost" size="sm" className="min-h-10" disabled={saving} onClick={() => setEditing(false)}>
              <X className="mr-1 h-4 w-4" /> Cancel
            </Button>
            <Button size="sm" className="min-h-10" disabled={saving} onClick={save}>
              <Check className="mr-1 h-4 w-4" /> {saving ? "Saving..." : "Save"}
            </Button>
          </div>
        ) : (
          <Button size="sm" variant="outline" className="min-h-10" onClick={() => setEditing(true)}>
            <Edit3 className="mr-1 h-4 w-4" /> Edit
          </Button>
        )}
      </div>

      <Card>
        <CardContent className="p-5">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-sm font-semibold">Profile completion</p>
              <p className="text-xs text-muted-foreground">
                {completion < 100 ? "Add missing details to complete your health record." : "Your profile is complete."}
              </p>
            </div>
            <span className="font-display text-xl font-bold text-primary">{completion}%</span>
          </div>
          <Progress value={completion} className="mt-3 h-2" />
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-5">
          <div className="flex items-start gap-4">
            <Avatar className="h-20 w-20">
              <AvatarFallback className="bg-primary/10 text-primary text-xl font-bold">
                {initialsOf(patientData.first_name, patientData.last_name)}
              </AvatarFallback>
            </Avatar>
            <div className="min-w-0 flex-1">
              <p className="font-display text-lg font-bold">
                {patientData.full_name || `${patientData.first_name} ${patientData.last_name}`.trim()}
              </p>
              <p className="text-xs text-muted-foreground">
                {patientData.patient_id} • {patientData.gender || "Not specified"} • {ageFromDob(patientData.date_of_birth)} yrs
              </p>
              <Badge variant="secondary" className="mt-1">
                {patientData.status || "active"} patient
              </Badge>
            </div>
            <Button variant="outline" size="sm" className="min-h-10" onClick={() => toast.info("Photo upload is a mock action in this demo")}>
              <Camera className="mr-1 h-4 w-4" /> Change photo
            </Button>
          </div>
          <div className="mt-5 grid gap-4 sm:grid-cols-2">
            <Field
              label="First Name"
              id="pat-fname"
              value={editing ? form.firstName : patientData.first_name}
              editing={editing}
              onChange={(v) => setForm({ ...form, firstName: v })}
            />
            <Field
              label="Last Name"
              id="pat-lname"
              value={editing ? form.lastName : patientData.last_name}
              editing={editing}
              onChange={(v) => setForm({ ...form, lastName: v })}
            />
            <Field
              label="Mobile"
              id="pat-mobile"
              value={editing ? form.mobile : patientData.phone || "Not provided"}
              editing={editing}
              onChange={(v) => setForm({ ...form, mobile: v })}
            />
            <Field label="Email" id="pat-email" value={patientData.email} />
            <Field
              label="Address"
              id="pat-address"
              value={editing ? form.street : patientData.address?.street || "Not provided"}
              editing={editing}
              onChange={(v) => setForm({ ...form, street: v })}
              className="sm:col-span-2"
            />
            <Field
              label="City"
              id="pat-city"
              value={editing ? form.city : patientData.address?.city || "Not provided"}
              editing={editing}
              onChange={(v) => setForm({ ...form, city: v })}
            />
            <Field label="Postal Code" id="pat-postal" value={patientData.address?.postal_code || "Not provided"} />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-5">
          <p className="font-display text-sm font-semibold uppercase tracking-wide text-muted-foreground">Emergency contact</p>
          <div className="mt-3 grid gap-3 sm:grid-cols-3">
            <Field
              label="Name"
              id="em-name"
              value={editing ? form.emergencyName : patientData.emergency_contact?.name || "Not provided"}
              editing={editing}
              onChange={(v) => setForm({ ...form, emergencyName: v })}
            />
            <Field
              label="Relationship"
              id="em-rel"
              value={editing ? form.emergencyRel : patientData.emergency_contact?.relationship || "Not provided"}
              editing={editing}
              onChange={(v) => setForm({ ...form, emergencyRel: v })}
            />
            <Field
              label="Mobile"
              id="em-mobile"
              value={editing ? form.emergencyPhone : patientData.emergency_contact?.phone || "Not provided"}
              editing={editing}
              onChange={(v) => setForm({ ...form, emergencyPhone: v })}
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-5">
          <p className="font-display text-sm font-semibold uppercase tracking-wide text-muted-foreground">Basic medical information</p>
          <p className="mt-1 text-xs text-muted-foreground">Informational — verified clinical records in Medical Records.</p>
          <div className="mt-3 grid gap-4 sm:grid-cols-2">
            <Field label="Blood Group" id="pat-blood" value={patientData.blood_group || "Not provided"} />
            <TextField
              label="Known Allergies"
              id="pat-allergies"
              value={editing ? form.allergies : Array.isArray(patientData.allergies) ? patientData.allergies.join(", ") : "None"}
              editing={editing}
              onChange={(v) => setForm({ ...form, allergies: v })}
            />
          </div>
        </CardContent>
      </Card>
    </ProfileFrame>
  );
}

/* ------------------------------------------------------------------ */
/* Doctor                                                               */
/* ------------------------------------------------------------------ */
/* ------------------------------------------------------------------ */
/* Doctor                                                               */
/* ------------------------------------------------------------------ */
function DoctorProfile() {
  const { user } = useAuth();
  const clinix = useClinix();
  const [profile, setProfile] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);

  const [form, setForm] = useState({
    firstName: "",
    lastName: "",
    phone: "",
    specialization: "",
    qualification: "",
    experienceYears: 0,
    registrationNumber: "",
    consultationFee: 0,
  });

  const loadDoctorProfile = async () => {
    try {
      const res = await apiClient.doctors.getMe();
      if (res?.data) {
        setProfile(res.data);
        setForm({
          firstName: res.data.first_name || "",
          lastName: res.data.last_name || "",
          phone: res.data.phone || "",
          specialization: res.data.specialization || "",
          qualification: res.data.qualification || "",
          experienceYears: res.data.experience_years || 0,
          registrationNumber: res.data.registration_number || "",
          consultationFee: res.data.consultation_fee || 0,
        });
      }
    } catch (err: any) {
      toast.error(err.message || "Failed to load doctor profile");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDoctorProfile();
  }, []);

  const save = async () => {
    setSaving(true);
    try {
      const payload: any = {
        first_name: form.firstName.trim() || undefined,
        last_name: form.lastName.trim() || undefined,
        phone: form.phone.trim() || undefined,
        specialization: form.specialization.trim() || undefined,
        qualification: form.qualification.trim() || undefined,
        experience_years: form.experienceYears ? Number(form.experienceYears) : undefined,
        registration_number: form.registrationNumber.trim() || undefined,
        consultation_fee: form.consultationFee ? Number(form.consultationFee) : undefined,
      };

      const res = await apiClient.doctors.updateMe(payload);
      if (res?.data) {
        setProfile(res.data);
      }
      setEditing(false);
      toast.success("Doctor profile updated successfully");
    } catch (err: any) {
      toast.error(err.message || "Failed to update profile on server");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <ProfileFrame title="Doctor Profile" description="Your professional details and account status.">
        <Card><CardContent className="p-8 text-center text-sm text-muted-foreground">Loading doctor profile from server...</CardContent></Card>
      </ProfileFrame>
    );
  }

  const doctorData = profile || {
    doctor_id: user?.doctorId || "DOC-ME",
    full_name: user?.fullName || "Doctor",
    first_name: user?.firstName || "Doctor",
    last_name: user?.lastName || "",
    email: user?.email || "",
    phone: "",
    department_id: "General Medicine",
    specialization: "General Medicine",
    qualification: "MBBS",
    experience_years: 0,
    registration_number: "Not provided",
    consultation_fee: 500,
    status: "active",
  };

  return (
    <ProfileFrame title="Doctor Profile" description="Your professional details and account status.">
      <div className="flex justify-end">
        {editing ? (
          <div className="flex gap-2">
            <Button variant="ghost" size="sm" className="min-h-10" disabled={saving} onClick={() => setEditing(false)}>
              <X className="mr-1 h-4 w-4" /> Cancel
            </Button>
            <Button size="sm" className="min-h-10" disabled={saving} onClick={save}>
              <Check className="mr-1 h-4 w-4" /> {saving ? "Saving..." : "Save"}
            </Button>
          </div>
        ) : (
          <Button size="sm" variant="outline" className="min-h-10" onClick={() => setEditing(true)}>
            <Edit3 className="mr-1 h-4 w-4" /> Edit
          </Button>
        )}
      </div>

      <Card>
        <CardContent className="p-6 flex flex-col gap-4 sm:flex-row sm:items-center">
          <Avatar className="h-20 w-20">
            <AvatarFallback className="bg-primary/10 text-primary text-xl font-bold">
              {initialsOf(doctorData.first_name || user?.firstName, doctorData.last_name || user?.lastName)}
            </AvatarFallback>
          </Avatar>
          <div className="min-w-0 flex-1 space-y-1">
            <p className="font-display text-lg font-bold">
              {doctorData.full_name || `${doctorData.first_name} ${doctorData.last_name}`.trim()}
            </p>
            <p className="text-sm text-muted-foreground">
              {doctorData.qualification || "MBBS"} • {doctorData.specialization || "General Medicine"}
            </p>
            <p className="text-xs text-muted-foreground">
              {doctorData.doctor_id} • {doctorData.department_id || "General"} • {doctorData.experience_years || 0} yrs experience
            </p>
            <Badge variant={doctorData.status === "active" ? "secondary" : "outline"} className="mt-1 capitalize">
              {doctorData.status || "active"}
            </Badge>
          </div>
          <Button variant="outline" size="sm" className="min-h-10" onClick={() => toast.info("Photo upload is a mock action in this demo")}>
            <Camera className="mr-1 h-4 w-4" /> Change photo
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-5">
          <p className="font-display text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            Contact & professional information
          </p>
          <div className="mt-3 grid gap-4 sm:grid-cols-2">
            <Field label="Email" id="doc-email" value={doctorData.email} />
            <Field
              label="Phone"
              id="doc-phone"
              value={editing ? form.phone : doctorData.phone || "Not provided"}
              editing={editing}
              onChange={(v) => setForm({ ...form, phone: v })}
            />
            <Field
              label="First Name"
              id="doc-fname"
              value={editing ? form.firstName : doctorData.first_name}
              editing={editing}
              onChange={(v) => setForm({ ...form, firstName: v })}
            />
            <Field
              label="Last Name"
              id="doc-lname"
              value={editing ? form.lastName : doctorData.last_name}
              editing={editing}
              onChange={(v) => setForm({ ...form, lastName: v })}
            />
            <Field
              label="Specialization"
              id="doc-spec"
              value={editing ? form.specialization : doctorData.specialization || "Not provided"}
              editing={editing}
              onChange={(v) => setForm({ ...form, specialization: v })}
            />
            <Field
              label="Qualification"
              id="doc-qual"
              value={editing ? form.qualification : doctorData.qualification || "Not provided"}
              editing={editing}
              onChange={(v) => setForm({ ...form, qualification: v })}
            />
            <Field
              label="Experience (Years)"
              id="doc-exp"
              value={editing ? String(form.experienceYears) : `${doctorData.experience_years || 0} yrs`}
              editing={editing}
              onChange={(v) => setForm({ ...form, experienceYears: parseInt(v) || 0 })}
            />
            <Field
              label="Registration Number"
              id="doc-reg"
              value={editing ? form.registrationNumber : doctorData.registration_number || "Not provided"}
              editing={editing}
              onChange={(v) => setForm({ ...form, registrationNumber: v })}
            />
            <Field
              label="Consultation Fee"
              id="doc-fee"
              value={editing ? String(form.consultationFee) : `₹${doctorData.consultation_fee || 0}`}
              editing={editing}
              onChange={(v) => setForm({ ...form, consultationFee: parseFloat(v) || 0 })}
            />
            <Field label="Department" id="doc-dept" value={doctorData.department_id || "General"} />
          </div>
        </CardContent>
      </Card>
    </ProfileFrame>
  );
}

/* ------------------------------------------------------------------ */
/* Staff                                                                */
/* ------------------------------------------------------------------ */
function StaffProfile() {
  const { user } = useAuth();
  const clinix = useClinix();
  const staff = clinix.staff[0];
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({ email: staff?.email ?? user?.email ?? "", mobile: staff?.mobile ?? "", desk: staff?.desk ?? "" });

  if (!staff) return null;

  const save = () => {
    clinix.updateStaff(staff.id, { email: form.email, mobile: form.mobile, desk: form.desk });
    setEditing(false);
    toast.success("Profile updated");
  };

  return (
    <ProfileFrame title="Staff Profile" description="Your CliniXAI staff account.">
      <div className="flex justify-end">
        {editing ? (
          <div className="flex gap-2">
            <Button variant="ghost" size="sm" className="min-h-10" onClick={() => setEditing(false)}><X className="mr-1 h-4 w-4" /> Cancel</Button>
            <Button size="sm" className="min-h-10" onClick={save}><Check className="mr-1 h-4 w-4" /> Save</Button>
          </div>
        ) : (
          <Button size="sm" variant="outline" className="min-h-10" onClick={() => setEditing(true)}><Edit3 className="mr-1 h-4 w-4" /> Edit</Button>
        )}
      </div>

      <Card><CardContent className="p-6 flex flex-col gap-4 sm:flex-row sm:items-center">
        <Avatar className="h-20 w-20"><AvatarFallback className="bg-primary/10 text-primary text-xl font-bold">{staff.photoInitial || initialsOf(staff.firstName, staff.lastName)}</AvatarFallback></Avatar>
        <div className="min-w-0 flex-1 space-y-1">
          <p className="font-display text-lg font-bold">{staff.firstName} {staff.lastName}</p>
          <p className="text-sm text-muted-foreground">{staff.department} • Desk {staff.desk}</p>
          <p className="text-xs text-muted-foreground">{staff.id} • Last active {staff.lastActive}</p>
          <Badge variant={staff.status === "active" ? "secondary" : "outline"} className="mt-1 capitalize">{staff.status}</Badge>
        </div>
        <Button variant="outline" size="sm" className="min-h-10" onClick={() => toast.info("Photo upload is a mock action in this demo")}><Camera className="mr-1 h-4 w-4" /> Change photo</Button>
      </CardContent></Card>

      <Card><CardContent className="p-5">
        <p className="font-display text-sm font-semibold uppercase tracking-wide text-muted-foreground">Contact & assignment</p>
        <div className="mt-3 grid gap-4 sm:grid-cols-2">
          <Field label="Email" id="staff-email" value={form.email} editing={editing} onChange={(v) => setForm({ ...form, email: v })} />
          <Field label="Mobile" id="staff-mobile" value={form.mobile} editing={editing} onChange={(v) => setForm({ ...form, mobile: v })} />
          <Field label="Department" id="staff-dept" value={staff.department} />
          <Field label="Desk" id="staff-desk" value={form.desk} editing={editing} onChange={(v) => setForm({ ...form, desk: v })} />
        </div>
      </CardContent></Card>
    </ProfileFrame>
  );
}

/* ------------------------------------------------------------------ */
/* Admin                                                                */
/* ------------------------------------------------------------------ */
function AdminProfile() {
  const { user } = useAuth();
  const clinix = useClinix();
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({ email: user?.email ?? "", mobile: "+91 90000 00000" });

  const save = () => {
    setEditing(false);
    toast.success("Profile updated");
  };

  return (
    <ProfileFrame title="Admin Profile" description="Your hospital administrator account.">
      <div className="flex justify-end">
        {editing ? (
          <div className="flex gap-2">
            <Button variant="ghost" size="sm" className="min-h-10" onClick={() => setEditing(false)}><X className="mr-1 h-4 w-4" /> Cancel</Button>
            <Button size="sm" className="min-h-10" onClick={save}><Check className="mr-1 h-4 w-4" /> Save</Button>
          </div>
        ) : (
          <Button size="sm" variant="outline" className="min-h-10" onClick={() => setEditing(true)}><Edit3 className="mr-1 h-4 w-4" /> Edit</Button>
        )}
      </div>

      <Card><CardContent className="p-6 flex flex-col gap-4 sm:flex-row sm:items-center">
        <Avatar className="h-20 w-20"><AvatarFallback className="bg-primary/10 text-primary text-xl font-bold">{initialsOf(user?.firstName, user?.lastName)}</AvatarFallback></Avatar>
        <div className="min-w-0 flex-1 space-y-1">
          <p className="font-display text-lg font-bold">{user?.firstName} {user?.lastName}</p>
          <p className="text-sm text-muted-foreground">Hospital Administrator</p>
          <Badge variant="secondary" className="mt-1">Active</Badge>
        </div>
        <Button variant="outline" size="sm" className="min-h-10" onClick={() => toast.info("Photo upload is a mock action in this demo")}><Camera className="mr-1 h-4 w-4" /> Change photo</Button>
      </CardContent></Card>

      <Card><CardContent className="p-5">
        <p className="font-display text-sm font-semibold uppercase tracking-wide text-muted-foreground">Contact information</p>
        <div className="mt-3 grid gap-4 sm:grid-cols-2">
          <Field label="Email" id="admin-email" value={form.email} editing={editing} onChange={(v) => setForm({ ...form, email: v })} />
          <Field label="Mobile" id="admin-mobile" value={form.mobile} editing={editing} onChange={(v) => setForm({ ...form, mobile: v })} />
          <Field label="Doctors managed" id="admin-doctors" value={String(clinix.doctors.length)} />
          <Field label="Staff managed" id="admin-staff" value={String(clinix.staff.length)} />
        </div>
      </CardContent></Card>
    </ProfileFrame>
  );
}

function Field({ label, id, value, editing, onChange, className }: { label: string; id: string; value: string; editing?: boolean; onChange?: (v: string) => void; className?: string }) {
  return (
    <div className={className}>
      <Label htmlFor={id} className="text-[11px] uppercase text-muted-foreground">{label}</Label>
      {editing && onChange ? <Input id={id} value={value} onChange={(e) => onChange(e.target.value)} /> : <p id={id} className="text-sm font-medium">{value || "—"}</p>}
    </div>
  );
}
function TextField({ label, id, value, editing, onChange }: { label: string; id: string; value: string; editing?: boolean; onChange?: (v: string) => void }) {
  return (
    <div>
      <Label htmlFor={id} className="text-[11px] uppercase text-muted-foreground">{label}</Label>
      {editing && onChange ? <Textarea id={id} rows={2} value={value} onChange={(e) => onChange(e.target.value)} /> : <p id={id} className="text-sm">{value || "—"}</p>}
    </div>
  );
}
