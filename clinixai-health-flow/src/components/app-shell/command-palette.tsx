import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import {
  Search, LogOut, Sun, Moon, Calendar, UserPlus, LogIn as CheckIn, ListOrdered,
  ClipboardList, Brain, FileText, BarChart3, ShieldAlert, Clock, Loader2, SearchX,
} from "lucide-react";
import {
  CommandDialog, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList, CommandSeparator, CommandShortcut,
} from "@/components/ui/command";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth-context";
import { useTheme } from "@/lib/theme-context";
import { useClinix } from "@/lib/store/clinix-store";
import { NAV_BY_ROLE, ROLE_LABEL, type Role } from "@/lib/roles";
import {
  buildSearchIndex, searchIndex, highlightParts, SEARCH_GROUP_ORDER,
  type SearchResult, type SearchGroup,
} from "@/lib/search/global-search";

type Command = { icon: React.ComponentType<{ className?: string }>; label: string; to: string };

const QUICK_ACTIONS_BY_ROLE: Record<Role, Command[]> = {
  patient: [{ icon: Calendar, label: "Book Appointment", to: "/app/book" }],
  staff: [
    { icon: UserPlus, label: "Register Patient", to: "/app/patient-registration" },
    { icon: CheckIn, label: "Check-In Patient", to: "/app/check-in" },
    { icon: ListOrdered, label: "Open Queue", to: "/app/queue" },
  ],
  doctor: [
    { icon: ClipboardList, label: "Consultations", to: "/app/consultations" },
    { icon: Brain, label: "AI Analysis", to: "/app/ai-analysis" },
  ],
  admin: [
    { icon: FileText, label: "Reports", to: "/app/reports" },
    { icon: BarChart3, label: "Analytics", to: "/app/analytics" },
    { icon: ShieldAlert, label: "Activity Logs", to: "/app/activity-logs" },
  ],
};

const RECENT_KEY = "clinixai.recentCmds";
const RECENT_SEARCH_KEY = "clinixai.recentSearches";

export function useCommandPalette() {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  return { open, setOpen };
}

function Highlight({ text, query }: { text: string; query: string }) {
  return (
    <>
      {highlightParts(text, query).map((p, i) =>
        p.match ? (
          <mark key={i} className="rounded-[2px] bg-primary/20 px-0.5 text-foreground">{p.text}</mark>
        ) : (
          <span key={i}>{p.text}</span>
        ),
      )}
    </>
  );
}

