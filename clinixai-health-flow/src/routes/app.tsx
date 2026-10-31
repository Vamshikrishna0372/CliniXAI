import { createFileRoute, Outlet, useNavigate, useRouter } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { SidebarProvider, SidebarInset } from "@/components/ui/sidebar";
import { AppSidebar } from "@/components/app-shell/app-sidebar";
import { AppTopbar } from "@/components/app-shell/app-topbar";
import { CommandPalette, useCommandPalette } from "@/components/app-shell/command-palette";
import { FullPageLoader, ServerErrorPage } from "@/components/dashboard/states";
import { useAuth } from "@/lib/auth-context";
import { canAccessSection } from "@/lib/roles";
import { useRouterState } from "@tanstack/react-router";
import { ForbiddenPage } from "@/components/dashboard/states";

export const Route = createFileRoute("/app")({
  head: () => ({ meta: [{ title: "CliniXAI Workspace" }, { name: "robots", content: "noindex" }] }),
  component: AppShellLayout,
  errorComponent: AppShellRouteError,
});

function AppShellRouteError({ error, reset }: { error: Error; reset: () => void }) {
  const router = useRouter();
  useEffect(() => {
    console.error("[AppShell Error]", error);
  }, [error]);

  return (
    <div className="min-h-screen bg-background p-6">
      <ServerErrorPage
        embedded
        homeTo="/app"
        reset={() => {
          router.invalidate();
          reset();
        }}
      />
    </div>
  );
}

function AppShellLayout() {
  const { user, hydrated, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const cmd = useCommandPalette();
  const [redirecting, setRedirecting] = useState(false);
  const pathname = useRouterState({ select: (s) => s.location.pathname });

  useEffect(() => {
    if (hydrated && !isAuthenticated && !redirecting) {
      setRedirecting(true);
      navigate({ to: "/auth/login" });
    }
  }, [hydrated, isAuthenticated, navigate, redirecting]);

  if (!hydrated || !user) return <FullPageLoader />;

  const section = pathname.split("/").filter(Boolean).slice(1).join("/");
  const allowed = canAccessSection(user.role, section);

  return (
    <SidebarProvider>
      <div className="flex min-h-dvh w-full max-w-full bg-background">
        <AppSidebar role={user.role} />
        <SidebarInset className="flex min-w-0 flex-1 flex-col">
          <AppTopbar onOpenSearch={() => cmd.setOpen(true)} />
          <div className="min-w-0 flex-1 px-4 py-6 sm:px-6 lg:px-8">
            {allowed ? <Outlet /> : <ForbiddenPage embedded />}
          </div>
        </SidebarInset>
      </div>
      <CommandPalette open={cmd.open} onOpenChange={cmd.setOpen} />
    </SidebarProvider>
  );
}
