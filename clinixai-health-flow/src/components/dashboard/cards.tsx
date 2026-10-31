import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { TrendingUp, TrendingDown, ArrowRight } from "lucide-react";

/* ---------- Responsive grid ---------- */

type ColN = 1 | 2 | 3 | 4 | 5 | 6;
type Cols = { base?: ColN; sm?: ColN; md?: ColN; lg?: ColN; xl?: ColN };

const BASE: Record<ColN, string> = { 1: "grid-cols-1", 2: "grid-cols-2", 3: "grid-cols-3", 4: "grid-cols-4", 5: "grid-cols-5", 6: "grid-cols-6" };
const SM: Record<ColN, string> = { 1: "sm:grid-cols-1", 2: "sm:grid-cols-2", 3: "sm:grid-cols-3", 4: "sm:grid-cols-4", 5: "sm:grid-cols-5", 6: "sm:grid-cols-6" };
const MD: Record<ColN, string> = { 1: "md:grid-cols-1", 2: "md:grid-cols-2", 3: "md:grid-cols-3", 4: "md:grid-cols-4", 5: "md:grid-cols-5", 6: "md:grid-cols-6" };
const LG: Record<ColN, string> = { 1: "lg:grid-cols-1", 2: "lg:grid-cols-2", 3: "lg:grid-cols-3", 4: "lg:grid-cols-4", 5: "lg:grid-cols-5", 6: "lg:grid-cols-6" };
const XL: Record<ColN, string> = { 1: "xl:grid-cols-1", 2: "xl:grid-cols-2", 3: "xl:grid-cols-3", 4: "xl:grid-cols-4", 5: "xl:grid-cols-5", 6: "xl:grid-cols-6" };

export function ResponsiveGrid({
  cols = { base: 1, sm: 2, lg: 3 },
  autoFit,
  minItem = "16rem",
  gap = "gap-4",
  className,
  children,
}: {
  cols?: Cols;
  autoFit?: boolean;
  minItem?: string;
  gap?: string;
  className?: string;
  children: ReactNode;
}) {
  if (autoFit) {
    return (
      <div
        className={cn("grid", gap, className)}
        style={{ gridTemplateColumns: `repeat(auto-fit, minmax(${minItem}, 1fr))` }}
      >
        {children}
      </div>
    );
  }
  const cls = cn(
    cols.base && BASE[cols.base],
    cols.sm && SM[cols.sm],
    cols.md && MD[cols.md],
    cols.lg && LG[cols.lg],
    cols.xl && XL[cols.xl],
  );
  return <div className={cn("grid", cls, gap, className)}>{children}</div>;
}

/* ---------- KPI / Stat cards ---------- */

export function KpiCard({
  label,
  value,
  delta,
  trend,
  icon: Icon,
  loading,
}: {
  label: string;
  value: string | number;
  delta?: string;
  trend?: "up" | "down" | "flat";
  icon?: React.ComponentType<{ className?: string }>;
  loading?: boolean;
}) {
  if (loading) {
    return (
      <Card><CardContent className="p-5 space-y-3">
        <Skeleton className="h-4 w-24" /><Skeleton className="h-8 w-32" /><Skeleton className="h-4 w-16" />
      </CardContent></Card>
    );
  }
  const TrendIcon = trend === "down" ? TrendingDown : TrendingUp;
  const trendCls = trend === "down" ? "text-error" : trend === "up" ? "text-success" : "text-muted-foreground";
  return (
    <Card className="card-hover">
      <CardContent className="p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-sm text-muted-foreground">{label}</p>
            <p className="mt-1 font-display text-2xl font-bold tracking-tight text-foreground">{value}</p>
            {delta && (
              <p className={cn("mt-1 flex items-center gap-1 text-xs font-medium", trendCls)}>
                <TrendIcon className="h-3.5 w-3.5" /> {delta}
              </p>
            )}
          </div>
          {Icon && (
            <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-primary/10 text-primary">
              <Icon className="h-5 w-5" />
            </span>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

/* ---------- Generic cards ---------- */

export function InfoCard({
  title, description, icon: Icon, children, action, className,
}: {
  title?: string;
  description?: string;
  icon?: React.ComponentType<{ className?: string }>;
  children?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <Card className={cn("card-hover", className)}>
      {(title || description) && (
        <CardHeader className="flex flex-row items-start gap-3">
          {Icon && (
            <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-primary/10 text-primary">
              <Icon className="h-4 w-4" />
            </span>
          )}
          <div className="min-w-0 flex-1">
            {title && <CardTitle className="text-base">{title}</CardTitle>}
            {description && <CardDescription>{description}</CardDescription>}
          </div>
          {action}
        </CardHeader>
      )}
      {children && <CardContent>{children}</CardContent>}
    </Card>
  );
}

export function QuickActionCard({
  label, description, icon: Icon, onClick,
}: {
  label: string;
  description?: string;
  icon: React.ComponentType<{ className?: string }>;
  onClick?: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="group flex w-full items-center gap-3 rounded-2xl border border-border bg-card p-4 text-left card-hover"
    >
      <span className="grid h-11 w-11 shrink-0 place-items-center rounded-xl gradient-primary text-primary-foreground shadow-[var(--shadow-glow)]">
        <Icon className="h-5 w-5" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-semibold text-foreground">{label}</span>
        {description && <span className="block truncate text-xs text-muted-foreground">{description}</span>}
      </span>
      <ArrowRight className="h-4 w-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
    </button>
  );
}

export function ChartContainer({
  title, description, children, action, loading,
}: {
  title: string;
  description?: string;
  children?: ReactNode;
  action?: ReactNode;
  loading?: boolean;
}) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between gap-3">
        <div className="min-w-0">
          <CardTitle className="text-base">{title}</CardTitle>
          {description && <CardDescription>{description}</CardDescription>}
        </div>
        {action}
      </CardHeader>
      <CardContent>
        {loading ? <Skeleton className="h-48 w-full" /> : (children ?? <div className="h-48 rounded-lg border border-dashed border-border grid place-items-center text-sm text-muted-foreground">Chart placeholder</div>)}
      </CardContent>
    </Card>
  );
}

export function ListCard({ title, items, empty, action }: { title: string; items: { id: string; primary: string; secondary?: string; meta?: string }[]; empty?: string; action?: ReactNode }) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="text-base">{title}</CardTitle>
        {action}
      </CardHeader>
      <CardContent className="p-0">
        {items.length === 0 ? (
          <p className="px-6 pb-6 text-sm text-muted-foreground">{empty ?? "Nothing to show."}</p>
        ) : (
          <ul className="divide-y divide-border">
            {items.map((it) => (
              <li key={it.id} className="flex items-center justify-between gap-3 px-6 py-3">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-foreground">{it.primary}</p>
                  {it.secondary && <p className="truncate text-xs text-muted-foreground">{it.secondary}</p>}
                </div>
                {it.meta && <span className="shrink-0 text-xs text-muted-foreground">{it.meta}</span>}
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

export function TableContainer({ title, description, action, children }: { title: string; description?: string; action?: ReactNode; children: ReactNode }) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between gap-3">
        <div className="min-w-0">
          <CardTitle className="text-base">{title}</CardTitle>
          {description && <CardDescription>{description}</CardDescription>}
        </div>
        {action}
      </CardHeader>
      <CardContent className="p-0 sm:p-0">{children}</CardContent>
    </Card>
  );
}

export { Button };
