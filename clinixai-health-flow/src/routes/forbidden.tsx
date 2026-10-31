import { createFileRoute } from "@tanstack/react-router";
import { ForbiddenPage } from "@/components/dashboard/states";

export const Route = createFileRoute("/forbidden")({
  head: () => ({ meta: [{ title: "Access denied — CliniXAI" }, { name: "robots", content: "noindex" }] }),
  component: ForbiddenPage,
});
