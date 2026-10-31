import { useMemo, useState, useEffect } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Laptop, Loader2, Monitor, Smartphone, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { apiClient } from "@/lib/api-client";
import { PageHeader } from "@/components/app-shell/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription,
  AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { useAuth } from "@/lib/auth-context";
import { useTheme, type Theme } from "@/lib/theme-context";
import { useClinix } from "@/lib/store/clinix-store";
import { NAV_BY_ROLE } from "@/lib/roles";

export const Route = createFileRoute("/app/settings")({
  head: () => ({ meta: [{ title: "Settings — CliniXAI" }, { name: "robots", content: "noindex" }] }),
  component: SettingsPage,
});

type NotifCategory = "Appointment reminders" | "AI report ready" | "Bill generated" | "Prescription refill" | "System announcements";
type Channel = "email" | "push" | "sms";
type NotifMatrix = Record<NotifCategory, Record<Channel, boolean>>;

const DEFAULT_NOTIF_MATRIX: NotifMatrix = {
  "Appointment reminders": { email: true, push: true, sms: false },
  "AI report ready": { email: true, push: true, sms: false },
  "Bill generated": { email: true, push: false, sms: false },
  "Prescription refill": { email: false, push: true, sms: false },
  "System announcements": { email: false, push: false, sms: false },
};

type Session = { id: string; device: string; icon: "laptop" | "phone" | "desktop"; location: string; lastActive: string; current?: boolean };

const DEFAULT_SESSIONS: Session[] = [
  { id: "S-1", device: "Chrome on macOS", icon: "laptop", location: "Bengaluru, IN", lastActive: "Active now", current: true },
  { id: "S-2", device: "CliniXAI app — iPhone 14", icon: "phone", location: "Bengaluru, IN", lastActive: "2 hours ago" },
  { id: "S-3", device: "Edge on Windows", icon: "desktop", location: "Mumbai, IN", lastActive: "3 days ago" },
];

function sessionIcon(icon: Session["icon"]) {
  if (icon === "phone") return Smartphone;
  if (icon === "desktop") return Monitor;
  return Laptop;
}

