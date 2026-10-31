import { useMemo, useState, type ReactNode } from "react";
import { ArrowUpDown, MoreHorizontal, Search, ChevronLeft, ChevronRight } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useIsMobile } from "@/hooks/use-mobile";
import { EmptyState, ErrorState, SkeletonTable } from "./states";
import { cn } from "@/lib/utils";

export type Column<T> = {
  key: string;
  header: string;
  render?: (row: T) => ReactNode;
  sortable?: boolean;
  accessor?: (row: T) => string | number;
  className?: string;
  mobileHidden?: boolean;
};

export type RowAction<T> = { label: string; onClick: (row: T) => void; destructive?: boolean };

export function DataTable<T extends { id: string | number }>({
  data, columns, actions, loading, error, onRetry, searchable = true, pageSize = 10, selectable, emptyTitle = "No records", emptyDescription,
}: {
  data: T[];
  columns: Column<T>[];
  actions?: RowAction<T>[];
  loading?: boolean;
  error?: boolean;
  onRetry?: () => void;
  searchable?: boolean;
  pageSize?: number;
  selectable?: boolean;
  emptyTitle?: string;
  emptyDescription?: string;
}) {
  const isMobile = useIsMobile();
  const [query, setQuery] = useState("");
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<Set<string | number>>(new Set());

  const filtered = useMemo(() => {
    let out = data;
    if (query) {
      const q = query.toLowerCase();
      out = out.filter((r) => JSON.stringify(r).toLowerCase().includes(q));
    }
    if (sortKey) {
      const col = columns.find((c) => c.key === sortKey);
      if (col?.accessor) {
        out = [...out].sort((a, b) => {
          const av = col.accessor!(a), bv = col.accessor!(b);
          if (av < bv) return sortDir === "asc" ? -1 : 1;
          if (av > bv) return sortDir === "asc" ? 1 : -1;
          return 0;
        });
      }
    }
    return out;
  }, [data, query, sortKey, sortDir, columns]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const pageData = filtered.slice((page - 1) * pageSize, page * pageSize);

  const toggleSort = (key: string) => {
    if (sortKey === key) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else { setSortKey(key); setSortDir("asc"); }
  };

  const toggleSel = (id: string | number) => {
    setSelected((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });
  };

  if (loading) return <SkeletonTable />;
  if (error) return <ErrorState onRetry={onRetry} />;

  return (
    <div className="space-y-3">
      {searchable && (
        <div className="flex items-center gap-2 px-4 pt-4 sm:px-6">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input value={query} onChange={(e) => { setQuery(e.target.value); setPage(1); }} placeholder="Search..." className="pl-9" />
          </div>
          {selected.size > 0 && <Badge variant="secondary">{selected.size} selected</Badge>}
        </div>
      )}

      {filtered.length === 0 ? (
        <div className="p-4 sm:p-6"><EmptyState title={emptyTitle} description={emptyDescription} /></div>
      ) : isMobile ? (
        <ul className="divide-y divide-border">
          {pageData.map((row) => (
            <li key={row.id} className="p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 space-y-1">
                  {columns.filter((c) => !c.mobileHidden).map((c) => (
                    <div key={c.key} className="flex items-baseline gap-2 text-sm">
                      <span className="shrink-0 text-xs text-muted-foreground">{c.header}:</span>
                      <span className="min-w-0 truncate text-foreground">{c.render ? c.render(row) : String((row as Record<string, unknown>)[c.key] ?? "")}</span>
                    </div>
                  ))}
                </div>
                {actions && actions.length > 0 && <RowActionsMenu actions={actions} row={row} />}
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-y border-border bg-muted/40 text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                {selectable && <th className="w-10 px-4 py-2"></th>}
                {columns.map((c) => (
                  <th key={c.key} className={cn("px-4 py-2 text-left font-medium", c.className)}>
                    {c.sortable ? (
                      <button className="inline-flex items-center gap-1 hover:text-foreground" onClick={() => toggleSort(c.key)}>
                        {c.header} <ArrowUpDown className="h-3 w-3" />
                      </button>
                    ) : c.header}
                  </th>
                ))}
                {actions && <th className="w-10 px-4 py-2"></th>}
              </tr>
            </thead>
            <tbody>
              {pageData.map((row) => (
                <tr key={row.id} className="border-b border-border transition-colors hover:bg-muted/40">
                  {selectable && (
                    <td className="px-4 py-3"><Checkbox checked={selected.has(row.id)} onCheckedChange={() => toggleSel(row.id)} aria-label="Select row" /></td>
                  )}
                  {columns.map((c) => (
                    <td key={c.key} className={cn("px-4 py-3", c.className)}>{c.render ? c.render(row) : String((row as Record<string, unknown>)[c.key] ?? "")}</td>
                  ))}
                  {actions && <td className="px-4 py-3 text-right"><RowActionsMenu actions={actions} row={row} /></td>}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {filtered.length > pageSize && (
        <div className="flex items-center justify-between gap-3 px-4 pb-4 sm:px-6">
          <p className="text-xs text-muted-foreground">Page {page} of {totalPages}</p>
          <div className="flex gap-1">
            <Button variant="outline" size="icon" disabled={page === 1} onClick={() => setPage((p) => p - 1)} aria-label="Previous page">
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <Button variant="outline" size="icon" disabled={page === totalPages} onClick={() => setPage((p) => p + 1)} aria-label="Next page">
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

function RowActionsMenu<T>({ actions, row }: { actions: RowAction<T>[]; row: T }) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" aria-label="Row actions"><MoreHorizontal className="h-4 w-4" /></Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        {actions.map((a) => (
          <DropdownMenuItem key={a.label} onClick={() => a.onClick(row)} className={cn(a.destructive && "text-error focus:text-error")}>
            {a.label}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
