import { createFileRoute } from "@tanstack/react-router";
import { OfflinePage } from "@/components/dashboard/states";

export const Route = createFileRoute("/offline")({
  head: () => ({ meta: [{ title: "You're offline — CliniXAI" }, { name: "robots", content: "noindex" }] }),
  component: OfflinePage,
});
