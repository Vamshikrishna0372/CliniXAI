import { createFileRoute } from "@tanstack/react-router";
import { UnauthorizedPage } from "@/components/dashboard/states";

export const Route = createFileRoute("/unauthorized")({
  head: () => ({ meta: [{ title: "Sign in required — CliniXAI" }, { name: "robots", content: "noindex" }] }),
  component: UnauthorizedPage,
});
