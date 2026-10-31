import { Activity } from "lucide-react";
import { cn } from "@/lib/utils";

export function BrandMark({ className, size = "md", labelClassName }: { className?: string; size?: "sm" | "md" | "lg"; labelClassName?: string }) {
  const dim = { sm: "h-8 w-8", md: "h-10 w-10", lg: "h-12 w-12" }[size];
  const text = { sm: "text-base", md: "text-lg", lg: "text-xl" }[size];
  return (
    <div className={cn("flex items-center gap-2.5", className)}>
      <div className={cn("grid place-items-center rounded-xl gradient-primary shadow-[var(--shadow-glow)]", dim)}>
        <Activity className="h-5 w-5 text-primary-foreground" strokeWidth={2.5} />
      </div>
      <span className={cn("font-display font-bold tracking-tight text-foreground", text, labelClassName)}>
        Clini<span className="text-gradient">XAI</span>
      </span>
    </div>
  );
}
