import { createFileRoute, Link, useSearch } from "@tanstack/react-router";
import { useState, useEffect } from "react";
import { CheckCircle2, MailCheck, AlertTriangle, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { AuthLayout } from "@/components/auth/auth-layout";
import { toast } from "sonner";
import { useAuth } from "@/lib/auth-context";
import { apiClient } from "@/lib/api-client";

type VerifyState = "pending" | "success" | "failed";

export const Route = createFileRoute("/auth/verify-email")({
  head: () => ({ meta: [{ title: "Verify your email — CliniXAI" }] }),
  validateSearch: (search: Record<string, unknown>): { state?: VerifyState; token?: string } => ({
    state: (search.state as VerifyState) || "pending",
    token: typeof search.token === "string" ? search.token : undefined,
  }),
  component: VerifyEmailPage,
});

function VerifyEmailPage() {
  const { state = "pending", token } = useSearch({ from: "/auth/verify-email" });
  const { user } = useAuth();
  const [resending, setResending] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [verifyResult, setVerifyResult] = useState<VerifyState | null>(null);

  // Auto-confirm if a token is in the URL
  useEffect(() => {
    if (token && state === "pending") {
      setVerifying(true);
      apiClient.post("/auth/email-verification/confirm", { token }, { skipAuth: true })
        .then(() => setVerifyResult("success"))
        .catch(() => setVerifyResult("failed"))
        .finally(() => setVerifying(false));
    }
  }, [token, state]);

  const resend = async () => {
    const email = user?.email;
    if (!email) {
      toast.error("No email address found. Please log in first.");
      return;
    }
    setResending(true);
    try {
      await apiClient.post("/auth/email-verification/request", { email }, { skipAuth: true });
      toast.success("Verification email sent again.");
    } catch (err: any) {
      toast.error(err?.message || "Failed to resend. Please try again.");
    } finally {
      setResending(false);
    }
  };

  // Resolve effective display state: verifyResult from token auto-confirm takes priority
  const effectiveState = verifyResult ?? state;

  if (verifying) {
    return (
      <AuthLayout title="Verifying your email" subtitle="Please wait while we verify your email address.">
        <div className="flex flex-col items-center gap-4 py-6">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
          <p className="text-sm text-muted-foreground">Verifying…</p>
        </div>
      </AuthLayout>
    );
  }

  if (effectiveState === "success") {
    return (
      <AuthLayout title="Email verified" subtitle="Your email has been verified successfully.">
        <div className="rounded-2xl border border-success/20 bg-success/5 p-6 text-center">
          <div className="mx-auto mb-3 grid h-12 w-12 place-items-center rounded-full bg-success/10 text-success">
            <CheckCircle2 className="h-6 w-6" />
          </div>
          <p className="text-sm text-foreground">You're all set to explore CliniXAI.</p>
          <Button asChild className="mt-4"><Link to="/app">Continue to CliniXAI</Link></Button>
        </div>
      </AuthLayout>
    );
  }

  if (effectiveState === "failed") {
    return (
      <AuthLayout title="Verification failed" subtitle="This link may be invalid or expired.">
        <div className="rounded-2xl border border-error/20 bg-error/5 p-6 text-center">
          <div className="mx-auto mb-3 grid h-12 w-12 place-items-center rounded-full bg-error/10 text-error">
            <AlertTriangle className="h-6 w-6" />
          </div>
          <p className="text-sm text-foreground">We couldn't verify your email using this link.</p>
          <Button onClick={resend} disabled={resending} className="mt-4">
            {resending ? <><Loader2 className="h-4 w-4 animate-spin" /> Sending...</> : "Resend Verification Email"}
          </Button>
        </div>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout title="Verify your email" subtitle="We've sent a verification link to your inbox.">
      <div className="rounded-2xl border border-border bg-card p-6 text-center">
        <div className="mx-auto mb-3 grid h-12 w-12 place-items-center rounded-full bg-primary/10 text-primary">
          <MailCheck className="h-6 w-6" />
        </div>
        <p className="text-sm text-foreground">Click the link in the email to activate your account.</p>
        <p className="mt-1 text-xs text-muted-foreground">Didn't receive it? Check your spam folder.</p>
        <Button onClick={resend} variant="outline" disabled={resending} className="mt-4">
          {resending ? <><Loader2 className="h-4 w-4 animate-spin" /> Sending...</> : "Resend Verification Email"}
        </Button>
      </div>
    </AuthLayout>
  );
}
