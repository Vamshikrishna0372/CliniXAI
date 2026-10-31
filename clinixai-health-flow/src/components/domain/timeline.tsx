import type { LucideIcon } from "lucide-react";
import { Activity, Brain, Calendar, FileText, Image as ImgIcon, Pill, ReceiptText, UserPlus, CalendarClock, Stethoscope } from "lucide-react";
import { cn } from "@/lib/utils";
import { fmtDate, type TimelineEvent } from "@/lib/mock/domain";

const ICON: Record<TimelineEvent["kind"], LucideIcon> = {
  registration: UserPlus,
  appointment: Calendar,
  consultation: Stethoscope,
  report: FileText,
  image: ImgIcon,
  ai: Brain,
  prescription: Pill,
  billing: ReceiptText,
  "follow-up": CalendarClock,
};

export function Timeline({ events, className }: { events: TimelineEvent[]; className?: string }) {
  if (events.length === 0) {
    return (
      <div className={cn("flex items-center gap-3 rounded-xl border border-dashed border-border p-6 text-sm text-muted-foreground", className)}>
        <Activity className="h-4 w-4" /> No events yet — activity will appear here as it happens.
      </div>
    );
  }
  return (
    <ol className={cn("relative space-y-4 border-l border-border pl-5", className)}>
      {events.map((e) => {
        const Icon = ICON[e.kind];
        return (
          <li key={e.id} className="relative">
            <span className="absolute -left-[30px] top-0 grid h-8 w-8 place-items-center rounded-full bg-primary/10 text-primary ring-4 ring-background">
              <Icon className="h-4 w-4" />
            </span>
            <div className="rounded-xl border border-border bg-card p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-sm font-semibold text-foreground">{e.title}</p>
                <span className="text-xs text-muted-foreground">{fmtDate(e.date)}</span>
              </div>
              {e.description && <p className="mt-1 text-xs text-muted-foreground">{e.description}</p>}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
