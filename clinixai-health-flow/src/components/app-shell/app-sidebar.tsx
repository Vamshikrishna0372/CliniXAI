import { Link, useRouterState } from "@tanstack/react-router";
import {
  Sidebar, SidebarContent, SidebarGroup, SidebarGroupContent, SidebarGroupLabel,
  SidebarHeader, SidebarMenu, SidebarMenuButton, SidebarMenuItem, SidebarFooter,
  useSidebar,
} from "@/components/ui/sidebar";
import { BrandMark } from "@/components/brand-mark";
import { NAV_BY_ROLE, ROLE_LABEL, type Role, type NavItem } from "@/lib/roles";
import { useAuth } from "@/lib/auth-context";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";

function pathFor(slug: string) {
  return slug ? `/app/${slug}` : "/app";
}

function groupItems(items: NavItem[]) {
  const main: NavItem[] = [];
  const groups = new Map<string, NavItem[]>();
  for (const it of items) {
    if (!it.group) main.push(it);
    else {
      if (!groups.has(it.group)) groups.set(it.group, []);
      groups.get(it.group)!.push(it);
    }
  }
  return { main, groups };
}

export function AppSidebar({ role }: { role: Role }) {
  const { state } = useSidebar();
  const collapsed = state === "collapsed";
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const { user } = useAuth();
  const items = NAV_BY_ROLE[role];
  const { main, groups } = groupItems(items);

  const isActive = (slug: string) => {
    const p = pathFor(slug);
    if (p === "/app") return pathname === "/app" || pathname === "/app/";
    return pathname === p || pathname.startsWith(p + "/") || pathname.startsWith(p + "?");
  };

  const renderItem = (item: NavItem) => (
    <SidebarMenuItem key={item.slug || "dash"}>
      <SidebarMenuButton asChild isActive={isActive(item.slug)} tooltip={item.title}>
        <Link to={pathFor(item.slug)} className="flex items-center gap-2">
          <item.icon className="h-4 w-4 shrink-0" />
          <span>{item.title}</span>
        </Link>
      </SidebarMenuButton>
    </SidebarMenuItem>
  );

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <Link to="/app" className="flex items-center gap-2 px-1 py-1.5">
          {collapsed ? <BrandMark size="sm" labelClassName="sr-only" /> : <BrandMark size="sm" />}
        </Link>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Workspace</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>{main.map(renderItem)}</SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
        {[...groups.entries()].map(([group, its]) => (
          <SidebarGroup key={group}>
            <SidebarGroupLabel>{group}</SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>{its.map(renderItem)}</SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        ))}
      </SidebarContent>
      <SidebarFooter>
        <div className="flex items-center gap-2 rounded-lg px-2 py-2">
          <Avatar className="h-8 w-8 shrink-0">
            <AvatarFallback className="bg-primary/10 text-primary text-xs font-semibold">
              {user ? (user.firstName[0] || "?") + (user.lastName[0] || "") : "?"}
            </AvatarFallback>
          </Avatar>
          {!collapsed && (
            <div className="min-w-0 flex-1">
              <p className="truncate text-xs font-medium text-foreground">
                {user ? `${user.firstName} ${user.lastName}`.trim() : "Guest"}
              </p>
              <p className="truncate text-[11px] text-muted-foreground">{ROLE_LABEL[role]}</p>
            </div>
          )}
        </div>
      </SidebarFooter>
    </Sidebar>
  );
}
