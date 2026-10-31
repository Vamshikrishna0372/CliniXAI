import { createFileRoute } from "@tanstack/react-router";
import { motion, useScroll, useTransform, useInView, useMotionValue, animate, AnimatePresence } from "framer-motion";
import { useEffect, useRef, useState } from "react";
import {
  Activity, Bell, Brain, Calendar, ChartBar, CheckCircle2, ChevronDown, FileText, Fingerprint,
  Heart, Hospital, Image as ImageIcon, LayoutDashboard, Lock, LogIn, Mail, MapPin, Menu,
  Moon, Phone, Pill, QrCode, ReceiptText, ShieldCheck, Smartphone, Sparkles, Star, Stethoscope, Sun,
  Timer, TrendingUp, UserCog, Users, X, ArrowRight, Github, Twitter, Linkedin,
} from "lucide-react";
import heroImg from "@/assets/hero-dashboard.jpg";
import aiImg from "@/assets/ai-showcase.jpg";

export const Route = createFileRoute("/")({
  component: LandingPage,
});

/* ---------------- primitives ---------------- */

function cn(...c: Array<string | false | undefined>) {
  return c.filter(Boolean).join(" ");
}

type BtnProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "outline" | "ghost";
  size?: "sm" | "md" | "lg";
  as?: "button" | "a";
  href?: string;
};

function Button({
  variant = "primary", size = "md", className, children, as = "button", href, ...rest
}: BtnProps) {
  const base =
    "inline-flex items-center justify-center gap-2 font-medium rounded-xl transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:opacity-50 disabled:pointer-events-none active:scale-[0.98] whitespace-nowrap";
  const sizes = {
    sm: "h-10 px-4 text-sm min-w-11",
    md: "h-11 px-5 text-sm",
    lg: "h-12 sm:h-13 px-6 sm:px-7 text-sm sm:text-base",
  }[size];
  const variants = {
    primary: "gradient-primary text-primary-foreground shadow-[var(--shadow-glow)] hover:brightness-110 hover:shadow-[var(--shadow-elev-2)]",
    secondary: "bg-secondary text-secondary-foreground hover:bg-muted",
    outline: "border border-border bg-surface hover:bg-muted text-foreground",
    ghost: "text-foreground hover:bg-muted",
  }[variant];
  const cls = cn(base, sizes, variants, className);
  if (as === "a") return <a href={href} className={cls}>{children}</a>;
  return <button className={cls} {...rest}>{children}</button>;
}

function Badge({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <span className={cn(
      "inline-flex items-center gap-1.5 rounded-full border border-border bg-surface px-3 py-1 text-xs font-medium text-muted-foreground",
      className,
    )}>
      {children}
    </span>
  );
}

function SectionHeader({
  eyebrow, title, description, center = true,
}: { eyebrow?: string; title: string; description?: string; center?: boolean }) {
  return (
    <div className={cn("max-w-3xl", center && "mx-auto text-center")}>
      {eyebrow && (
        <Badge className="mb-4">
          <Sparkles className="size-3.5 text-primary" />
          {eyebrow}
        </Badge>
      )}
      <h2 className="font-display text-[26px] leading-tight sm:text-4xl md:text-5xl font-bold tracking-tight text-foreground">
        {title}
      </h2>
      {description && (
        <p className="mt-4 text-[15px] sm:text-lg text-muted-foreground leading-relaxed">{description}</p>
      )}
    </div>
  );
}

/* ---------------- theme toggle ---------------- */

function useTheme() {
  const [theme, setTheme] = useState<"light" | "dark">("light");
  useEffect(() => {
    const saved = (typeof window !== "undefined" && localStorage.getItem("clinixai-theme")) as
      | "light" | "dark" | null;
    const initial =
      saved ??
      (window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    setTheme(initial);
  }, []);
  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    try { localStorage.setItem("clinixai-theme", theme); } catch {}
  }, [theme]);
  return { theme, toggle: () => setTheme((t) => (t === "dark" ? "light" : "dark")) };
}

/* ---------------- scroll spy ---------------- */

function useActiveSection(ids: string[]) {
  const [active, setActive] = useState(ids[0]);
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
        if (visible) setActive(visible.target.id);
      },
      { rootMargin: "-40% 0px -55% 0px", threshold: [0, 0.25, 0.5, 1] },
    );
    ids.forEach((id) => {
      const el = document.getElementById(id);
      if (el) observer.observe(el);
    });
    return () => observer.disconnect();
  }, [ids]);
  return active;
}

/* ---------------- navbar ---------------- */

const NAV = [
  { label: "Home", href: "#home", id: "home" },
  { label: "Features", href: "#features", id: "features" },
  { label: "How It Works", href: "#how", id: "how" },
  { label: "AI Platform", href: "#ai", id: "ai" },
  { label: "About", href: "#about", id: "about" },
  { label: "FAQ", href: "#faq", id: "faq" },
  { label: "Contact", href: "#contact", id: "contact" },
];

function Logo() {
  return (
    <a href="#home" className="flex items-center gap-2 group shrink-0">
      <span className="grid size-9 place-items-center rounded-xl gradient-primary shadow-[var(--shadow-glow)] transition-transform group-hover:scale-105">
        <Activity className="size-5 text-primary-foreground" strokeWidth={2.5} />
      </span>
      <span className="font-display text-lg font-bold tracking-tight">
        Clini<span className="text-gradient">XAI</span>
      </span>
    </a>
  );
}

