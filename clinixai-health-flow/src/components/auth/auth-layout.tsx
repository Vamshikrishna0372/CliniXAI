import type { ReactNode } from "react";
import { Link } from "@tanstack/react-router";
import { motion } from "framer-motion";
import { ShieldCheck, Lock, KeyRound, HeartPulse } from "lucide-react";
import { BrandMark } from "@/components/brand-mark";

export function AuthLayout({
  title,
  subtitle,
  children,
  footer,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
  footer?: ReactNode;
}) {
  return (
    <div className="min-h-dvh bg-background lg:grid lg:grid-cols-2">
      {/* Brand panel */}
      <aside className="relative hidden overflow-hidden gradient-hero lg:flex lg:flex-col lg:justify-between lg:p-12">
        <Link to="/" className="inline-flex">
          <BrandMark size="lg" />
        </Link>
        <div className="relative z-10 space-y-8">
          <motion.h2
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
            className="max-w-md font-display text-4xl font-bold leading-tight text-foreground"
          >
            AI-powered clinical decisions, made simple.
          </motion.h2>
          <p className="max-w-md text-muted-foreground">
            CliniXAI supports doctors, staff, and patients with explainable AI, streamlined operations, and secure hospital management.
          </p>
          <ul className="grid max-w-md grid-cols-2 gap-3">
            {[
              { icon: ShieldCheck, label: "Secure Authentication" },
              { icon: Lock, label: "Privacy Protected" },
              { icon: KeyRound, label: "Encrypted Access" },
              { icon: HeartPulse, label: "Healthcare Reliable" },
            ].map(({ icon: Icon, label }) => (
              <li key={label} className="glass flex items-center gap-2 rounded-xl px-3 py-2 text-sm">
                <Icon className="h-4 w-4 text-primary" />
                <span className="text-foreground">{label}</span>
              </li>
            ))}
          </ul>
        </div>
        <p className="relative z-10 text-xs text-muted-foreground">© {new Date().getFullYear()} CliniXAI. All rights reserved.</p>
      </aside>

      {/* Form panel */}
      <main className="flex min-h-dvh flex-col px-5 py-8 sm:px-8 lg:min-h-0 lg:justify-center lg:px-12">
        <div className="mb-6 flex items-center justify-between lg:hidden">
          <Link to="/"><BrandMark /></Link>
        </div>
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35 }}
          className="mx-auto w-full max-w-md"
        >
          <div className="mb-6">
            <h1 className="font-display text-2xl font-bold text-foreground sm:text-3xl">{title}</h1>
            {subtitle && <p className="mt-1.5 text-sm text-muted-foreground">{subtitle}</p>}
          </div>
          {children}
          {footer && <div className="mt-6 text-center text-sm text-muted-foreground">{footer}</div>}
        </motion.div>
      </main>
    </div>
  );
}
