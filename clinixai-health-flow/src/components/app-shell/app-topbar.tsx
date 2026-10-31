import { SidebarTrigger } from "@/components/ui/sidebar";
import { Separator } from "@/components/ui/separator";
import { Breadcrumbs } from "./breadcrumbs";
import { UserMenu } from "./user-menu";
import { NotificationsButton } from "./notifications-panel";
import { ThemeToggle } from "@/components/theme-toggle";
import { GlobalSearchTrigger } from "./command-palette";

export function AppTopbar({ onOpenSearch }: { onOpenSearch: () => void }) {
  return (
    <header className="sticky top-0 z-30 flex h-14 w-full min-w-0 items-center gap-2 border-b border-border bg-background/80 px-3 backdrop-blur-md sm:px-4">
      <SidebarTrigger className="shrink-0" />
      <Separator orientation="vertical" className="hidden h-6 sm:block" />
      <Breadcrumbs className="hidden sm:flex" />
      <div className="ml-auto flex min-w-0 shrink items-center gap-1 sm:gap-2">
        <GlobalSearchTrigger onOpen={onOpenSearch} />
        <NotificationsButton />
        <ThemeToggle />
        <UserMenu />
      </div>
    </header>
  );
}
