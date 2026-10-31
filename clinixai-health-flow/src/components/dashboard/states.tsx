import type { ReactNode } from "react";
import { Link, useNavigate } from "@tanstack/react-router";
import { motion } from "framer-motion";
import {
  AlertTriangle, Inbox, LifeBuoy, Lock, RotateCcw, ShieldOff, WifiOff, Ban,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { BrandMark } from "@/components/brand-mark";
import { cn } from "@/lib/utils";
import { getStoredTokens } from "@/lib/api-client";

/* ---------- States ---------- */

export function EmptyState({
  icon: Icon = Inbox,
  title,
  description,
  action,
  className,
}: {
  icon?: React.ComponentType<{ className?: string }>;
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col items-center justify-center rounded-2xl border border-dashed border-border bg-card px-6 py-12 text-center", className)}>
      <span className="grid h-14 w-14 place-items-center rounded-2xl bg-primary/10 text-primary">
        <Icon className="h-6 w-6" />
      </span>
      <h3 className="mt-4 font-display text-lg font-semibold text-foreground">{title}</h3>
      {description && <p className="mt-1 max-w-sm text-sm text-muted-foreground">{description}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

export function ErrorState({
  title = "Something went wrong",
  description = "We couldn't complete that request. Please try again.",
  onRetry,
  className,
}: {
  title?: string;
  description?: string;
  onRetry?: () => void;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col items-center justify-center rounded-2xl border border-error/20 bg-error/5 px-6 py-12 text-center", className)}>
      <span className="grid h-14 w-14 place-items-center rounded-2xl bg-error/10 text-error">
        <AlertTriangle className="h-6 w-6" />
      </span>
      <h3 className="mt-4 font-display text-lg font-semibold text-foreground">{title}</h3>
      <p className="mt-1 max-w-sm text-sm text-muted-foreground">{description}</p>
      {onRetry && (
        <Button variant="outline" onClick={onRetry} className="mt-5 gap-2">
          <RotateCcw className="h-4 w-4" /> Try again
        </Button>
      )}
    </div>
  );
}

export function SessionExpired() {
  return (
    <FullPageStatus
      icon={Lock}
      title="Your session has expired"
      description="For your security, please sign in again to continue."
      action={<Button asChild><Link to="/auth/login">Sign In</Link></Button>}
    />
  );
}

/* ---------- Skeletons ---------- */

export function SkeletonCard() {
  return (
    <Card><CardContent className="space-y-3 p-5">
      <Skeleton className="h-4 w-2/3" />
      <Skeleton className="h-8 w-1/2" />
      <Skeleton className="h-3 w-1/3" />
    </CardContent></Card>
  );
}

export function SkeletonList({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex items-center gap-3 rounded-lg border border-border bg-card p-3">
          <Skeleton className="h-10 w-10 rounded-full" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-3 w-1/3" />
            <Skeleton className="h-3 w-1/2" />
          </div>
        </div>
      ))}
    </div>
  );
}

export function SkeletonTable({ rows = 6 }: { rows?: number }) {
  return (
    <div className="space-y-2 p-4">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="grid grid-cols-4 gap-3">
          <Skeleton className="h-8 col-span-2" />
          <Skeleton className="h-8" />
          <Skeleton className="h-8" />
        </div>
      ))}
    </div>
  );
}

export function SkeletonForm() {
  return (
    <div className="space-y-4">
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} className="space-y-2">
          <Skeleton className="h-3 w-24" />
          <Skeleton className="h-10 w-full" />
        </div>
      ))}
      <Skeleton className="h-10 w-32" />
    </div>
  );
}

export function SkeletonDashboard() {
  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => <SkeletonCard key={i} />)}
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card><CardContent className="p-5"><Skeleton className="h-48 w-full" /></CardContent></Card>
        <Card><CardContent className="p-5"><Skeleton className="h-48 w-full" /></CardContent></Card>
      </div>
    </div>
  );
}

export function SkeletonChart() {
  return <Skeleton className="h-64 w-full rounded-xl" />;
}

/* ---------- Full page ---------- */

