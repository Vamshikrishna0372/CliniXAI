import { createFileRoute, Link, useParams } from "@tanstack/react-router";
import { CompassIcon } from "lucide-react";
import { PageHeader } from "@/components/app-shell/page-header";
import { EmptyState } from "@/components/dashboard/states";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth-context";

export const Route = createFileRoute("/app/$section")({
  head: () => ({ meta: [{ title: "Page not found — CliniXAI" }, { name: "robots", content: "noindex" }] }),
  component: SectionNotFound,
});

function SectionNotFound() {
  const { section } = useParams({ from: "/app/$section" });
  const { user } = useAuth();
  const title = section.replace(/-/g, " ").replace(/\b\w/g, (c: string) => c.toUpperCase());

  return (
    <div className="space-y-6">
      <PageHeader
        title="Page not found"
        description={`"${title}" doesn't exist or isn't available for your account.`}
        status={{ label: "404", tone: "warning" }}
      />
      <EmptyState
        icon={CompassIcon}
        title="We couldn't find that page"
        description="The link may be outdated, or this module isn't part of your role yet. Head back to your dashboard to keep going."
        action={
          <Button asChild variant="outline" className="min-h-10">
            <Link to="/app" aria-label={`Back to ${user ? user.role : ""} dashboard`}>
              Back to dashboard
            </Link>
          </Button>
        }
      />
    </div>
  );
}
