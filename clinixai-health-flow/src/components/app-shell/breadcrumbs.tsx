import { Fragment } from "react";
import { Link, useRouterState } from "@tanstack/react-router";
import { ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth-context";
import { findNavItem } from "@/lib/roles";

function humanize(s: string) {
  return s.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function Breadcrumbs({ className }: { className?: string }) {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const { user } = useAuth();
  const segments = pathname.split("/").filter(Boolean); // e.g. ["app","appointments"]
  if (segments[0] !== "app") return null;

  const crumbs = [{ label: "Dashboard", href: "/app" }];
  if (segments.length > 1) {
    const slug = segments.slice(1).join("/");
    const item = user ? findNavItem(user.role, segments[1]) : undefined;
    crumbs.push({ label: item?.title ?? humanize(slug), href: pathname });
  }

  return (
    <nav aria-label="Breadcrumb" className={cn("min-w-0 flex-1", className)}>
      <ol className="flex min-w-0 items-center gap-1.5 text-sm">
        {crumbs.map((c, i) => {
          const last = i === crumbs.length - 1;
          return (
            <Fragment key={c.href}>
              {i > 0 && <ChevronRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />}
              {last ? (
                <span className="truncate font-medium text-foreground">{c.label}</span>
              ) : (
                <Link to={c.href} className="truncate text-muted-foreground hover:text-foreground">
                  {c.label}
                </Link>
              )}
            </Fragment>
          );
        })}
      </ol>
    </nav>
  );
}