function Navbar() {
  const { theme, toggle } = useTheme();
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);
  const active = useActiveSection(NAV.map((n) => n.id));

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 12);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    document.body.style.overflow = open ? "hidden" : "";
    return () => { document.body.style.overflow = ""; };
  }, [open]);

  return (
    <header
      className={cn(
        "sticky top-0 z-50 w-full transition-all duration-300",
        scrolled ? "glass shadow-[var(--shadow-soft)]" : "bg-transparent",
      )}
    >
      <div className={cn(
        "mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 flex items-center justify-between gap-3 transition-all duration-300",
        scrolled ? "h-14" : "h-16 sm:h-18",
      )}>
        <Logo />
        <nav className="hidden lg:flex items-center gap-0.5">
          {NAV.map((n) => {
            const isActive = active === n.id;
            return (
              <a
                key={n.href}
                href={n.href}
                className={cn(
                  "relative px-3 py-2 text-sm rounded-lg transition-colors",
                  isActive ? "text-foreground" : "text-muted-foreground hover:text-foreground",
                )}
              >
                {n.label}
                {isActive && (
                  <motion.span
                    layoutId="nav-underline"
                    className="absolute inset-x-3 -bottom-0.5 h-0.5 rounded-full gradient-primary"
                    transition={{ type: "spring", stiffness: 380, damping: 30 }}
                  />
                )}
              </a>
            );
          })}
        </nav>
        <div className="flex items-center gap-2">
          <button
            aria-label="Toggle theme"
            onClick={toggle}
            className="grid size-10 place-items-center rounded-xl border border-border bg-surface hover:bg-muted transition-colors"
          >
            {theme === "dark" ? <Sun className="size-4" /> : <Moon className="size-4" />}
          </button>
          <Button as="a" href="/auth/login" variant="ghost" size="sm" className="hidden md:inline-flex">
            <LogIn className="size-4" /> Login
          </Button>
          <Button as="a" href="/auth/register" size="sm" className="hidden sm:inline-flex">
            Get Started <ArrowRight className="size-4" />
          </Button>
          <button
            aria-label={open ? "Close menu" : "Open menu"}
            onClick={() => setOpen((v) => !v)}
            className="lg:hidden grid size-10 place-items-center rounded-xl border border-border bg-surface"
          >
            {open ? <X className="size-4" /> : <Menu className="size-4" />}
          </button>
        </div>
      </div>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.2 }}
            className="lg:hidden border-t border-border glass"
          >
            <div className="px-4 py-3 flex flex-col gap-1">
              {NAV.map((n) => (
                <a
                  key={n.href}
                  href={n.href}
                  onClick={() => setOpen(false)}
                  className={cn(
                    "px-3 py-3 rounded-lg text-sm font-medium transition-colors min-h-11 flex items-center",
                    active === n.id
                      ? "bg-primary-soft text-primary"
                      : "text-foreground hover:bg-muted",
                  )}
                >
                  {n.label}
                </a>
              ))}
              <div className="flex gap-2 pt-3 mt-2 border-t border-border">
                <Button as="a" href="/auth/login" variant="outline" size="md" className="flex-1"><LogIn className="size-4" />Login</Button>
                <Button as="a" href="/auth/register" size="md" className="flex-1">Get Started</Button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </header>
  );
}

/* ---------------- hero ---------------- */

function Hero() {
  const ref = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start start", "end start"] });
  const y = useTransform(scrollYProgress, [0, 1], [0, 80]);
  return (
    <section id="home" ref={ref} className="relative gradient-hero overflow-hidden">
      {/* soft animated blobs */}
      <motion.div
        aria-hidden
        className="pointer-events-none absolute -top-24 -left-24 size-[420px] rounded-full opacity-40 blur-3xl"
        style={{ background: "radial-gradient(closest-side, oklch(0.75 0.14 195 / 0.5), transparent)" }}
        animate={{ x: [0, 40, 0], y: [0, 20, 0] }}
        transition={{ duration: 14, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.div
        aria-hidden
        className="pointer-events-none absolute top-40 -right-20 size-[380px] rounded-full opacity-40 blur-3xl"
        style={{ background: "radial-gradient(closest-side, oklch(0.72 0.16 250 / 0.45), transparent)" }}
        animate={{ x: [0, -30, 0], y: [0, 30, 0] }}
        transition={{ duration: 16, repeat: Infinity, ease: "easeInOut" }}
      />

      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 pt-10 sm:pt-20 pb-16 sm:pb-24">
        <div className="grid lg:grid-cols-[1.1fr_1fr] gap-10 lg:gap-16 items-center">
          <motion.div
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, ease: [0.2, 0.8, 0.2, 1] }}
            className="text-center lg:text-left"
          >
            <Badge className="mb-4 sm:mb-5">
              <span className="size-1.5 rounded-full bg-success animate-pulse" />
              New · Explainable clinical AI is here
            </Badge>
            <h1 className="font-display text-[34px] leading-[1.08] sm:text-5xl lg:text-6xl font-bold tracking-tight text-foreground">
              AI-powered hospital management &{" "}
              <span className="text-gradient">clinical decision support</span>
            </h1>
            <p className="mt-5 sm:mt-6 text-[15px] sm:text-lg text-muted-foreground max-w-xl mx-auto lg:mx-0 leading-relaxed">
              CliniXAI unifies modern hospital operations with explainable AI — so doctors decide
              faster, staff work smoother, and patients experience better care.
            </p>
            <div className="mt-7 sm:mt-8 flex flex-col sm:flex-row flex-wrap gap-3 justify-center lg:justify-start">
              <Button as="a" href="/auth/register" size="lg" className="w-full sm:w-auto">
                Get Started <ArrowRight className="size-4" />
              </Button>
              <Button as="a" href="#features" size="lg" variant="outline" className="w-full sm:w-auto">
                Explore Features
              </Button>
            </div>
            <div className="mt-8 sm:mt-10 flex flex-wrap justify-center lg:justify-start items-center gap-x-5 gap-y-2.5 text-xs sm:text-sm text-muted-foreground">
              <span className="inline-flex items-center gap-2"><ShieldCheck className="size-4 text-primary" /> HIPAA-ready</span>
              <span className="inline-flex items-center gap-2"><Lock className="size-4 text-primary" /> End-to-end encrypted</span>
              <span className="inline-flex items-center gap-2"><Brain className="size-4 text-primary" /> Explainable AI</span>
            </div>
          </motion.div>

          <motion.div
            style={{ y }}
            initial={{ opacity: 0, scale: 0.96 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.8, delay: 0.15, ease: [0.2, 0.8, 0.2, 1] }}
            className="relative mx-auto w-full max-w-xl lg:max-w-none"
          >
            <div className="absolute -inset-6 -z-10 rounded-3xl gradient-primary opacity-20 blur-3xl" />
            <div className="rounded-2xl border border-border bg-surface shadow-[var(--shadow-elev-3)] overflow-hidden">
              <img
                src={heroImg}
                width={1600}
                height={1200}
                alt="CliniXAI platform preview showing patient vitals, analytics, and AI-assisted diagnostic scan"
                className="w-full h-auto"
              />
            </div>
            <FloatingCard
              className="absolute -left-2 sm:-left-8 top-6 sm:top-8"
              icon={<Heart className="size-4 text-error" />}
              title="Vitals stable"
              value="72 bpm · 98%"
              delay={0.6}
            />
            <FloatingCard
              className="absolute -right-2 sm:-right-6 bottom-6 sm:bottom-10"
              icon={<Brain className="size-4 text-primary" />}
              title="AI confidence"
              value="94.2%"
              delay={0.8}
            />
          </motion.div>
        </div>
      </div>
    </section>
  );
}