function SettingsPage() {
  const { user, signOut } = useAuth();
  const { theme, setTheme } = useTheme();
  const clinix = useClinix();
  const role = user?.role ?? "patient";
  const isAdmin = role === "admin";

  /* ---------- Account ---------- */
  const [firstName, setFirstName] = useState(user?.firstName ?? "");
  const [lastName, setLastName] = useState(user?.lastName ?? "");
  const [email, setEmail] = useState(user?.email ?? "");
  const [phone, setPhone] = useState("+91 98765 43210");
  const [pwOpen, setPwOpen] = useState(false);
  const [pwSaving, setPwSaving] = useState(false);
  const [currentPw, setCurrentPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [confirmPw, setConfirmPw] = useState("");

  const saveAccount = () => {
    toast.success("Account details saved");
    clinix.log({ user: `${firstName} ${lastName}`.trim() || "User", role, action: "Updated account settings", entity: "Settings" });
  };

  const changePassword = () => {
    if (!currentPw || !newPw || newPw.length < 6) {
      toast.error("Enter your current password and a new password of at least 6 characters.");
      return;
    }
    if (newPw !== confirmPw) {
      toast.error("New password and confirmation do not match.");
      return;
    }
    setPwSaving(true);
    setTimeout(() => {
      setPwSaving(false);
      setPwOpen(false);
      setCurrentPw(""); setNewPw(""); setConfirmPw("");
      toast.success("Password updated successfully");
    }, 700);
  };

  /* ---------- Preferences ---------- */
  const [language, setLanguage] = useState("en");
  const [timezone, setTimezone] = useState("Asia/Kolkata");
  const [dateFormat, setDateFormat] = useState("DD/MM/YYYY");
  const nav = NAV_BY_ROLE[role] ?? [];
  const [landingSlug, setLandingSlug] = useState(nav[0]?.slug ?? "");

  const savePreferences = () => toast.success("Preferences saved");

  /* ---------- Notifications ---------- */
  const [notifMatrix, setNotifMatrix] = useState<NotifMatrix>(DEFAULT_NOTIF_MATRIX);
  const toggleNotif = (cat: NotifCategory, ch: Channel) => {
    setNotifMatrix((m) => ({ ...m, [cat]: { ...m[cat], [ch]: !m[cat][ch] } }));
  };

  /* ---------- Privacy ---------- */
  const [shareData, setShareData] = useState(false);
  const [marketing, setMarketing] = useState(true);
  const [sessions, setSessions] = useState<Session[]>(DEFAULT_SESSIONS);
  const revokeSession = (id: string) => {
    setSessions((s) => s.filter((x) => x.id !== id));
    toast.success("Session revoked");
  };
  const downloadMyData = () => {
    const payload = { user, accountPreferences: { language, timezone, dateFormat }, notifications: notifMatrix, exportedAt: new Date().toISOString() };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = "clinixai-my-data.json";
    document.body.appendChild(a); a.click(); a.remove();
    URL.revokeObjectURL(url);
    toast.success("Your data export has started downloading");
  };
  const [deleteConfirm, setDeleteConfirm] = useState("");
  const deleteAccount = async () => {
    toast.success("Account deletion requested. You have been signed out.");
    await signOut();
  };

  /* ---------- Appearance ---------- */
  const [density, setDensity] = useState<"comfortable" | "compact">("comfortable");
  const [reducedMotion, setReducedMotion] = useState(false);

  /* ---------- Admin: hospital settings ---------- */
  const [hospitalName, setHospitalName] = useState("CliniXAI Multispecialty Hospital");
  const [openTime, setOpenTime] = useState("08:00");
  const [closeTime, setCloseTime] = useState("20:00");
  const [aiAutoSuggest, setAiAutoSuggest] = useState(true);
  const [aiConfidenceThreshold, setAiConfidenceThreshold] = useState("70");

  useEffect(() => {
    if (isAdmin) {
      apiClient.admin.getSettings()
        .then((res: any) => {
          if (res && res.data) {
            if (res.data.hospital_name) setHospitalName(res.data.hospital_name);
            if (res.data.opening_time) setOpenTime(res.data.opening_time);
            if (res.data.closing_time) setCloseTime(res.data.closing_time);
            if (res.data.ai_auto_suggest !== undefined) setAiAutoSuggest(res.data.ai_auto_suggest);
            if (res.data.ai_confidence_threshold !== undefined) {
              setAiConfidenceThreshold(String(res.data.ai_confidence_threshold));
            }
          }
        })
        .catch((err: any) => console.warn("Could not load hospital settings:", err));
    }
  }, [isAdmin]);

  const saveHospitalSettings = async () => {
    try {
      await apiClient.admin.updateSettings({
        hospital_name: hospitalName,
        opening_time: openTime,
        closing_time: closeTime,
        ai_auto_suggest: aiAutoSuggest,
        ai_confidence_threshold: Number(aiConfidenceThreshold),
      });
      toast.success("Hospital settings saved & persisted to database");
      clinix.log({
        user: `${firstName} ${lastName}`.trim() || "Admin",
        role: "admin",
        action: "Updated hospital settings",
        entity: "Hospital",
      });
    } catch (err: any) {
      toast.error(err?.message || "Failed to update hospital settings");
    }
  };

  const tabs = useMemo(() => {
    const base = ["account", "preferences", "notifications", "privacy", "appearance"];
    return isAdmin ? [...base, "hospital"] : base;
  }, [isAdmin]);

  return (
    <div className="space-y-6">
      <PageHeader title="Settings" description="Manage your account, preferences, notifications, privacy, and appearance." />

      <Tabs defaultValue="account" className="space-y-4">
        <TabsList className="flex h-auto flex-wrap justify-start gap-1 bg-transparent p-0">
          {tabs.map((t) => (
            <TabsTrigger key={t} value={t} className="min-h-10 capitalize data-[state=active]:bg-primary data-[state=active]:text-primary-foreground">
              {t === "hospital" ? "Hospital" : t}
            </TabsTrigger>
          ))}
        </TabsList>

        {/* Account */}
        <TabsContent value="account">
          <Section title="Account">
            <div className="grid gap-4 py-3 sm:grid-cols-2">
              <div>
                <Label htmlFor="settings-first-name">First name</Label>
                <Input id="settings-first-name" value={firstName} onChange={(e) => setFirstName(e.target.value)} />
              </div>
              <div>
                <Label htmlFor="settings-last-name">Last name</Label>
                <Input id="settings-last-name" value={lastName} onChange={(e) => setLastName(e.target.value)} />
              </div>
              <div>
                <Label htmlFor="settings-email">Email</Label>
                <Input id="settings-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
              </div>
              <div>
                <Label htmlFor="settings-phone">Phone</Label>
                <Input id="settings-phone" type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} />
              </div>
            </div>
            <Row label="Password" description="Update your password regularly to keep your account secure">
              <Dialog open={pwOpen} onOpenChange={setPwOpen}>
                <DialogTrigger asChild>
                  <Button variant="outline" size="sm" className="min-h-10">Change password</Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>Change password</DialogTitle>
                    <DialogDescription>Enter your current password and choose a new one.</DialogDescription>
                  </DialogHeader>
                  <div className="space-y-3">
                    <div>
                      <Label htmlFor="pw-current">Current password</Label>
                      <Input id="pw-current" type="password" value={currentPw} onChange={(e) => setCurrentPw(e.target.value)} />
                    </div>
                    <div>
                      <Label htmlFor="pw-new">New password</Label>
                      <Input id="pw-new" type="password" value={newPw} onChange={(e) => setNewPw(e.target.value)} />
                    </div>
                    <div>
                      <Label htmlFor="pw-confirm">Confirm new password</Label>
                      <Input id="pw-confirm" type="password" value={confirmPw} onChange={(e) => setConfirmPw(e.target.value)} />
                    </div>
                  </div>
                  <DialogFooter>
                    <Button variant="ghost" onClick={() => setPwOpen(false)}>Cancel</Button>
                    <Button onClick={changePassword} disabled={pwSaving}>
                      {pwSaving && <Loader2 className="mr-1 h-4 w-4 animate-spin" />} Update password
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
            </Row>
            <div className="flex justify-end pt-3">
              <Button size="sm" className="min-h-10" onClick={saveAccount}>Save account</Button>
            </div>
          </Section>
        </TabsContent>

        {/* Preferences */}
        <TabsContent value="preferences">
          <Section title="Preferences">
            <Row label="Language" description="Interface display language">
              <Select value={language} onValueChange={setLanguage}>
                <SelectTrigger className="w-40" aria-label="Language"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="en">English</SelectItem>
                  <SelectItem value="hi">Hindi</SelectItem>
                  <SelectItem value="kn">Kannada</SelectItem>
                </SelectContent>
              </Select>
            </Row>
            <Row label="Timezone" description="Used for appointment and report timestamps">
              <Select value={timezone} onValueChange={setTimezone}>
                <SelectTrigger className="w-48" aria-label="Timezone"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="Asia/Kolkata">Asia/Kolkata (IST)</SelectItem>
                  <SelectItem value="Asia/Dubai">Asia/Dubai (GST)</SelectItem>
                  <SelectItem value="UTC">UTC</SelectItem>
                </SelectContent>
              </Select>
            </Row>
            <Row label="Date format" description="How dates are displayed across the app">
              <Select value={dateFormat} onValueChange={setDateFormat}>
                <SelectTrigger className="w-40" aria-label="Date format"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="DD/MM/YYYY">DD/MM/YYYY</SelectItem>
                  <SelectItem value="MM/DD/YYYY">MM/DD/YYYY</SelectItem>
                  <SelectItem value="YYYY-MM-DD">YYYY-MM-DD</SelectItem>
                </SelectContent>
              </Select>
            </Row>
            <Row label="Default landing section" description="Page shown right after you sign in">
              <Select value={landingSlug} onValueChange={setLandingSlug}>
                <SelectTrigger className="w-56" aria-label="Default landing section"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {nav.map((n) => <SelectItem key={n.slug || "dashboard"} value={n.slug}>{n.title}</SelectItem>)}
                </SelectContent>
              </Select>
            </Row>
            <div className="flex justify-end pt-3">
              <Button size="sm" className="min-h-10" onClick={savePreferences}>Save preferences</Button>
            </div>
          </Section>
        </TabsContent>

        {/* Notifications */}
        <TabsContent value="notifications">
          <Card><CardContent className="overflow-x-auto p-5">
            <p className="mb-3 font-display text-sm font-semibold uppercase tracking-wide text-muted-foreground">Notification settings</p>
            <table className="w-full min-w-[480px] text-sm">
              <thead>
                <tr className="text-left text-xs uppercase text-muted-foreground">
                  <th className="py-2">Category</th>
                  <th className="py-2 text-center">Email</th>
                  <th className="py-2 text-center">Push</th>
                  <th className="py-2 text-center">SMS</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {(Object.keys(notifMatrix) as NotifCategory[]).map((cat) => (
                  <tr key={cat}>
                    <td className="py-3 pr-3 font-medium">{cat}</td>
                    {(["email", "push", "sms"] as Channel[]).map((ch) => (
                      <td key={ch} className="py-3 text-center">
                        <Switch
                          aria-label={`${cat} via ${ch}`}
                          checked={notifMatrix[cat][ch]}
                          onCheckedChange={() => toggleNotif(cat, ch)}
                        />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="flex justify-end pt-4">
              <Button size="sm" className="min-h-10" onClick={() => toast.success("Notification preferences saved")}>Save notification settings</Button>
            </div>
          </CardContent></Card>
        </TabsContent>

        {/* Privacy */}
        <TabsContent value="privacy" className="space-y-4">
          <Section title="Privacy">
            <Row label="Share anonymized data" description="Help improve CliniXAI's clinical models">
              <Switch checked={shareData} onCheckedChange={setShareData} aria-label="Share anonymized data" />
            </Row>
            <Row label="Marketing emails" description="Occasional health tips and product updates">
              <Switch checked={marketing} onCheckedChange={setMarketing} aria-label="Marketing emails" />
            </Row>
            <Row label="Download my data" description="Export a copy of your account data as JSON">
              <Button variant="outline" size="sm" className="min-h-10" onClick={downloadMyData}>Download</Button>
            </Row>
          </Section>

          <Card><CardContent className="p-5">
            <p className="mb-3 font-display text-sm font-semibold uppercase tracking-wide text-muted-foreground">Active sessions & devices</p>
            <div className="divide-y divide-border">
              {sessions.map((s) => {
                const Icon = sessionIcon(s.icon);
                return (
                  <div key={s.id} className="flex items-center justify-between gap-3 py-3">
                    <div className="flex items-center gap-3">
                      <Icon className="h-5 w-5 shrink-0 text-muted-foreground" />
                      <div className="min-w-0">
                        <p className="text-sm font-medium">{s.device} {s.current && <Badge variant="secondary" className="ml-1 align-middle text-[10px]">This device</Badge>}</p>
                        <p className="text-xs text-muted-foreground">{s.location} • {s.lastActive}</p>
                      </div>
                    </div>
                    {!s.current && (
                      <Button variant="ghost" size="sm" className="min-h-10 text-destructive" onClick={() => revokeSession(s.id)} aria-label={`Revoke session on ${s.device}`}>
                        <Trash2 className="mr-1 h-4 w-4" /> Revoke
                      </Button>
                    )}
                  </div>
                );
              })}
              {sessions.length === 0 && <p className="py-3 text-sm text-muted-foreground">No other active sessions.</p>}
            </div>
          </CardContent></Card>

          <Card className="border-destructive/40"><CardContent className="p-5">
            <p className="mb-1 font-display text-sm font-semibold uppercase tracking-wide text-destructive">Danger zone</p>
            <p className="mb-3 text-xs text-muted-foreground">Deleting your account permanently removes access to CliniXAI. This action cannot be undone.</p>
            <AlertDialog onOpenChange={(o) => !o && setDeleteConfirm("")}>
              <AlertDialogTrigger asChild>
                <Button variant="destructive" size="sm" className="min-h-10">Delete account</Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Delete your account?</AlertDialogTitle>
                  <AlertDialogDescription>
                    Type <span className="font-semibold text-foreground">DELETE</span> to confirm. This is permanent and cannot be undone.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <Input aria-label="Type DELETE to confirm" value={deleteConfirm} onChange={(e) => setDeleteConfirm(e.target.value)} placeholder="DELETE" />
                <AlertDialogFooter>
                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                  <AlertDialogAction disabled={deleteConfirm !== "DELETE"} onClick={deleteAccount} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
                    Delete account
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </CardContent></Card>
        </TabsContent>

        {/* Appearance */}
        <TabsContent value="appearance">
          <Section title="Appearance">
            <Row label="Theme" description="Choose the interface theme">
              <Select value={theme} onValueChange={(v) => setTheme(v as Theme)}>
                <SelectTrigger className="w-40" aria-label="Theme"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="light">Light</SelectItem>
                  <SelectItem value="dark">Dark</SelectItem>
                  <SelectItem value="system">System</SelectItem>
                </SelectContent>
              </Select>
            </Row>
            <Row label="Density" description="Adjust spacing for tables and lists">
              <Select value={density} onValueChange={(v) => setDensity(v as typeof density)}>
                <SelectTrigger className="w-40" aria-label="Density"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="comfortable">Comfortable</SelectItem>
                  <SelectItem value="compact">Compact</SelectItem>
                </SelectContent>
              </Select>
            </Row>
            <Row label="Reduced motion" description="Minimize animations and transitions">
              <Switch checked={reducedMotion} onCheckedChange={setReducedMotion} aria-label="Reduced motion" />
            </Row>
            <div className="flex justify-end pt-3">
              <Button size="sm" className="min-h-10" onClick={() => toast.success("Appearance preferences saved")}>Save appearance</Button>
            </div>
          </Section>
        </TabsContent>

        {/* Admin: hospital */}
        {isAdmin && (
          <TabsContent value="hospital">
            <Section title="Hospital settings">
              <div className="grid gap-4 py-3 sm:grid-cols-2">
                <div>
                  <Label htmlFor="hospital-name">Hospital name</Label>
                  <Input id="hospital-name" value={hospitalName} onChange={(e) => setHospitalName(e.target.value)} />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <Label htmlFor="hospital-open">Opening time</Label>
                    <Input id="hospital-open" type="time" value={openTime} onChange={(e) => setOpenTime(e.target.value)} />
                  </div>
                  <div>
                    <Label htmlFor="hospital-close">Closing time</Label>
                    <Input id="hospital-close" type="time" value={closeTime} onChange={(e) => setCloseTime(e.target.value)} />
                  </div>
                </div>
              </div>
              <Row label="Departments" description={`${clinix.departments.length} departments configured`}>
                <Button variant="outline" size="sm" className="min-h-10" asChild>
                  <a href="/app/departments">Manage departments</a>
                </Button>
              </Row>
              <Row label="AI auto-suggest diagnosis" description="Suggest likely conditions to doctors during AI analysis">
                <Switch checked={aiAutoSuggest} onCheckedChange={setAiAutoSuggest} aria-label="AI auto-suggest diagnosis" />
              </Row>
              <Row label="AI confidence threshold" description="Minimum confidence (%) before flagging a report for review">
                <Select value={aiConfidenceThreshold} onValueChange={setAiConfidenceThreshold}>
                  <SelectTrigger className="w-28" aria-label="AI confidence threshold"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {["50", "60", "70", "80", "90"].map((v) => <SelectItem key={v} value={v}>{v}%</SelectItem>)}
                  </SelectContent>
                </Select>
              </Row>
              <div className="flex justify-end pt-3">
                <Button size="sm" className="min-h-10" onClick={saveHospitalSettings}>Save hospital settings</Button>
              </div>
            </Section>
          </TabsContent>
        )}
      </Tabs>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Card><CardContent className="p-5">
      <p className="mb-3 font-display text-sm font-semibold uppercase tracking-wide text-muted-foreground">{title}</p>
      <div className="divide-y divide-border">{children}</div>
    </CardContent></Card>
  );
}
function Row({ label, description, children }: { label: string; description?: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-2 py-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0"><Label className="text-sm font-medium">{label}</Label>{description && <p className="text-xs text-muted-foreground">{description}</p>}</div>
      <div className="shrink-0">{children}</div>
    </div>
  );
}
