import { createFileRoute, Outlet, redirect } from "@tanstack/react-router";

export const Route = createFileRoute("/auth")({
  head: () => ({ meta: [{ title: "Sign in — CliniXAI" }] }),
  beforeLoad: ({ location }) => {
    if (location.pathname === "/auth" || location.pathname === "/auth/") {
      throw redirect({ to: "/auth/login" });
    }
  },
  component: () => <Outlet />,
});