function FloatingCard({
  className, icon, title, value, delay = 0.6,
}: { className?: string; icon: React.ReactNode; title: string; value: string; delay?: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12, scale: 0.9 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ delay, duration: 0.6, ease: [0.2, 0.8, 0.2, 1] }}
      className={cn(
        "glass rounded-2xl px-3 py-2.5 sm:px-4 sm:py-3 shadow-[var(--shadow-elev-2)] flex items-center gap-2.5 sm:gap-3",
        className,
      )}
    >
      <span className="grid size-8 sm:size-9 place-items-center rounded-xl bg-primary-soft shrink-0">{icon}</span>
      <div className="min-w-0">
        <div className="text-[10px] sm:text-[11px] uppercase tracking-wider text-muted-foreground">{title}</div>
        <div className="text-xs sm:text-sm font-semibold text-foreground whitespace-nowrap">{value}</div>
      </div>
    </motion.div>
  );
}

/* ---------------- trust ---------------- */

function Trust() {
  const items = ["MediCore", "NovaHealth", "PulseCare", "Wellspring", "Auralis", "Vitalink"];
  return (
    <section className="border-y border-border bg-surface-elevated/60">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8 sm:py-10">
        <p className="text-center text-[10px] sm:text-xs uppercase tracking-[0.2em] text-muted-foreground">
          Trusted by forward-thinking healthcare organizations
        </p>
        <div className="mt-5 sm:mt-6 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4 sm:gap-6 items-center">
          {items.map((n) => (
            <div key={n} className="flex items-center justify-center gap-2 text-muted-foreground/70 hover:text-foreground transition-colors">
              <Hospital className="size-4 shrink-0" />
              <span className="font-display font-semibold tracking-tight text-sm sm:text-base truncate">{n}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ---------------- stats ---------------- */

function Counter({ to, suffix = "" }: { to: number; suffix?: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, margin: "-80px" });
  const mv = useMotionValue(0);
  const [display, setDisplay] = useState("0");
  useEffect(() => {
    if (!inView) return;
    const controls = animate(mv, to, {
      duration: 1.8, ease: [0.2, 0.8, 0.2, 1],
      onUpdate: (v) => setDisplay(Math.floor(v).toLocaleString()),
    });
    return () => controls.stop();
  }, [inView, to, mv]);
  return <span ref={ref}>{display}{suffix}</span>;
}

function Stats() {
  const stats = [
    { icon: Hospital, value: 320, suffix: "+", label: "Hospitals onboarded" },
    { icon: Stethoscope, value: 12500, suffix: "+", label: "Doctors empowered" },
    { icon: Users, value: 1800000, suffix: "+", label: "Patients served" },
    { icon: Calendar, value: 4200000, suffix: "+", label: "Appointments managed" },
    { icon: Brain, value: 950000, suffix: "+", label: "AI analyses run" },
    { icon: FileText, value: 2100000, suffix: "+", label: "Reports generated" },
  ];
  return (
    <section className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-14 sm:py-20 lg:py-24">
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 sm:gap-4 lg:gap-6">
        {stats.map((s, i) => (
          <motion.div
            key={s.label}
            initial={{ opacity: 0, y: 12 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-40px" }}
            transition={{ duration: 0.4, delay: (i % 3) * 0.05 }}
            className="rounded-2xl border border-border bg-surface p-4 sm:p-5 lg:p-6 text-center card-hover"
          >
            <span className="mx-auto grid size-9 place-items-center rounded-xl bg-primary-soft text-primary mb-2 sm:mb-3">
              <s.icon className="size-4" />
            </span>
            <div className="font-display text-xl sm:text-2xl lg:text-3xl font-bold text-gradient">
              <Counter to={s.value} suffix={s.suffix} />
            </div>
            <div className="mt-1 text-[11px] sm:text-xs lg:text-sm text-muted-foreground leading-tight">{s.label}</div>
          </motion.div>
        ))}
      </div>
    </section>
  );
}

/* ---------------- features ---------------- */

const FEATURES = [
  { icon: Hospital, title: "Hospital Management", desc: "Departments, wards, beds, and resources in one operational cockpit." },
  { icon: Calendar, title: "Appointment Scheduling", desc: "Smart scheduling with reminders, waitlists, and multi-doctor coordination." },
  { icon: Users, title: "Patient Management", desc: "Unified patient profiles, history, allergies, and care plans." },
  { icon: Stethoscope, title: "Doctor Workspace", desc: "Consultations, notes, prescriptions, and referrals — beautifully organized." },
  { icon: FileText, title: "Medical Records", desc: "Secure EMR with structured records and version history." },
  { icon: Timer, title: "Medical Timeline", desc: "Chronological view of every visit, lab, and intervention." },
  { icon: Brain, title: "AI Clinical Decision Support", desc: "Actionable, evidence-linked suggestions at the point of care." },
  { icon: ImageIcon, title: "Medical Image Analysis", desc: "Deep-learning models for X-ray, CT, and MRI triage." },
  { icon: Sparkles, title: "Explainable AI (Grad-CAM)", desc: "Every prediction shows what the model looked at, and why." },
  { icon: QrCode, title: "QR Health Card", desc: "Instant patient identification and record retrieval anywhere." },
  { icon: ReceiptText, title: "Billing", desc: "Invoices, insurance workflows, and transparent line-item pricing." },
  { icon: ChartBar, title: "Reports & Analytics", desc: "Operational, clinical, and financial dashboards out of the box." },
  { icon: Activity, title: "Real-time Notifications", desc: "Critical alerts routed to the right person on the right device." },
  { icon: ShieldCheck, title: "Secure Authentication", desc: "Role-based access, audit trails, MFA, and session controls." },
  { icon: Fingerprint, title: "Google Sign-In", desc: "Frictionless SSO for staff and patients." },
  { icon: Smartphone, title: "Responsive Platform", desc: "Pixel-perfect from wall-mounted displays to phones." },
];

function Features() {
  return (
    <section id="features" className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-16 sm:py-24">
      <SectionHeader
        eyebrow="Platform"
        title="Everything a modern hospital needs"
        description="One coherent platform for administrators, doctors, staff, and patients — designed for the way healthcare actually works."
      />
      <div className="mt-10 sm:mt-14 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 sm:gap-5">
        {FEATURES.map((f, i) => (
          <motion.div
            key={f.title}
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-40px" }}
            transition={{ duration: 0.5, delay: (i % 4) * 0.05 }}
            className="group rounded-2xl border border-border bg-surface p-5 sm:p-6 card-hover"
          >
            <div className="grid size-11 place-items-center rounded-xl bg-primary-soft text-primary group-hover:gradient-primary group-hover:text-primary-foreground transition-all duration-300">
              <f.icon className="size-5" />
            </div>
            <h3 className="mt-4 font-display text-base sm:text-lg font-semibold text-foreground">{f.title}</h3>
            <p className="mt-1.5 text-sm text-muted-foreground leading-relaxed">{f.desc}</p>
          </motion.div>
        ))}
      </div>
    </section>
  );
}

/* ---------------- AI showcase ---------------- */

const AI_STEPS = [
  { icon: ImageIcon, title: "Medical Image", desc: "Chest X-ray uploaded" },
  { icon: Brain, title: "AI Prediction", desc: "ResNet-50 inference" },
  { icon: Activity, title: "Confidence Score", desc: "94.2% pneumonia" },
  { icon: Sparkles, title: "Grad-CAM", desc: "Regions of interest" },
  { icon: Stethoscope, title: "Doctor Review", desc: "Human-in-the-loop" },
  { icon: CheckCircle2, title: "Final Diagnosis", desc: "Signed & recorded" },
];

function AIShowcase() {
  return (
    <section id="ai" className="relative overflow-hidden py-16 sm:py-24">
      <div className="absolute inset-0 -z-10 gradient-hero opacity-70" />
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <SectionHeader
          eyebrow="Explainable AI"
          title="From scan to signed diagnosis — with clarity at every step"
          description="CliniXAI never hides behind a black box. Every prediction ships with a confidence score and a visual explanation."
        />
        <div className="mt-10 sm:mt-14 grid lg:grid-cols-[1fr_1.1fr] gap-6 sm:gap-10 items-center">
          <motion.div
            initial={{ opacity: 0, scale: 0.96 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true, margin: "-60px" }}
            transition={{ duration: 0.6 }}
            className="relative rounded-3xl border border-border bg-surface p-3 sm:p-4 shadow-[var(--shadow-elev-2)]"
          >
            <img
              src={aiImg}
              alt="Chest X-ray with Grad-CAM heatmap"
              loading="lazy"
              width={1200}
              height={1200}
              className="w-full h-auto rounded-2xl"
            />
            <div className="absolute bottom-5 left-5 right-5 sm:bottom-6 sm:left-6 sm:right-6 flex items-center justify-between gap-3 glass rounded-xl px-3 py-2.5 sm:px-4 sm:py-3">
              <div className="min-w-0">
                <div className="text-[10px] sm:text-[11px] uppercase tracking-wider text-muted-foreground">Prediction</div>
                <div className="text-xs sm:text-sm font-semibold truncate">Pneumonia · Right lower lobe</div>
              </div>
              <span className="rounded-full bg-success/15 text-success px-2.5 sm:px-3 py-1 text-xs font-semibold shrink-0">94.2%</span>
            </div>
          </motion.div>
          <div className="space-y-2.5 sm:space-y-3">
            {AI_STEPS.map((s, i) => (
              <motion.div
                key={s.title}
                initial={{ opacity: 0, x: 20 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true, margin: "-60px" }}
                transition={{ duration: 0.45, delay: i * 0.06 }}
                className="flex items-center gap-3 sm:gap-4 rounded-2xl border border-border bg-surface px-4 py-3.5 sm:px-5 sm:py-4 card-hover"
              >
                <span className="grid size-10 sm:size-11 place-items-center rounded-xl gradient-primary text-primary-foreground shrink-0">
                  <s.icon className="size-4 sm:size-5" />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="font-semibold text-foreground text-sm sm:text-base">{s.title}</div>
                  <div className="text-xs sm:text-sm text-muted-foreground truncate">{s.desc}</div>
                </div>
                <span className="text-[11px] sm:text-xs font-mono text-muted-foreground shrink-0">0{i + 1}</span>
              </motion.div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

/* ---------------- how it works ---------------- */

const HOW = [
  { icon: UserCog, title: "Patient Registration", desc: "Onboard in minutes with digital ID." },
  { icon: Calendar, title: "Appointment Booking", desc: "Pick a doctor, slot, and modality." },
  { icon: Hospital, title: "Hospital Visit", desc: "Check-in via QR health card." },
  { icon: Stethoscope, title: "Consultation", desc: "Structured notes and orders." },
  { icon: Brain, title: "AI Analysis", desc: "Explainable clinical insights." },
  { icon: CheckCircle2, title: "Doctor Decision", desc: "Confirm, adjust, or escalate." },
  { icon: FileText, title: "Prescription", desc: "e-Prescription & pharmacy sync." },
  { icon: Timer, title: "Follow-up", desc: "Automated reminders and tracking." },
];

function HowItWorks() {
  return (
    <section id="how" className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-16 sm:py-24">
      <SectionHeader
        eyebrow="How it works"
        title="A continuous care journey, orchestrated"
        description="Every step is instrumented, connected, and — where it matters — augmented by AI."
      />
      <div className="mt-10 sm:mt-14 relative">
        <div className="hidden md:block absolute left-1/2 top-0 bottom-0 w-px bg-border -translate-x-1/2" />
        <div className="grid md:grid-cols-2 gap-4 sm:gap-6 md:gap-x-16">
          {HOW.map((s, i) => (
            <motion.div
              key={s.title}
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-40px" }}
              transition={{ duration: 0.5, delay: (i % 2) * 0.08 }}
              className={cn(
                "relative rounded-2xl border border-border bg-surface p-5 sm:p-6 card-hover",
                i % 2 === 0 ? "md:mr-8" : "md:ml-8 md:mt-16",
              )}
            >
              <div className="flex items-center gap-3">
                <span className="grid size-10 place-items-center rounded-xl bg-primary-soft text-primary">
                  <s.icon className="size-5" />
                </span>
                <span className="text-xs font-mono text-muted-foreground">Step 0{i + 1}</span>
              </div>
              <h3 className="mt-4 font-display text-base sm:text-lg font-semibold">{s.title}</h3>
              <p className="mt-1 text-sm text-muted-foreground">{s.desc}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ---------------- why choose ---------------- */

const WHY = [
  { icon: Timer, title: "Faster diagnosis", desc: "Cut time-to-decision by up to 40% with AI-assisted triage." },
  { icon: Sparkles, title: "Transparent AI", desc: "Grad-CAM overlays and confidence scores on every prediction." },
  { icon: Hospital, title: "Better workflows", desc: "Fewer clicks, less duplication, more time for patients." },
  { icon: ShieldCheck, title: "Secure by default", desc: "Encryption, MFA, RBAC, and full audit trails." },
  { icon: Smartphone, title: "Modern experience", desc: "A platform patients and staff actually enjoy using." },
  { icon: Heart, title: "Higher satisfaction", desc: "Measurable lifts in NPS and outcome-based scores." },
];

function WhyChoose() {
  return (
    <section id="about" className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-16 sm:py-24">
      <SectionHeader eyebrow="Why CliniXAI" title="The advantages hospitals feel on day one" />
      <div className="mt-10 sm:mt-14 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-5">
        {WHY.map((w, i) => (
          <motion.div
            key={w.title}
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-40px" }}
            transition={{ duration: 0.5, delay: (i % 3) * 0.05 }}
            className="rounded-2xl border border-border bg-surface p-5 sm:p-6 card-hover"
          >
            <span className="grid size-11 place-items-center rounded-xl gradient-primary text-primary-foreground">
              <w.icon className="size-5" />
            </span>
            <h3 className="mt-4 font-display text-base sm:text-lg font-semibold">{w.title}</h3>
            <p className="mt-1.5 text-sm text-muted-foreground leading-relaxed">{w.desc}</p>
          </motion.div>
        ))}
      </div>
    </section>
  );
}

/* ---------------- platform preview (realistic mockups) ---------------- */

const DASHBOARDS = [
  { key: "patient", label: "Patient", icon: Heart },
  { key: "doctor", label: "Doctor", icon: Stethoscope },
  { key: "staff", label: "Staff", icon: Users },
  { key: "admin", label: "Admin", icon: LayoutDashboard },
];

const SIDEBAR: Record<string, string[]> = {
  patient: ["Overview", "Appointments", "Prescriptions", "Records", "Messages", "Billing"],
  doctor: ["Today", "Patients", "AI Scans", "Prescriptions", "Referrals", "Notes"],
  staff: ["Overview", "Check-ins", "Wards", "Tasks", "Resources", "Reports"],
  admin: ["Overview", "Departments", "Finance", "Staff", "Compliance", "Settings"],
};

function Sparkline({ points, className }: { points: number[]; className?: string }) {
  const w = 100, h = 32;
  const max = Math.max(...points), min = Math.min(...points);
  const range = max - min || 1;
  const path = points
    .map((p, i) => {
      const x = (i / (points.length - 1)) * w;
      const y = h - ((p - min) / range) * h;
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className={cn("w-full h-8", className)} preserveAspectRatio="none">
      <defs>
        <linearGradient id="spark" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="currentColor" stopOpacity="0.25" />
          <stop offset="100%" stopColor="currentColor" stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={`${path} L${w},${h} L0,${h} Z`} fill="url(#spark)" />
      <path d={path} fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function StatTile({ icon: Icon, label, value, trend, tone = "primary" }: {
  icon: React.ElementType; label: string; value: string; trend: string; tone?: "primary" | "success" | "accent" | "warning";
}) {
  const toneMap = {
    primary: "text-primary bg-primary-soft",
    success: "text-success bg-success/10",
    accent: "text-accent bg-accent/10",
    warning: "text-warning bg-warning/10",
  }[tone];
  return (
    <div className="rounded-xl border border-border bg-surface-elevated p-3 sm:p-4">
      <div className="flex items-start justify-between gap-2">
        <span className={cn("grid size-8 place-items-center rounded-lg", toneMap)}>
          <Icon className="size-4" />
        </span>
        <span className="text-[10px] font-medium text-success inline-flex items-center gap-0.5">
          <TrendingUp className="size-3" /> {trend}
        </span>
      </div>
      <div className="mt-2 text-lg sm:text-xl font-bold font-display">{value}</div>
      <div className="text-[11px] text-muted-foreground">{label}</div>
    </div>
  );
}

function DashboardMock({ tab }: { tab: string }) {
  if (tab === "patient") {
    return (
      <div className="space-y-4">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <StatTile icon={Heart} label="Resting heart rate" value="72 bpm" trend="+2%" tone="primary" />
          <StatTile icon={Activity} label="Steps today" value="8,432" trend="+12%" tone="success" />
          <StatTile icon={Pill} label="Adherence" value="96%" trend="+4%" tone="accent" />
          <StatTile icon={Calendar} label="Next visit" value="Tue 10:30" trend="On track" tone="warning" />
        </div>
        <div className="grid md:grid-cols-2 gap-3">
          <div className="rounded-xl border border-border bg-surface-elevated p-4">
            <div className="flex items-center justify-between">
              <div className="text-sm font-semibold">Vitals · Last 7 days</div>
              <Badge>Stable</Badge>
            </div>
            <div className="mt-3 text-primary">
              <Sparkline points={[62, 68, 65, 71, 69, 74, 72]} />
            </div>
            <div className="mt-2 flex justify-between text-[10px] text-muted-foreground font-mono">
              <span>Mon</span><span>Wed</span><span>Fri</span><span>Sun</span>
            </div>
          </div>
          <div className="rounded-xl border border-border bg-surface-elevated p-4">
            <div className="text-sm font-semibold">Upcoming appointments</div>
            <ul className="mt-3 space-y-2.5">
              {[
                { d: "Tue, 10:30", w: "Dr. Priya Nair · Cardiology" },
                { d: "Fri, 15:00", w: "Lab · Blood panel" },
                { d: "Mon 22, 09:00", w: "Dr. Aisha Khan · Follow-up" },
              ].map((a) => (
                <li key={a.d} className="flex items-center gap-3 text-xs">
                  <span className="grid size-8 place-items-center rounded-lg bg-primary-soft text-primary shrink-0">
                    <Calendar className="size-4" />
                  </span>
                  <div className="min-w-0">
                    <div className="font-medium text-foreground truncate">{a.w}</div>
                    <div className="text-muted-foreground">{a.d}</div>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    );
  }
  if (tab === "doctor") {
    return (
      <div className="space-y-4">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <StatTile icon={Users} label="Consultations" value="14" trend="+3" tone="primary" />
          <StatTile icon={Brain} label="AI-flagged scans" value="6" trend="Review" tone="warning" />
          <StatTile icon={FileText} label="Pending notes" value="2" trend="-40%" tone="success" />
          <StatTile icon={Pill} label="Rx to sign" value="9" trend="+2" tone="accent" />
        </div>
        <div className="grid md:grid-cols-[1.4fr_1fr] gap-3">
          <div className="rounded-xl border border-border bg-surface-elevated p-4">
            <div className="text-sm font-semibold">AI-flagged scans</div>
            <ul className="mt-3 divide-y divide-border">
              {[
                { p: "R. Menon · 42M", d: "Chest X-ray", c: 94, tag: "Pneumonia" },
                { p: "S. Iyer · 61F", d: "CT Brain", c: 88, tag: "Micro-bleed" },
                { p: "V. Patel · 35M", d: "MRI Knee", c: 82, tag: "ACL tear" },
              ].map((s) => (
                <li key={s.p} className="flex items-center gap-3 py-2.5 text-xs">
                  <span className="grid size-8 place-items-center rounded-lg gradient-primary text-primary-foreground shrink-0">
                    <Brain className="size-4" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="font-medium text-foreground truncate">{s.p}</div>
                    <div className="text-muted-foreground">{s.d} · {s.tag}</div>
                  </div>
                  <span className="text-[10px] font-semibold rounded-full bg-success/15 text-success px-2 py-0.5 shrink-0">{s.c}%</span>
                </li>
              ))}
            </ul>
          </div>
          <div className="rounded-xl border border-border bg-surface-elevated p-4">
            <div className="text-sm font-semibold">Consultations this week</div>
            <div className="mt-3 text-accent">
              <Sparkline points={[8, 12, 9, 14, 11, 15, 14]} />
            </div>
            <div className="mt-3 flex items-center justify-between text-xs">
              <span className="text-muted-foreground">Avg. per day</span>
              <span className="font-semibold">12.4</span>
            </div>
          </div>
        </div>
      </div>
    );
  }
  if (tab === "staff") {
    return (
      <div className="space-y-4">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <StatTile icon={Hospital} label="Beds occupied" value="184/220" trend="83%" tone="primary" />
          <StatTile icon={Users} label="Check-ins today" value="96" trend="+8%" tone="success" />
          <StatTile icon={Timer} label="Avg. wait" value="12m" trend="-3m" tone="accent" />
          <StatTile icon={Bell} label="Open tasks" value="7" trend="Down" tone="warning" />
        </div>
        <div className="grid md:grid-cols-2 gap-3">
          <div className="rounded-xl border border-border bg-surface-elevated p-4">
            <div className="text-sm font-semibold">Ward occupancy</div>
            <div className="mt-3 space-y-2.5">
              {[
                { w: "ICU", v: 92 }, { w: "General", v: 74 }, { w: "Pediatrics", v: 58 }, { w: "Maternity", v: 66 },
              ].map((w) => (
                <div key={w.w}>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-muted-foreground">{w.w}</span>
                    <span className="font-semibold">{w.v}%</span>
                  </div>
                  <div className="h-1.5 rounded-full bg-muted overflow-hidden">
                    <motion.div
                      initial={{ width: 0 }} whileInView={{ width: `${w.v}%` }}
                      viewport={{ once: true }} transition={{ duration: 0.8, ease: "easeOut" }}
                      className="h-full gradient-primary"
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
          <div className="rounded-xl border border-border bg-surface-elevated p-4">
            <div className="text-sm font-semibold">Task queue</div>
            <ul className="mt-3 space-y-2 text-xs">
              {[
                { t: "Room 214 · Discharge paperwork", s: "High" },
                { t: "Pharmacy restock · Amoxicillin", s: "Med" },
                { t: "Transport · MRI to ward 3", s: "Low" },
                { t: "ICU · Ventilator check", s: "High" },
              ].map((t) => (
                <li key={t.t} className="flex items-center gap-2.5 rounded-lg border border-border bg-surface p-2.5">
                  <span className={cn(
                    "size-2 rounded-full shrink-0",
                    t.s === "High" ? "bg-error" : t.s === "Med" ? "bg-warning" : "bg-success",
                  )} />
                  <span className="text-foreground truncate flex-1">{t.t}</span>
                  <span className="text-muted-foreground shrink-0">{t.s}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    );
  }
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <StatTile icon={TrendingUp} label="Revenue MTD" value="$1.24M" trend="+8.2%" tone="success" />
        <StatTile icon={Users} label="Active patients" value="12,480" trend="+4%" tone="primary" />
        <StatTile icon={Stethoscope} label="Staff utilization" value="87%" trend="+2%" tone="accent" />
        <StatTile icon={ShieldCheck} label="Compliance" value="100%" trend="On track" tone="warning" />
      </div>
      <div className="grid md:grid-cols-[1.4fr_1fr] gap-3">
        <div className="rounded-xl border border-border bg-surface-elevated p-4">
          <div className="flex items-center justify-between">
            <div className="text-sm font-semibold">Revenue · Last 30 days</div>
            <Badge><TrendingUp className="size-3 text-success" /> +8.2%</Badge>
          </div>
          <div className="mt-3 text-primary">
            <Sparkline points={[40, 52, 48, 60, 58, 66, 72, 68, 75, 82, 78, 88]} className="h-16" />
          </div>
        </div>
        <div className="rounded-xl border border-border bg-surface-elevated p-4">
          <div className="text-sm font-semibold">Department mix</div>
          <div className="mt-3 space-y-2 text-xs">
            {[
              { d: "Cardiology", v: 32 }, { d: "Radiology", v: 24 }, { d: "Pediatrics", v: 18 }, { d: "Ortho", v: 14 },
            ].map((d) => (
              <div key={d.d} className="flex items-center gap-2">
                <span className="w-20 text-muted-foreground truncate">{d.d}</span>
                <div className="flex-1 h-1.5 rounded-full bg-muted overflow-hidden">
                  <motion.div
                    initial={{ width: 0 }} whileInView={{ width: `${d.v * 2.5}%` }}
                    viewport={{ once: true }} transition={{ duration: 0.8 }}
                    className="h-full gradient-primary"
                  />
                </div>
                <span className="font-semibold w-8 text-right">{d.v}%</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function PlatformPreview() {
  const [tab, setTab] = useState("patient");
  return (
    <section className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-16 sm:py-24">
      <SectionHeader eyebrow="Product preview" title="Purpose-built for every role" description="One platform, four tailored experiences — every workflow shaped around how the role actually thinks." />
      <div className="mt-8 sm:mt-10 flex flex-wrap justify-center gap-2">
        {DASHBOARDS.map((d) => (
          <button
            key={d.key}
            onClick={() => setTab(d.key)}
            className={cn(
              "inline-flex items-center gap-2 rounded-full px-3.5 sm:px-4 h-10 text-xs sm:text-sm font-medium border transition-all",
              tab === d.key
                ? "gradient-primary text-primary-foreground border-transparent shadow-[var(--shadow-glow)]"
                : "border-border bg-surface text-muted-foreground hover:text-foreground hover:bg-muted",
            )}
          >
            <d.icon className="size-4" />
            {d.label}
          </button>
        ))}
      </div>

      <motion.div
        key={tab}
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="mt-8 sm:mt-10 rounded-2xl sm:rounded-3xl border border-border bg-surface shadow-[var(--shadow-elev-2)] overflow-hidden"
      >
        <div className="border-b border-border px-4 sm:px-5 py-2.5 sm:py-3 flex items-center gap-2">
          <span className="size-2.5 rounded-full bg-error/70" />
          <span className="size-2.5 rounded-full bg-warning/70" />
          <span className="size-2.5 rounded-full bg-success/70" />
          <span className="ml-3 text-[10px] sm:text-xs text-muted-foreground font-mono truncate">clinixai.app / {tab}</span>
        </div>
        <div className="grid lg:grid-cols-[220px_1fr]">
          <aside className="hidden lg:block border-r border-border bg-surface-elevated p-4 space-y-1">
            {SIDEBAR[tab].map((s, i) => (
              <div
                key={s}
                className={cn(
                  "flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors",
                  i === 0 ? "bg-primary-soft text-primary font-medium" : "text-muted-foreground hover:text-foreground",
                )}
              >
                <span className="size-1.5 rounded-full bg-current opacity-60" /> {s}
              </div>
            ))}
          </aside>
          <div className="p-4 sm:p-6 lg:p-7">
            <div className="flex items-center justify-between gap-3 mb-4 sm:mb-5">
              <div className="min-w-0">
                <h3 className="font-display text-base sm:text-lg font-semibold truncate">
                  {DASHBOARDS.find((d) => d.key === tab)?.label} Dashboard
                </h3>
                <div className="text-xs text-muted-foreground">Today · {new Date().toLocaleDateString(undefined, { month: "short", day: "numeric" })}</div>
              </div>
              <span className="grid size-9 place-items-center rounded-xl border border-border bg-surface shrink-0">
                <Bell className="size-4 text-muted-foreground" />
              </span>
            </div>
            <DashboardMock tab={tab} />
          </div>
        </div>
      </motion.div>
    </section>
  );
}

/* ---------------- testimonials ---------------- */

const TESTIMONIALS = [
  { name: "Dr. Priya Nair", role: "Chief of Radiology", org: "MediCore General", quote: "The Grad-CAM overlays changed how our residents learn. We adopted CliniXAI in a month." },
  { name: "Rahul Menon", role: "Hospital Administrator", org: "NovaHealth Group", quote: "Scheduling, records, and billing on one platform. Our monthly close is now painless." },
  { name: "Dr. Aisha Khan", role: "Consultant Physician", org: "PulseCare Hospital", quote: "Explainable AI I actually trust. It suggests, I decide — and my notes write themselves." },
];

function Testimonials() {
  return (
    <section className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-16 sm:py-24">
      <SectionHeader eyebrow="Testimonials" title="Loved by clinicians and operators alike" />
      <div className="mt-10 sm:mt-14 grid grid-cols-1 md:grid-cols-3 gap-4 sm:gap-5">
        {TESTIMONIALS.map((t, i) => (
          <motion.div
            key={t.name}
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-40px" }}
            transition={{ duration: 0.5, delay: i * 0.08 }}
            className="rounded-2xl border border-border bg-surface p-5 sm:p-6 card-hover flex flex-col"
          >
            <div className="flex gap-0.5 mb-3" aria-label="5 out of 5 stars">
              {Array.from({ length: 5 }).map((_, s) => (
                <Star key={s} className="size-4 fill-warning text-warning" />
              ))}
            </div>
            <p className="text-sm sm:text-base text-foreground leading-relaxed flex-1">"{t.quote}"</p>
            <div className="mt-5 sm:mt-6 pt-5 sm:pt-6 border-t border-border flex items-center gap-3">
              <span className="grid size-11 place-items-center rounded-full gradient-primary text-primary-foreground font-semibold shrink-0">
                {t.name.split(" ").map((n) => n[0]).join("").slice(0, 2)}
              </span>
              <div className="min-w-0">
                <div className="text-sm font-semibold truncate">{t.name}</div>
                <div className="text-xs text-muted-foreground truncate">{t.role} · {t.org}</div>
              </div>
            </div>
          </motion.div>
        ))}
      </div>
    </section>
  );
}

/* ---------------- FAQ ---------------- */

const FAQS = [
  { q: "Is CliniXAI compliant with healthcare regulations?", a: "Yes. CliniXAI is designed to align with HIPAA, GDPR, and regional healthcare standards, with encryption in transit and at rest and full audit logging." },
  { q: "How does the explainable AI actually work?", a: "Every model prediction is paired with a confidence score and a Grad-CAM heatmap that shows which regions influenced the decision — so clinicians can validate before signing off." },
  { q: "Can we integrate our existing EMR or lab systems?", a: "CliniXAI exposes standards-based APIs (FHIR, HL7) and provides connectors for major EMR, PACS, and LIS systems." },
  { q: "What about data privacy and patient consent?", a: "Patient data stays in your region. Consent is captured explicitly, and role-based access ensures only the right people see the right records." },
  { q: "How long does implementation typically take?", a: "Most hospitals go live in 4–8 weeks. Our onboarding team handles data migration, staff training, and change management." },
  { q: "Do you offer training and support?", a: "Yes — dedicated onboarding, in-app guides, 24/7 support, and a customer success partner for every hospital." },
];

function FAQ() {
  const [open, setOpen] = useState<number | null>(0);
  return (
    <section id="faq" className="mx-auto max-w-4xl px-4 sm:px-6 lg:px-8 py-16 sm:py-24">
      <SectionHeader eyebrow="FAQ" title="Questions, answered" />
      <div className="mt-8 sm:mt-12 space-y-3">
        {FAQS.map((f, i) => {
          const isOpen = open === i;
          return (
            <div
              key={f.q}
              className={cn(
                "rounded-2xl border bg-surface overflow-hidden transition-colors",
                isOpen ? "border-primary/40 shadow-[var(--shadow-elev-1)]" : "border-border",
              )}
            >
              <button
                onClick={() => setOpen(isOpen ? null : i)}
                className="w-full flex items-center justify-between gap-4 px-5 sm:px-6 py-4 sm:py-5 text-left min-h-14"
                aria-expanded={isOpen}
              >
                <span className="font-medium text-sm sm:text-base text-foreground">{f.q}</span>
                <span className={cn(
                  "grid size-8 place-items-center rounded-full shrink-0 transition-all",
                  isOpen ? "gradient-primary text-primary-foreground rotate-180" : "bg-muted text-muted-foreground",
                )}>
                  <ChevronDown className="size-4" />
                </span>
              </button>
              <motion.div
                initial={false}
                animate={{ height: isOpen ? "auto" : 0, opacity: isOpen ? 1 : 0 }}
                transition={{ duration: 0.3, ease: [0.2, 0.8, 0.2, 1] }}
                className="overflow-hidden"
              >
                <div className="px-5 sm:px-6 pb-5 text-sm sm:text-base text-muted-foreground leading-relaxed">{f.a}</div>
              </motion.div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

/* ---------------- contact ---------------- */

function Contact() {
  return (
    <section id="contact" className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-16 sm:py-24">
      <div className="grid lg:grid-cols-2 gap-8 sm:gap-10">
        <div>
          <SectionHeader
            eyebrow="Contact"
            title="Talk to our team"
            center={false}
            description="Tell us about your hospital. We'll show you a tailored demo within 48 hours."
          />
          <div className="mt-6 sm:mt-8 space-y-3">
            {[
              { icon: Mail, text: "hello@clinixai.health" },
              { icon: Phone, text: "+1 (415) 555-0142" },
              { icon: MapPin, text: "500 Market Street, San Francisco, CA" },
            ].map((c) => (
              <div key={c.text} className="flex items-center gap-3 text-sm rounded-xl border border-border bg-surface p-3">
                <span className="grid size-10 place-items-center rounded-xl bg-primary-soft text-primary shrink-0">
                  <c.icon className="size-4" />
                </span>
                <span className="truncate">{c.text}</span>
              </div>
            ))}
            <div className="mt-4 sm:mt-6 rounded-2xl overflow-hidden border border-border h-48 sm:h-56 relative gradient-hero">
              <svg className="absolute inset-0 w-full h-full opacity-40" viewBox="0 0 400 200" preserveAspectRatio="none">
                <defs>
                  <pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse">
                    <path d="M 20 0 L 0 0 0 20" fill="none" stroke="currentColor" strokeWidth="0.5" className="text-primary" />
                  </pattern>
                </defs>
                <rect width="400" height="200" fill="url(#grid)" />
                <path d="M0 120 Q100 100 200 130 T400 110" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-primary/60" />
                <path d="M0 80 Q120 60 240 90 T400 70" fill="none" stroke="currentColor" strokeWidth="1" className="text-accent/50" />
              </svg>
              <div className="absolute inset-0 grid place-items-center">
                <div className="flex items-center gap-2 rounded-full glass px-4 py-2 text-sm font-medium">
                  <MapPin className="size-4 text-primary" /> San Francisco, CA
                </div>
              </div>
            </div>
          </div>
        </div>
        <form
          onSubmit={(e) => e.preventDefault()}
          className="rounded-2xl sm:rounded-3xl border border-border bg-surface p-5 sm:p-8 shadow-[var(--shadow-elev-1)] space-y-4"
        >
          <div className="grid sm:grid-cols-2 gap-4">
            <Field label="First name" placeholder="Jane" />
            <Field label="Last name" placeholder="Doe" />
          </div>
          <Field label="Work email" type="email" placeholder="jane@hospital.org" />
          <Field label="Hospital / Organization" placeholder="MediCore General" />
          <div>
            <label className="text-sm font-medium text-foreground">How can we help?</label>
            <textarea
              rows={4}
              placeholder="Tell us a bit about your goals…"
              className="mt-1.5 w-full rounded-xl border border-border bg-surface-elevated px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-ring focus:border-transparent transition-all resize-none"
            />
          </div>
          <Button size="lg" className="w-full">Request a demo <ArrowRight className="size-4" /></Button>
          <p className="text-xs text-muted-foreground text-center">
            By submitting, you agree to our Privacy Policy.
          </p>
        </form>
      </div>
    </section>
  );
}

function Field({ label, ...rest }: { label: string } & React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <div>
      <label className="text-sm font-medium text-foreground">{label}</label>
      <input
        {...rest}
        className="mt-1.5 w-full h-11 rounded-xl border border-border bg-surface-elevated px-4 text-sm outline-none focus:ring-2 focus:ring-ring focus:border-transparent transition-all"
      />
    </div>
  );
}

/* ---------------- footer ---------------- */

function Footer() {
  const cols = [
    { title: "Product", links: ["Features", "AI Platform", "Pricing", "Changelog"] },
    { title: "Company", links: ["About", "Careers", "Press", "Partners"] },
    { title: "Resources", links: ["Documentation", "Guides", "Case Studies", "API"] },
    { title: "Legal", links: ["Privacy", "Terms", "HIPAA", "Security"] },
  ];
  return (
    <footer className="border-t border-border bg-surface-elevated">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-12 sm:py-16">
        <div className="grid lg:grid-cols-[1.4fr_2fr_1.2fr] gap-10 lg:gap-12">
          <div>
            <Logo />
            <p className="mt-4 text-sm text-muted-foreground max-w-sm leading-relaxed">
              CliniXAI is the AI-powered operating system for modern hospitals — built for outcomes, designed for people.
            </p>
            <div className="mt-5 sm:mt-6 flex gap-2">
              {[
                { Icon: Twitter, label: "Twitter" },
                { Icon: Linkedin, label: "LinkedIn" },
                { Icon: Github, label: "GitHub" },
              ].map(({ Icon, label }) => (
                <a
                  key={label}
                  href="#"
                  aria-label={label}
                  className="grid size-10 place-items-center rounded-xl border border-border bg-surface hover:bg-primary-soft hover:text-primary hover:border-primary/30 transition-all"
                >
                  <Icon className="size-4" />
                </a>
              ))}
            </div>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-6 sm:gap-8">
            {cols.map((c) => (
              <div key={c.title}>
                <div className="text-sm font-semibold text-foreground">{c.title}</div>
                <ul className="mt-3 space-y-2">
                  {c.links.map((l) => (
                    <li key={l}>
                      <a href="#" className="text-sm text-muted-foreground hover:text-foreground transition-colors">{l}</a>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
          <div>
            <div className="text-sm font-semibold">Stay in the loop</div>
            <p className="mt-3 text-sm text-muted-foreground leading-relaxed">Product updates, case studies, and the occasional deep dive.</p>
            <form onSubmit={(e) => e.preventDefault()} className="mt-4 flex flex-col sm:flex-row gap-2">
              <input
                type="email"
                placeholder="you@hospital.org"
                aria-label="Email address"
                className="flex-1 h-11 rounded-xl border border-border bg-surface px-4 text-sm outline-none focus:ring-2 focus:ring-ring transition-all"
              />
              <Button size="md" className="sm:w-auto">Subscribe</Button>
            </form>
          </div>
        </div>
        <div className="mt-10 sm:mt-14 pt-6 sm:pt-8 border-t border-border flex flex-col sm:flex-row items-center justify-between gap-3 text-center sm:text-left">
          <p className="text-xs text-muted-foreground">© {new Date().getFullYear()} CliniXAI. All rights reserved.</p>
          <p className="text-xs text-muted-foreground">Made with care for healthcare teams.</p>
        </div>
      </div>
    </footer>
  );
}

/* ---------------- page ---------------- */

function LandingPage() {
  return (
    <main className="min-h-dvh bg-background text-foreground overflow-x-hidden">
      <Navbar />
      <Hero />
      <Trust />
      <Stats />
      <Features />
      <AIShowcase />
      <HowItWorks />
      <WhyChoose />
      <PlatformPreview />
      <Testimonials />
      <FAQ />
      <Contact />
      <Footer />
    </main>
  );
}
