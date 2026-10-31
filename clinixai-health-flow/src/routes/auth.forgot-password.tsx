import { createFileRoute, Link } from "@tanstack/react-router";
import { useState, type FormEvent } from "react";
import { ArrowLeft, CheckCircle2, Loader2, Mail } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AuthLayout } from "@/components/auth/auth-layout";
import { useAuth } from "@/lib/auth-context";

export const Route = createFileRoute("/auth/forgot-password")({
  head: () => ({ meta: [{ title: "Reset your CliniXAI password" }] }),
  component: ForgotPage,
});

function ForgotPage() {
  const { forgotPassword } = useAuth();
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const valid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!valid) return;
    setLoading(true);
    try {
      await forgotPassword(email);
      setSent(true);
    } catch (err: any) {
      // Backend returns success even for non-existent emails (security best practice),
      // so any real error here is likely network / server issue.
      setError(err?.message || "Unable to reach the server. Please try again.");
    } finally {
      setLoading(false);
    }
  };


  return (
    <AuthLayout
      title={sent ? "Check your inbox" : "Forgot password"}
      subtitle={sent ? "We've sent reset instructions if an account exists for that email." : "Enter your email and we'll send you a reset link."}
      footer={<Link to="/auth/login" className="inline-flex items-center gap-1.5 text-primary hover:underline"><ArrowLeft className="h-3.5 w-3.5" /> Back to sign in</Link>}
    >
      {sent ? (
        <div className="rounded-2xl border border-success/20 bg-success/5 p-6 text-center">
          <div className="mx-auto mb-3 grid h-12 w-12 place-items-center rounded-full bg-success/10 text-success">
            <CheckCircle2 className="h-6 w-6" />
          </div>
          <p className="text-sm text-foreground">Sent instructions to <span className="font-medium">{email}</span>.</p>
          <p className="mt-2 text-xs text-muted-foreground">Didn't get it? Check spam or <button type="button" onClick={() => setSent(false)} className="text-primary hover:underline">try again</button>.</p>
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-4" noValidate>
          <div className="space-y-2">
            <Label htmlFor="email">Email address</Label>
            <div className="relative">
              <Mail className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input id="email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@hospital.com" className="h-11 pl-9" />
            </div>
            {email && !valid && <p className="text-xs text-error">Please enter a valid email.</p>}
          </div>
          {error && <p className="rounded-lg bg-error/10 px-3 py-2 text-sm text-error">{error}</p>}
          <Button type="submit" disabled={!valid || loading} className="h-11 w-full">
            {loading ? <><Loader2 className="h-4 w-4 animate-spin" /> Sending...</> : "Send Reset Link"}
          </Button>
        </form>
      )}
    </AuthLayout>
  );
}
