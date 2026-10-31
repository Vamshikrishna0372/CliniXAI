import { useNavigate } from "@tanstack/react-router";
import { Bell, CheckCheck, Inbox, Mail, MailOpen } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { NOTIF_ICON } from "@/lib/notifications-mock";
import { useClinix } from "@/lib/store/clinix-store";
import { useAuth } from "@/lib/auth-context";
import { cn } from "@/lib/utils";

export function NotificationsButton() {
  const { notifications, unreadCount, markNotificationRead, markAllNotificationsRead } = useClinix();
  const { user } = useAuth();
  const navigate = useNavigate();
  const recent = notifications.slice(0, 8);

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="ghost" size="icon" aria-label={`Notifications${unreadCount ? ` (${unreadCount} unread)` : ""}`} className="relative h-10 w-10">
          <Bell className="h-5 w-5" />
          {unreadCount > 0 && (
            <span className="absolute right-1.5 top-1.5 grid h-4 min-w-4 place-items-center rounded-full bg-error px-1 text-[10px] font-bold text-background">
              {unreadCount > 9 ? "9+" : unreadCount}
            </span>
          )}
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-[min(92vw,22rem)] p-0">
        <div className="flex items-center justify-between px-4 py-3">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold">Notifications</h3>
            {unreadCount > 0 && <Badge variant="secondary" className="text-[10px]">{unreadCount} new</Badge>}
          </div>
          <Button variant="ghost" size="sm" onClick={markAllNotificationsRead} disabled={unreadCount === 0} className="h-9 gap-1 text-xs">
            <CheckCheck className="h-3.5 w-3.5" /> Mark all read
          </Button>
        </div>
        <Separator />
        {recent.length === 0 ? (
          <div className="flex flex-col items-center gap-2 px-6 py-10 text-center">
            <Inbox className="h-8 w-8 text-muted-foreground" />
            <p className="text-sm font-medium">You're all caught up</p>
            <p className="text-xs text-muted-foreground">New notifications will appear here.</p>
          </div>
        ) : (
          <ScrollArea className="max-h-[60vh]">
            <ul className="divide-y divide-border">
              {recent.map((n) => {
                const Icon = NOTIF_ICON[n.category];
                const handleClick = () => {
                  markNotificationRead(n.id, true);
                  if (n.category === "appointment" || n.referenceType === "appointment") {
                    if (n.referenceId) navigate({ to: "/app/appointments/$id", params: { id: n.referenceId } });
                    else navigate({ to: "/app/appointments" });
                  } else if (n.category === "billing" || n.referenceType === "billing") {
                    const isPatient = (user?.rawRole || user?.role || "").toLowerCase() === "patient";
                    if (isPatient) {
                      if (n.referenceId) navigate({ to: "/app/bills/$id", params: { id: n.referenceId } });
                      else navigate({ to: "/app/bills" });
                    } else {
                      if (n.referenceId) navigate({ to: "/app/billing/$id", params: { id: n.referenceId } });
                      else navigate({ to: "/app/billing" });
                    }
                  } else if (n.category === "prescription") {
                    navigate({ to: "/app/prescriptions" });
                  } else if (n.category === "follow-up" || n.referenceType === "follow_up") {
                    navigate({ to: "/app/follow-ups" });
                  } else if (n.category === "ai-report" || n.referenceType === "ai_analysis") {
                    const isPatient = (user?.rawRole || user?.role || "").toLowerCase() === "patient";
                    if (isPatient) {
                      if (n.referenceId) navigate({ to: "/app/ai-reports/$id", params: { id: n.referenceId } });
                      else navigate({ to: "/app/ai-reports" });
                    } else {
                      if (n.referenceId) navigate({ to: "/app/ai-analysis/$id", params: { id: n.referenceId } });
                      else navigate({ to: "/app/ai-analysis" });
                    }
                  }
                };

                return (
                  <li key={n.id} className="flex items-start gap-2 px-2 py-1">
                    <button
                      type="button"
                      onClick={handleClick}
                      className={cn(
                        "flex min-h-10 flex-1 items-start gap-3 rounded-md px-2 py-2 text-left transition-colors hover:bg-muted/60",
                        !n.read && "bg-primary-soft/40",
                      )}
                    >
                      <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-primary/10 text-primary">
                        <Icon className="h-4 w-4" />
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="flex items-center justify-between gap-2">
                          <span className="truncate text-sm font-medium text-foreground">{n.title}</span>
                          <span className="shrink-0 text-[11px] text-muted-foreground">{n.time}</span>
                        </span>
                        <span className="mt-0.5 line-clamp-2 block text-xs text-muted-foreground">{n.body}</span>
                      </span>
                      {!n.read && <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-primary" aria-label="Unread" />}
                    </button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-10 w-10 shrink-0"
                      aria-label={n.read ? "Mark as unread" : "Mark as read"}
                      onClick={() => markNotificationRead(n.id, !n.read)}
                    >
                      {n.read ? <Mail className="h-4 w-4" /> : <MailOpen className="h-4 w-4" />}
                    </Button>
                  </li>
                );
              })}
            </ul>
          </ScrollArea>
        )}
        <Separator />
        <div className="p-2">
          <Button variant="ghost" className="min-h-10 w-full text-xs" onClick={() => navigate({ to: "/app/notifications" })}>
            View all notifications
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  );
}
