import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useState, useEffect, type FormEvent } from "react";
import { Loader2, Mail } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Separator } from "@/components/ui/separator";
import { toast } from "sonner";
import { AuthLayout } from "@/components/auth/auth-layout";
import { PasswordInput } from "@/components/auth/password-input";
import { GoogleButton } from "@/components/auth/google-button";
import { useAuth } from "@/lib/auth-context";

export const Route = createFileRoute("/auth/login")({
  head: () => ({ meta: [{ title: "Sign in — CliniXAI" }, { name: "description", content: "Sign in to your CliniXAI account." }] }),
  component: LoginPage,
});

function LoginPage() {
  const navigate = useNavigate();
  const { signIn, isAuthenticated, user } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isAuthenticated || user) {
      navigate({ to: "/app" });
    }
  }, [isAuthenticated, user, navigate]);

  useEffect(() => {
    if (typeof window !== "undefined") {
      const params = new URLSearchParams(window.location.search);
      const urlErr = params.get("error");
      if (urlErr) {
        setError(decodeURIComponent(urlErr.replace(/\+/g, " ")));
      }
      if (params.get("google_success") === "true") {
        toast.success("Google Sign-In successful!");
        navigate({ to: "/app" });
      }
    }
  }, [navigate]);

  const emailValid = !email || /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());
  const canSubmit = email.trim().length > 0 && emailValid && password.length >= 6 && !loading;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!canSubmit) return;
    setLoading(true);
    try {
      await signIn(email.trim().toLowerCase(), password);
      toast.success("Welcome back!");
      navigate({ to: "/app" });
    } catch (err: any) {
      setError(err?.message || "Incorrect email or password.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthLayout
      title="Welcome back"
      subtitle="Sign in to continue to your CliniXAI workspace."
      footer={<>Don't have an account? <Link to="/auth/register" className="font-medium text-primary hover:underline">Create Account</Link></>}
    >
      <form onSubmit={submit} className="space-y-4" noValidate>

        <div className="space-y-2">
          <Label htmlFor="email">Email address</Label>
          <div className="relative">
            <Mail className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input id="email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="name@example.com" className="h-11 pl-9" />
          </div>
          {email && !emailValid && <p className="text-xs text-error">Please enter a valid email address.</p>}
        </div>

        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <Label htmlFor="password">Password</Label>
            <Link to="/auth/forgot-password" className="text-xs font-medium text-primary hover:underline">Forgot password?</Link>
          </div>
          <PasswordInput id="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" className="h-11" />
        </div>

        <div className="flex items-center gap-2">
          <Checkbox id="remember" aria-label="Remember me for 30 days" checked={remember} onCheckedChange={(v) => setRemember(!!v)} />
          <Label htmlFor="remember" className="text-sm font-normal">Remember me for 30 days</Label>
        </div>

        {error && <p className="rounded-lg bg-error/10 px-3 py-2 text-sm text-error">{error}</p>}

        <Button type="submit" disabled={!canSubmit} className="h-11 w-full">
          {loading ? <><Loader2 className="h-4 w-4 animate-spin" /> Signing in...</> : "Sign In"}
        </Button>

        <div className="flex items-center gap-3">
          <Separator className="flex-1" />
          <span className="text-xs uppercase tracking-wider text-muted-foreground">or</span>
          <Separator className="flex-1" />
        </div>

        <GoogleButton />
      </form>
    </AuthLayout>
  );
}
