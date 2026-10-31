import { cn } from "@/lib/utils";

export type ClassProbability = { label: string; probability: number };

type Props = {
  probabilities?: ClassProbability[];
  /** Fallback single value when no distribution is available. */
  confidence?: number;
  topLabel?: string;
  className?: string;
};

export function confidenceBand(value: number): { label: string; tone: "success" | "warning" | "destructive" } {
  if (value >= 0.85) return { label: "High", tone: "success" };
  if (value >= 0.7) return { label: "Moderate", tone: "warning" };
  return { label: "Low", tone: "destructive" };
}

const toneClasses: Record<string, string> = {
  success: "text-success bg-success/10 border-success/30",
  warning: "text-warning bg-warning/10 border-warning/30",
  destructive: "text-destructive bg-destructive/10 border-destructive/30",
};

/** Reusable AI confidence visualization: sorted bars, top-class highlight, confidence band. */
export function ConfidenceBreakdown({ probabilities, confidence, topLabel, className }: Props) {
  const rows = probabilities && probabilities.length > 0
    ? [...probabilities].sort((a, b) => b.probability - a.probability)
    : [{ label: topLabel ?? "Prediction", probability: confidence ?? 0 }];

  const top = rows[0];
  const band = confidenceBand(top?.probability ?? 0);

  return (
    <div className={cn("space-y-2", className)}>
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs text-muted-foreground">Confidence distribution</p>
        <span className={cn("shrink-0 rounded-full border px-2 py-0.5 text-[11px] font-medium", toneClasses[band.tone])}>
          {band.label} confidence
        </span>
      </div>
      <div className="space-y-1.5">
        {rows.map((r) => {
          const isTop = r.label === top?.label;
          const pct = Math.round(r.probability * 100);
          return (
            <div key={r.label} className="min-w-0">
              <div className="flex items-center justify-between gap-2 text-xs">
                <span className={cn("truncate", isTop && "font-semibold text-foreground")}>{r.label}</span>
                <span className={cn("shrink-0 tabular-nums", isTop && "font-semibold")}>{pct}%</span>
              </div>
              <div className="mt-0.5 h-2 w-full overflow-hidden rounded-full bg-muted">
                <div
                  className={cn("h-full rounded-full", isTop ? "bg-primary" : "bg-primary/40")}
                  style={{ width: `${pct}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
      <p className="text-[11px] text-muted-foreground">High confidence does not equal medical certainty.</p>
    </div>
  );
}
