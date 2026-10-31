import { useMemo, useState } from "react";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { CheckCheck, Inbox, MailOpen, Mail, Trash2 } from "lucide-react";
import { PageHeader } from "@/components/app-shell/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { NOTIF_ICON } from "@/lib/notifications-mock";
import { useClinix } from "@/lib/store/clinix-store";
import { useAuth } from "@/lib/auth-context";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/app/notifications")({
  head: () => ({ meta: [{ title: "Notifications — CliniXAI" }, { name: "robots", content: "noindex" }] }),
  component: NotificationsPage,
});

const TABS = ["all", "unread", "appointment", "ai-report", "prescription", "follow-up", "billing", "system"] as const;

function NotificationsPage() {
  const { notifications, markNotificationRead, markAllNotificationsRead, clearNotifications, unreadCount } = useClinix();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [tab, setTab] = useState<(typeof TABS)[number]>("all");

  const filtered = useMemo(
    () =>
      notifications.filter((i) => {
        if (tab === "all") return true;
        if (tab === "unread") return !i.read;
        return i.category === tab;
      }),
    [notifications, tab],
  );

  return (
    <div className="space-y-6">
      <PageHeader
        title="Notifications"
        description="All updates about your care, appointments, and billing."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" size="sm" onClick={markAllNotificationsRead} disabled={unreadCount === 0} className="min-h-10">
              <CheckCheck className="mr-1 h-4 w-4" /> Mark all read
            </Button>
            <Button variant="outline" size="sm" onClick={clearNotifications} disabled={notifications.length === 0} className="min-h-10">
              <Trash2 className="mr-1 h-4 w-4" /> Clear all
            </Button>
          </div>
        }
      />
      <Tabs value={tab} onValueChange={(v) => setTab(v as typeof tab)}>
        <TabsList className="w-full overflow-x-auto">
          <div className="flex">
            {TABS.map((t) => (
              <TabsTrigger key={t} value={t} className="min-h-10 capitalize">
                {t === "unread" ? `Unread${unreadCount ? ` (${unreadCount})` : ""}` : t.replace("-", " ")}
              </TabsTrigger>
            ))}
          </div>
        </TabsList>
      </Tabs>

      {filtered.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-2 p-10 text-center">
            <Inbox className="h-8 w-8 text-muted-foreground" />
            <p className="text-sm font-medium">You're all caught up</p>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="p-0">
            <ul className="divide-y divide-border">
              {filtered.map((n) => {
                const Icon = NOTIF_ICON[n.category];
                const handleClick = () => {
                  markNotificationRead(n.id, true);
                  if (n.category === "appointment" || n.referenceType === "appointment") {
                    if (n.referenceId) navigate({ to: "/app/appointments/$id", params: { id: n.referenceId } });
                    else navigate({ to: "/app/appointments" });
                  } else if (n.category === "billing" || n.referenceType === "billing") {
                    const isPatient = user?.role === "patient";
                    if (isPatient) {
                      navigate({ to: "/app/bills" });
                    } else {
                      if (n.referenceId) navigate({ to: "/app/billing/$id", params: { id: n.referenceId } });
                      else navigate({ to: "/app/billing" });
                    }
                  } else if (n.category === "prescription") {
                    navigate({ to: "/app/prescriptions" });
                  } else if (n.category === "follow-up" || n.referenceType === "follow_up") {
                    navigate({ to: "/app/follow-ups" });
                  } else if (n.category === "ai-report" || n.referenceType === "ai_analysis") {
                    const isPatient = user?.role === "patient";
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
                  <li key={n.id} className={cn("flex items-start gap-3 p-4", !n.read && "bg-primary-soft/40")}>
                    <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-primary/10 text-primary cursor-pointer" onClick={handleClick}>
                      <Icon className="h-4 w-4" />
                    </span>
                    <div className="min-w-0 flex-1 cursor-pointer" onClick={handleClick}>
                      <div className="flex items-center justify-between gap-2">
                        <p className="truncate text-sm font-medium">{n.title}</p>
                        <span className="shrink-0 text-[11px] text-muted-foreground">{n.time}</span>
                      </div>
                      <p className="mt-0.5 text-xs text-muted-foreground">{n.body}</p>
                    </div>
                    <div className="flex shrink-0 items-center gap-1">
                      {!n.read && <span className="mr-1 h-2 w-2 rounded-full bg-primary" aria-label="Unread" />}
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-10 w-10"
                        aria-label={n.read ? "Mark as unread" : "Mark as read"}
                        onClick={() => markNotificationRead(n.id, !n.read)}
                      >
                        {n.read ? <Mail className="h-4 w-4" /> : <MailOpen className="h-4 w-4" />}
                      </Button>
                    </div>
                  </li>
                );
              })}
            </ul>
          </CardContent>
        </Card>
      )}

      <p className="text-center text-xs text-muted-foreground">
        Signed in as {user ? `${user.firstName} ${user.lastName}` : "guest"} ·{" "}
        <Link to="/app" className="underline underline-offset-2">
          Back to dashboard
        </Link>
      </p>
    </div>
  );
}
