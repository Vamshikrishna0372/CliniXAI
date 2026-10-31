import { createFileRoute, Link, useSearch } from "@tanstack/react-router";
import { useState, type FormEvent } from "react";
import { CheckCircle2, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { AuthLayout } from "@/components/auth/auth-layout";
import { PasswordInput, PasswordStrength, scorePassword } from "@/components/auth/password-input";
import { useAuth } from "@/lib/auth-context";

export const Route = createFileRoute("/auth/reset-password")({
  head: () => ({ meta: [{ title: "Set a new password — CliniXAI" }] }),
  validateSearch: (search: Record<string, unknown>): { token?: string } => ({
    token: typeof search.token === "string" ? search.token : undefined,
  }),
  component: ResetPage,
});

function ResetPage() {
  const { token } = useSearch({ from: "/auth/reset-password" });
  const { resetPassword } = useAuth();
  const [pw, setPw] = useState("");
  const [pw2, setPw2] = useState("");
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const strong = scorePassword(pw).score >= 3;
  const match = pw && pw === pw2;
  const canSubmit = strong && match && !loading;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!canSubmit) return;
    if (!token) {
      setError("Invalid or missing reset token. Please use the link from your email.");
      return;
    }
    setLoading(true);
    try {
      await resetPassword(token, pw);
      setDone(true);
    } catch (err: any) {
      setError(err?.message || "Failed to reset password. The link may have expired.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthLayout
      title={done ? "Password updated" : "Reset password"}
      subtitle={done ? "Your password has been changed successfully." : "Choose a strong new password to secure your account."}
    >
      {done ? (
        <div className="rounded-2xl border border-success/20 bg-success/5 p-6 text-center">
          <div className="mx-auto mb-3 grid h-12 w-12 place-items-center rounded-full bg-success/10 text-success">
            <CheckCircle2 className="h-6 w-6" />
          </div>
          <p className="text-sm text-foreground">You can now sign in with your new password.</p>
          <Button asChild className="mt-4"><Link to="/auth/login">Return to Login</Link></Button>
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-4" noValidate>
          {!token && (
            <p className="rounded-lg bg-error/10 px-3 py-2 text-sm text-error">
              Invalid or missing reset token. Please use the link sent to your email.
            </p>
          )}
          <div className="space-y-2">
            <Label htmlFor="pw">New password</Label>
            <PasswordInput id="pw" required value={pw} onChange={(e) => setPw(e.target.value)} className="h-11" />
            <PasswordStrength password={pw} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="pw2">Confirm new password</Label>
            <PasswordInput id="pw2" required value={pw2} onChange={(e) => setPw2(e.target.value)} className="h-11" />
            {pw2 && !match && <p className="text-xs text-error">Passwords don't match.</p>}
          </div>
          {error && <p className="rounded-lg bg-error/10 px-3 py-2 text-sm text-error">{error}</p>}
          <Button type="submit" disabled={!canSubmit || !token} className="h-11 w-full">
            {loading ? <><Loader2 className="h-4 w-4 animate-spin" /> Updating...</> : "Reset Password"}
          </Button>
        </form>
      )}
    </AuthLayout>
  );
}