export function CommandPalette({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const navigate = useNavigate();
  const { user, signOut } = useAuth();
  const { resolved, toggle } = useTheme();
  const store = useClinix();
  const [recent, setRecent] = useState<string[]>([]);
  const [recentSearches, setRecentSearches] = useState<string[]>([]);
  const [query, setQuery] = useState("");
  const [debounced, setDebounced] = useState("");
  const [searching, setSearching] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const role = user?.role ?? "patient";

  const navCommands = useMemo<Command[]>(
    () => NAV_BY_ROLE[role].map((n) => ({ icon: n.icon, label: n.title, to: n.slug ? `/app/${n.slug}` : "/app" })),
    [role],
  );
  const quickActions = QUICK_ACTIONS_BY_ROLE[role] ?? [];
  const allCommands = useMemo(() => [...navCommands, ...quickActions], [navCommands, quickActions]);

  const index = useMemo(
    () => buildSearchIndex(
      {
        patients: store?.patients ?? [], doctors: store?.doctors ?? [], doctorMeta: store?.doctorMeta ?? [],
        staff: store?.staff ?? [], departments: store?.departments ?? [], appointments: store?.appointments ?? [],
        consultations: store?.consultations ?? [], prescriptions: store?.prescriptions ?? [],
        aiReports: store?.aiReports ?? [], bills: store?.bills ?? [], receipts: store?.receipts ?? [],
        documents: store?.documents ?? [], queue: store?.queue ?? [], activityLog: store?.activityLog ?? [],
        notifications: store?.notifications ?? [], followUps: store?.followUps ?? [],
        aiModels: store?.aiModels ?? [], trash: store?.trash ?? [],
      },
      role,
      user?.id,
    ),
    [store, role, user?.id],
  );

  /* Debounced search with an explicit loading state. */
  useEffect(() => {
    if (timer.current) clearTimeout(timer.current);
    if (!query.trim()) {
      setDebounced("");
      setSearching(false);
      return;
    }
    setSearching(true);
    timer.current = setTimeout(() => {
      setDebounced(query);
      setSearching(false);
    }, 140);
    return () => { if (timer.current) clearTimeout(timer.current); };
  }, [query]);

  const results = useMemo(() => searchIndex(index, debounced), [index, debounced]);
  const grouped = useMemo(() => {
    const map = new Map<SearchGroup, SearchResult[]>();
    for (const r of results) {
      const arr = map.get(r.group) ?? [];
      arr.push(r);
      map.set(r.group, arr);
    }
    return SEARCH_GROUP_ORDER.filter((g) => map.has(g)).map((g) => [g, map.get(g)!] as const);
  }, [results]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      setRecent(JSON.parse(window.localStorage.getItem(RECENT_KEY) || "[]"));
      setRecentSearches(JSON.parse(window.localStorage.getItem(RECENT_SEARCH_KEY) || "[]"));
    } catch {
      /* noop */
    }
    if (!open) setQuery("");
  }, [open]);

  const go = useCallback((to: string) => {
    onOpenChange(false);
    navigate({ to });
  }, [navigate, onOpenChange]);

  const run = (to: string, label: string) => {
    go(to);
    if (typeof window !== "undefined") {
      const next = [label, ...recent.filter((l) => l !== label)].slice(0, 5);
      window.localStorage.setItem(RECENT_KEY, JSON.stringify(next));
    }
  };

  const openResult = (r: SearchResult) => {
    go(r.to);
    if (typeof window !== "undefined" && debounced.trim()) {
      const next = [debounced.trim(), ...recentSearches.filter((s) => s !== debounced.trim())].slice(0, 5);
      window.localStorage.setItem(RECENT_SEARCH_KEY, JSON.stringify(next));
    }
  };

  const runAction = (action: () => void) => {
    onOpenChange(false);
    action();
  };

  const isSearching = query.trim().length > 0;

  return (
    <CommandDialog
      open={open}
      onOpenChange={onOpenChange}
      shouldFilter={!isSearching}
      title="Global search"
      description="Search patients, doctors, appointments, records, bills, AI reports and pages."
    >
      <CommandInput
        value={query}
        onValueChange={setQuery}
        placeholder="Search records, pages and actions..."
      />
      <CommandList className="max-h-[min(70vh,26rem)]">
        {isSearching ? (
          <>
            {searching && (
              <div className="flex items-center gap-2 px-4 py-6 text-sm text-muted-foreground" role="status" aria-live="polite">
                <Loader2 className="h-4 w-4 animate-spin" /> Searching CliniXAI…
              </div>
            )}
            {!searching && results.length === 0 && (
              <div className="flex flex-col items-center gap-1.5 px-4 py-8 text-center" role="status" aria-live="polite">
                <SearchX className="h-6 w-6 text-muted-foreground" />
                <p className="text-sm font-medium text-foreground">No matches for “{debounced}”</p>
                <p className="text-xs text-muted-foreground">Try a patient name, ID, doctor, diagnosis or bill number.</p>
              </div>
            )}
            {!searching && grouped.map(([group, items]) => (
              <CommandGroup key={group} heading={group}>
                {items.map((r) => (
                  <CommandItem key={r.id} value={r.id} onSelect={() => openResult(r)} className="items-start">
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-foreground">
                        <Highlight text={r.title} query={debounced} />
                      </p>
                      <p className="truncate text-xs text-muted-foreground">
                        <Highlight text={r.subtitle} query={debounced} />
                      </p>
                    </div>
                  </CommandItem>
                ))}
              </CommandGroup>
            ))}
            {!searching && results.length > 0 && (
              <>
                <CommandSeparator />
                <CommandGroup heading="Pages">
                  {allCommands
                    .filter((c) => c.label.toLowerCase().includes(debounced.toLowerCase()))
                    .slice(0, 5)
                    .map((it) => (
                      <CommandItem key={`p-${it.to}`} value={`page-${it.to}`} onSelect={() => run(it.to, it.label)}>
                        <it.icon className="h-4 w-4" />
                        <Highlight text={it.label} query={debounced} />
                      </CommandItem>
                    ))}
                </CommandGroup>
              </>
            )}
          </>
        ) : (
          <>
            <CommandEmpty>No results found.</CommandEmpty>
            {recentSearches.length > 0 && (
              <>
                <CommandGroup heading="Recent searches">
                  {recentSearches.map((s) => (
                    <CommandItem key={`rs-${s}`} value={`rs-${s}`} onSelect={() => setQuery(s)}>
                      <Clock className="h-4 w-4 text-muted-foreground" /> {s}
                    </CommandItem>
                  ))}
                </CommandGroup>
                <CommandSeparator />
              </>
            )}
            {recent.length > 0 && (
              <>
                <CommandGroup heading="Recent pages">
                  {recent.map((r) => {
                    const found = allCommands.find((i) => i.label === r);
                    if (!found) return null;
                    const Icon = found.icon;
                    return (
                      <CommandItem key={r} onSelect={() => run(found.to, found.label)}>
                        <Icon className="h-4 w-4" /> {found.label}
                      </CommandItem>
                    );
                  })}
                </CommandGroup>
                <CommandSeparator />
              </>
            )}
            <CommandGroup heading={ROLE_LABEL[role]}>
              {navCommands.map((it) => (
                <CommandItem key={it.to} onSelect={() => run(it.to, it.label)}>
                  <it.icon className="h-4 w-4" /> {it.label}
                </CommandItem>
              ))}
            </CommandGroup>
            {quickActions.length > 0 && (
              <>
                <CommandSeparator />
                <CommandGroup heading="Quick actions">
                  {quickActions.map((it) => (
                    <CommandItem key={`qa-${it.to}`} onSelect={() => run(it.to, it.label)}>
                      <it.icon className="h-4 w-4" /> {it.label}
                    </CommandItem>
                  ))}
                </CommandGroup>
              </>
            )}
            <CommandSeparator />
            <CommandGroup heading="Preferences">
              <CommandItem onSelect={() => runAction(toggle)}>
                {resolved === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
                {resolved === "dark" ? "Switch to light mode" : "Switch to dark mode"}
              </CommandItem>
              <CommandItem
                onSelect={() => runAction(async () => { await signOut(); navigate({ to: "/auth/login" }); })}
                className="text-error"
              >
                <LogOut className="h-4 w-4" /> Log out
              </CommandItem>
            </CommandGroup>
          </>
        )}
      </CommandList>
    </CommandDialog>
  );
}

export function GlobalSearchTrigger({ onOpen }: { onOpen: () => void }) {
  return (
    <>
      <Button variant="ghost" size="icon" onClick={onOpen} aria-label="Open search" className="h-10 w-10 lg:hidden">
        <Search className="h-5 w-5" />
      </Button>
      <button
        type="button"
        onClick={onOpen}
        aria-label="Open command palette"
        className="hidden h-10 w-56 min-w-0 items-center gap-2 rounded-lg border border-border bg-muted/40 px-3 text-sm text-muted-foreground transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring lg:flex xl:w-72"
      >
        <Search className="h-4 w-4 shrink-0" />
        <span className="flex-1 truncate text-left">Search patients, reports...</span>
        <CommandShortcut>⌘K</CommandShortcut>
      </button>
    </>
  );
}
