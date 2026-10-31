import { Check } from "lucide-react";
import { cn } from "@/lib/utils";

export function Stepper({ steps, current, className }: { steps: string[]; current: number; className?: string }) {
  return (
    <ol className={cn("flex w-full items-center gap-2 overflow-x-auto pb-2", className)}>
      {steps.map((s, i) => {
        const done = i < current;
        const active = i === current;
        return (
          <li key={s} className="flex min-w-0 flex-1 items-center gap-2">
            <div className="flex min-w-0 items-center gap-2">
              <span
                className={cn(
                  "grid h-7 w-7 shrink-0 place-items-center rounded-full text-xs font-semibold",
                  done && "bg-success text-white",
                  active && "bg-primary text-primary-foreground",
                  !done && !active && "bg-muted text-muted-foreground",
                )}
              >
                {done ? <Check className="h-4 w-4" /> : i + 1}
              </span>
              <span className={cn("truncate text-xs sm:text-sm", active ? "font-semibold text-foreground" : "text-muted-foreground")}>{s}</span>
            </div>
            {i < steps.length - 1 && <span className="hidden h-px flex-1 bg-border sm:block" />}
          </li>
        );
      })}
    </ol>
  );
}

export function StatusProgress({ steps, current }: { steps: string[]; current: number }) {
  return (
    <ol className="grid gap-3 sm:grid-cols-6">
      {steps.map((s, i) => {
        const done = i <= current;
        return (
          <li key={s} className="flex items-center gap-2 sm:flex-col sm:items-start">
            <span className={cn("h-1.5 w-full rounded-full sm:w-full", done ? "bg-primary" : "bg-muted")} />
            <span className={cn("text-xs", done ? "font-semibold text-foreground" : "text-muted-foreground")}>{s}</span>
          </li>
        );
      })}
    </ol>
  );
}