export function FullPageLoader({ message = "Loading CliniXAI..." }: { message?: string }) {
  return (
    <main className="grid min-h-dvh place-items-center bg-background">
      <div className="flex flex-col items-center gap-4">
        <motion.div
          animate={{ scale: [1, 1.08, 1], opacity: [0.8, 1, 0.8] }}
          transition={{ duration: 1.6, repeat: Infinity, ease: "easeInOut" }}
        >
          <BrandMark size="lg" />
        </motion.div>
        <div className="h-1 w-40 overflow-hidden rounded-full bg-muted">
          <motion.div
            className="h-full w-1/3 gradient-primary"
            animate={{ x: ["-100%", "300%"] }}
            transition={{ duration: 1.2, repeat: Infinity, ease: "easeInOut" }}
          />
        </div>
        <p className="text-sm text-muted-foreground">{message}</p>
      </div>
    </main>
  );
}

export function FullPageStatus({
  icon: Icon, title, description, action, embedded = false,
}: {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  description?: string;
  action?: ReactNode;
  /** Render inside an existing <main> landmark (e.g. the app shell). */
  embedded?: boolean;
}) {
  const Tag = embedded ? "div" : "main";
  return (
    <Tag className={cn("grid place-items-center gradient-hero px-4", embedded ? "min-h-[60vh] rounded-2xl" : "min-h-dvh")}>
      <div className="w-full max-w-md rounded-3xl border border-border bg-card p-8 text-center shadow-[var(--shadow-elev-2)]">
        <div className="mx-auto mb-4 grid h-16 w-16 place-items-center rounded-2xl bg-primary/10 text-primary">
          <Icon className="h-7 w-7" />
        </div>
        <h1 className="font-display text-2xl font-bold text-foreground">{title}</h1>
        {description && <p className="mt-2 text-sm text-muted-foreground">{description}</p>}
        {action && <div className="mt-6 flex flex-wrap justify-center gap-2">{action}</div>}
      </div>
    </Tag>
  );
}

/* ---------- Preset error pages ---------- */

export function NotFoundPage() {
  const nav = useNavigate();
  return (
    <FullPageStatus
      icon={Ban}
      title="Page not found"
      description="The page you're looking for doesn't exist or has been moved."
      action={<>
        <Button variant="outline" onClick={() => nav({ to: "/" })}>Go home</Button>
        <Button onClick={() => nav({ to: "/app" })}>Go to Dashboard</Button>
      </>}
    />
  );
}

export function UnauthorizedPage() {
  return (
    <FullPageStatus
      icon={Lock}
      title="Authentication required"
      description="Please sign in to access this page."
      action={<Button asChild><Link to="/auth/login">Sign In</Link></Button>}
    />
  );
}

export function ForbiddenPage({ embedded = false }: { embedded?: boolean }) {
  return (
    <FullPageStatus
      embedded={embedded}
      icon={ShieldOff}
      title="Access denied"
      description="You don't have permission to view this resource. Contact your administrator if you believe this is a mistake."
      action={<Button asChild variant="outline"><Link to="/app">Go to Dashboard</Link></Button>}
    />
  );
}

export function ServerErrorPage({
  reset,
  embedded = false,
  homeTo,
}: {
  reset?: () => void;
  embedded?: boolean;
  homeTo?: string;
}) {
  const target = homeTo || (getStoredTokens()?.accessToken ? "/app" : "/");
  return (
    <FullPageStatus
      embedded={embedded}
      icon={AlertTriangle}
      title="Something went wrong"
      description="An unexpected error occurred on our end. You can try again or head back to Dashboard."
      action={<>
        <Button asChild variant="outline">
          <Link to={target}>{target.startsWith("/app") ? "Go to Dashboard" : "Go home"}</Link>
        </Button>
        <Button onClick={() => (reset ? reset() : window.location.reload())}>Try again</Button>
      </>}
    />
  );
}

export function OfflinePage() {
  return (
    <FullPageStatus
      icon={WifiOff}
      title="You're offline"
      description="Check your internet connection and try again."
      action={<Button onClick={() => window.location.reload()}>Retry</Button>}
    />
  );
}

export function SupportHint() {
  return (
    <p className="mt-6 inline-flex items-center gap-1.5 text-xs text-muted-foreground">
      <LifeBuoy className="h-3.5 w-3.5" /> Need help? Contact CliniXAI support.
    </p>
  );
}
