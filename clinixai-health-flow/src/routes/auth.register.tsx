import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useState, type FormEvent } from "react";
import { Loader2, Mail, Phone, User } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Separator } from "@/components/ui/separator";
import { toast } from "sonner";
import { AuthLayout } from "@/components/auth/auth-layout";
import { PasswordInput, PasswordStrength, scorePassword } from "@/components/auth/password-input";
import { GoogleButton } from "@/components/auth/google-button";
import { useAuth } from "@/lib/auth-context";

export const Route = createFileRoute("/auth/register")({
  head: () => ({ meta: [{ title: "Create your CliniXAI account" }] }),
  component: RegisterPage,
});

function RegisterPage() {
  const navigate = useNavigate();
  const { register } = useAuth();
  const [firstName, setFirst] = useState("");
  const [lastName, setLast] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [agree, setAgree] = useState(false);
  const [loading, setLoading] = useState(false);

  const [error, setError] = useState<string | null>(null);

  const emailValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
  const pwStrong = scorePassword(password).score >= 3;
  const match = password && password === confirm;
  const canSubmit = firstName && lastName && emailValid && password && match && pwStrong && agree && !loading;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!canSubmit) return;
    setLoading(true);
    try {
      await register({ firstName, lastName, email, password });
      toast.success("Account created. Welcome to CliniXAI!");
      navigate({ to: "/app" });
    } catch (err: any) {
      setError(err?.message || "Failed to create account. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthLayout
      title="Create your account"
      subtitle="Join CliniXAI to bring AI-powered decisions into your workflow."
      footer={<>Already have an account? <Link to="/auth/login" className="font-medium text-primary hover:underline">Sign In</Link></>}
    >
      <form onSubmit={submit} className="space-y-4" noValidate>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="first">First name</Label>
            <div className="relative">
              <User className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input id="first" required value={firstName} onChange={(e) => setFirst(e.target.value)} placeholder="Priya" className="h-11 pl-9" />
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="last">Last name</Label>
            <Input id="last" required value={lastName} onChange={(e) => setLast(e.target.value)} placeholder="Sharma" className="h-11" />
          </div>
        </div>

        <div className="space-y-2">
          <Label htmlFor="email">Email address</Label>
          <div className="relative">
            <Mail className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input id="email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@hospital.com" className="h-11 pl-9" />
          </div>
          {email && !emailValid && <p className="text-xs text-error">Please enter a valid email.</p>}
        </div>

        <div className="space-y-2">
          <Label htmlFor="phone">Mobile number</Label>
          <div className="relative">
            <Phone className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input id="phone" type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="+91 98765 43210" className="h-11 pl-9" />
          </div>
        </div>

        <p className="rounded-lg border border-dashed border-border bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
          Public sign-ups create a Patient account. Doctor, Staff, and Admin accounts are provisioned by hospital administration.
        </p>


        <div className="space-y-2">
          <Label htmlFor="pw">Password</Label>
          <PasswordInput id="pw" required value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Create a strong password" className="h-11" />
          <PasswordStrength password={password} />
        </div>

        <div className="space-y-2">
          <Label htmlFor="pw2">Confirm password</Label>
          <PasswordInput id="pw2" required value={confirm} onChange={(e) => setConfirm(e.target.value)} placeholder="Re-enter password" className="h-11" />
          {confirm && !match && <p className="text-xs text-error">Passwords don't match.</p>}
        </div>

        <label className="flex items-start gap-2 text-sm text-muted-foreground">
          <Checkbox aria-label="Agree to Terms and Conditions and Privacy Policy" checked={agree} onCheckedChange={(v) => setAgree(!!v)} className="mt-0.5" />
          <span>I agree to the <a className="text-primary hover:underline" href="#">Terms & Conditions</a> and <a className="text-primary hover:underline" href="#">Privacy Policy</a>.</span>
        </label>

        {error && <p className="rounded-lg bg-error/10 px-3 py-2 text-sm text-error">{error}</p>}

        <Button type="submit" disabled={!canSubmit} className="h-11 w-full">
          {loading ? <><Loader2 className="h-4 w-4 animate-spin" /> Creating account...</> : "Create Account"}
        </Button>

        <div className="flex items-center gap-3">
          <Separator className="flex-1" />
          <span className="text-xs uppercase tracking-wider text-muted-foreground">or</span>
          <Separator className="flex-1" />
        </div>

        <GoogleButton label="Sign up with Google" />
      </form>
    </AuthLayout>
  );
}
