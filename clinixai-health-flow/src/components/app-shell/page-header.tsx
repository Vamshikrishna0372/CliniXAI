import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";

export function PageHeader({
  title,
  description,
  status,
  primary,
  secondary,
  actions,
  className,
}: {
  title: string;
  description?: string;
  status?: { label: string; tone?: "default" | "success" | "warning" | "error" | "info" };
  primary?: ReactNode;
  secondary?: ReactNode;
  actions?: ReactNode;
  className?: string;
}) {
  const toneCls: Record<string, string> = {
    default: "",
    success: "bg-success/10 text-success border-success/20",
    warning: "bg-warning/10 text-warning border-warning/20",
    error: "bg-error/10 text-error border-error/20",
    info: "bg-info/10 text-info border-info/20",
  };
  const right = actions ?? (primary || secondary ? <>{secondary}{primary}</> : null);
  return (
    <header
      className={cn(
        "grid grid-cols-[minmax(0,1fr)_auto] items-start gap-4 border-b border-border pb-4 sm:flex sm:flex-wrap sm:items-center sm:justify-between",
        className,
      )}
    >
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <h1 className="truncate font-display text-xl font-bold text-foreground sm:text-2xl">{title}</h1>
          {status && status.label && (
            <Badge variant="outline" className={cn("shrink-0", toneCls[status.tone ?? "default"])}>
              {status.label}
            </Badge>
          )}
        </div>
        {description && <p className="mt-1 text-sm text-muted-foreground">{description}</p>}
      </div>
      {right && (
        <div className="col-span-2 flex flex-wrap items-center gap-2 sm:col-span-1">
          {right}
        </div>
      )}
    </header>
  );
}
