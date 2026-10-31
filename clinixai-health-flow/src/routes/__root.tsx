import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  Outlet,
  createRootRouteWithContext,
  useRouter,
  HeadContent,
  Scripts,
} from "@tanstack/react-router";
import { useEffect, type ReactNode } from "react";

import appCss from "../styles.css?url";
import { AuthProvider } from "@/lib/auth-context";
import { ClinixProvider } from "@/lib/store/clinix-store";
import { ThemeProvider } from "@/lib/theme-context";
import { Toaster } from "@/components/ui/sonner";
import { NotFoundPage, ServerErrorPage } from "@/components/dashboard/states";

function ErrorBoundary({ error, reset }: { error: any; reset: () => void }) {
  const router = useRouter();
  useEffect(() => {
    console.error(error);
    // Error recorded via console.error
  }, [error]);
  return <ServerErrorPage reset={() => { router.invalidate(); reset(); }} />;
}

export const Route = createRootRouteWithContext<{ queryClient: QueryClient }>()({
  head: () => ({
    meta: [
      { charSet: "utf-8" },
      { name: "viewport", content: "width=device-width, initial-scale=1" },
      { title: "CliniXAI — AI-Powered Hospital Management & Clinical Decision Support" },
      {
        name: "description",
        content:
          "CliniXAI combines modern hospital management with explainable AI to support doctors, streamline operations, and improve patient care.",
      },
      { property: "og:title", content: "CliniXAI — AI-Powered Hospital Management" },
      {
        property: "og:description",
        content:
          "Modern hospital management meets explainable clinical AI. Built for hospitals, doctors, staff, and patients.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
    links: [
      { rel: "stylesheet", href: appCss },
      { rel: "icon", href: "/favicon.svg", type: "image/svg+xml" },
      { rel: "alternate icon", href: "/favicon.ico", type: "image/x-icon" },
      { rel: "preconnect", href: "https://fonts.googleapis.com" },
      { rel: "preconnect", href: "https://fonts.gstatic.com", crossOrigin: "anonymous" },
      {
        rel: "stylesheet",
        href: "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Manrope:wght@500;600;700;800&display=swap",
      },
    ],
  }),
  shellComponent: RootShell,
  component: RootComponent,
  notFoundComponent: NotFoundPage,
  errorComponent: ErrorBoundary,
});

function RootShell({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <head>
        <HeadContent />
      </head>
      <body>
        {children}
        <Scripts />
      </body>
    </html>
  );
}

function RootComponent() {
  const { queryClient } = Route.useRouteContext();

  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <AuthProvider>
          <ClinixProvider>
            {/* Required: nested routes render here. Removing <Outlet /> breaks all child routes. */}
            <Outlet />
            <Toaster richColors position="top-right" />
          </ClinixProvider>
        </AuthProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}
