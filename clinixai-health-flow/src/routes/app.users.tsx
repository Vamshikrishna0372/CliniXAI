import { useState, useEffect, useCallback, useMemo } from "react";
import { createFileRoute } from "@tanstack/react-router";
import {
  Users, Search, Shield, UserX, UserCheck, Mail, RefreshCw, AlertTriangle,
  ChevronLeft, ChevronRight, Lock, KeyRound,
} from "lucide-react";
import { PageHeader } from "@/components/app-shell/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { EmptyState } from "@/components/dashboard/states";
import { useAuth } from "@/lib/auth-context";
import { apiClient } from "@/lib/api-client";
import { toast } from "sonner";
import { fmtDateTime } from "@/lib/mock/domain";

export const Route = createFileRoute("/app/users")({
  head: () => ({ meta: [{ title: "User Management — CliniXAI Admin" }, { name: "robots", content: "noindex" }] }),
  component: UsersManagementPage,
});

interface UserItem {
  user_id: string;
  email: string;
  full_name: string;
  role: string;
  account_status: string;
  email_verified: boolean;
  created_at: string;
  updated_at: string;
  last_login_at?: string;
}

function UsersManagementPage() {
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState<UserItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [loading, setLoading] = useState(true);

  // Modal states
  const [selectedUser, setSelectedUser] = useState<UserItem | null>(null);
  const [actionType, setActionType] = useState<"disable" | "enable" | "reinvite" | null>(null);
  const [actionPending, setActionPending] = useState(false);

  // Debounce search
  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedSearch(search);
      setPage(1);
    }, 300);
    return () => clearTimeout(handler);
  }, [search]);

  const loadUsers = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = {
        page: String(page),
        page_size: String(pageSize),
      };
      if (debouncedSearch.trim()) params.search = debouncedSearch.trim();
      if (roleFilter !== "all") params.role = roleFilter;
      if (statusFilter !== "all") params.status = statusFilter;

      const res = await apiClient.admin.listUsers(params);
      if (res && res.data) {
        setUsers(res.data);
        if (res.pagination) {
          setTotal(res.pagination.total);
        }
      }
    } catch (err: any) {
      toast.error(err?.message || "Failed to load user accounts");
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, debouncedSearch, roleFilter, statusFilter]);

  useEffect(() => {
    loadUsers();
  }, [loadUsers]);

  const handleAction = async () => {
    if (!selectedUser || !actionType) return;
    setActionPending(true);
    try {
      if (actionType === "disable") {
        await apiClient.admin.updateUserStatus(selectedUser.user_id, { account_status: "disabled" });
        toast.success(`Account for ${selectedUser.full_name || selectedUser.email} has been disabled.`);
      } else if (actionType === "enable") {
        await apiClient.admin.updateUserStatus(selectedUser.user_id, { account_status: "active" });
        toast.success(`Account for ${selectedUser.full_name || selectedUser.email} is now active.`);
      } else if (actionType === "reinvite") {
        await apiClient.admin.reinviteUser(selectedUser.user_id);
        toast.success(`Setup invitation email redispatched to ${selectedUser.email}.`);
      }
      setSelectedUser(null);
      setActionType(null);
      await loadUsers();
    } catch (err: any) {
      toast.error(err?.message || "Operation failed.");
    } finally {
      setActionPending(false);
    }
  };

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="space-y-6">
      <PageHeader
        title="User & Account Management"
        description="Search, inspect, and manage system user accounts, roles, and lifecycle states."
        actions={
          <Button variant="outline" size="sm" onClick={() => loadUsers()} disabled={loading}>
            <RefreshCw className={`mr-1.5 h-4 w-4 ${loading ? "animate-spin" : ""}`} /> Refresh
          </Button>
        }
      />

      <Card>
        <CardContent className="grid gap-3 p-4 sm:grid-cols-[1fr_180px_180px]">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Search by name, email, or user ID..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9"
            />
          </div>
          <Select value={roleFilter} onValueChange={(v) => { setRoleFilter(v); setPage(1); }}>
            <SelectTrigger><SelectValue placeholder="All Roles" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Roles</SelectItem>
              <SelectItem value="hospital_admin">Hospital Admin</SelectItem>
              <SelectItem value="doctor">Doctor</SelectItem>
              <SelectItem value="hospital_staff">Hospital Staff</SelectItem>
              <SelectItem value="patient">Patient</SelectItem>
            </SelectContent>
          </Select>
          <Select value={statusFilter} onValueChange={(v) => { setStatusFilter(v); setPage(1); }}>
            <SelectTrigger><SelectValue placeholder="All Statuses" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Statuses</SelectItem>
              <SelectItem value="active">Active</SelectItem>
              <SelectItem value="disabled">Disabled</SelectItem>
              <SelectItem value="password_setup_required">Setup Required</SelectItem>
              <SelectItem value="inactive">Inactive</SelectItem>
            </SelectContent>
          </Select>
        </CardContent>
      </Card>

      {loading ? (
        <Card>
          <CardContent className="p-8 text-center text-muted-foreground">
            <RefreshCw className="mx-auto mb-2 h-6 w-6 animate-spin text-primary" />
            <p className="text-sm font-medium">Loading user accounts...</p>
          </CardContent>
        </Card>
      ) : users.length === 0 ? (
        <EmptyState
          icon={Users}
          title="No users found"
          description="No accounts match your current query or filter criteria."
        />
      ) : (
        <Card>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-muted/40 text-xs font-semibold uppercase text-muted-foreground">
                  <tr>
                    <th className="p-3">User</th>
                    <th className="p-3">Role</th>
                    <th className="p-3">Account Status</th>
                    <th className="p-3">Created</th>
                    <th className="p-3">Last Login</th>
                    <th className="p-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {users.map((u) => {
                    const isSelf = currentUser?.id === u.user_id || currentUser?.email === u.email;
                    const isActive = u.account_status === "active";
                    const isSetup = u.account_status === "password_setup_required" || u.account_status === "inactive";
                    return (
                      <tr key={u.user_id} className="hover:bg-muted/20">
                        <td className="p-3">
                          <div className="font-medium text-foreground">{u.full_name || "Unnamed"}</div>
                          <div className="text-xs text-muted-foreground">{u.email}</div>
                          <div className="font-mono text-[10px] text-muted-foreground/70">{u.user_id}</div>
                        </td>
                        <td className="p-3">
                          <Badge variant="outline" className="capitalize">
                            {u.role.replace("_", " ")}
                          </Badge>
                        </td>
                        <td className="p-3">
                          <Badge
                            variant={isActive ? "default" : isSetup ? "secondary" : "destructive"}
                            className="capitalize text-xs"
                          >
                            {u.account_status.replace("_", " ")}
                          </Badge>
                        </td>
                        <td className="p-3 text-xs text-muted-foreground">
                          {fmtDateTime(u.created_at)}
                        </td>
                        <td className="p-3 text-xs text-muted-foreground">
                          {u.last_login_at ? fmtDateTime(u.last_login_at) : "Never"}
                        </td>
                        <td className="p-3 text-right">
                          <div className="flex items-center justify-end gap-1.5">
                            {isSetup && (
                              <Button
                                size="sm"
                                variant="outline"
                                className="h-8 text-xs"
                                onClick={() => { setSelectedUser(u); setActionType("reinvite"); }}
                              >
                                <Mail className="mr-1 h-3.5 w-3.5" /> Reinvite
                              </Button>
                            )}
                            {isActive ? (
                              <Button
                                size="sm"
                                variant="outline"
                                className="h-8 text-xs text-destructive hover:bg-destructive/10 hover:text-destructive"
                                disabled={isSelf}
                                onClick={() => { setSelectedUser(u); setActionType("disable"); }}
                              >
                                <UserX className="mr-1 h-3.5 w-3.5" /> Disable
                              </Button>
                            ) : (
                              <Button
                                size="sm"
                                variant="outline"
                                className="h-8 text-xs text-success hover:bg-success/10 hover:text-success"
                                onClick={() => { setSelectedUser(u); setActionType("enable"); }}
                              >
                                <UserCheck className="mr-1 h-3.5 w-3.5" /> Enable
                              </Button>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {totalPages > 1 && (
              <div className="flex items-center justify-between border-t p-3 text-xs text-muted-foreground">
                <span>Total: {total} accounts</span>
                <div className="flex items-center gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={page <= 1}
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                  >
                    <ChevronLeft className="h-4 w-4" /> Previous
                  </Button>
                  <span>Page {page} of {totalPages}</span>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={page >= totalPages}
                    onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  >
                    Next <ChevronRight className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Confirmation Dialog */}
      <Dialog open={Boolean(selectedUser && actionType)} onOpenChange={(open) => { if (!open) { setSelectedUser(null); setActionType(null); } }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {actionType === "disable" && "Disable User Account"}
              {actionType === "enable" && "Re-Enable User Account"}
              {actionType === "reinvite" && "Resend Setup Invitation"}
            </DialogTitle>
            <DialogDescription>
              {actionType === "disable" && (
                <>
                  Are you sure you want to disable <strong>{selectedUser?.full_name}</strong> ({selectedUser?.email})?
                  <br />
                  <span className="mt-2 block text-amber-600 dark:text-amber-400">
                    This user will immediately be barred from signing in, active refresh sessions will be revoked, and any open WebSocket connection will be terminated.
                  </span>
                </>
              )}
              {actionType === "enable" && (
                <>
                  Re-enable account access for <strong>{selectedUser?.full_name}</strong> ({selectedUser?.email})?
                  <br />
                  <span className="mt-2 block text-muted-foreground">
                    The user will be restored to active status and permitted to authenticate normally.
                  </span>
                </>
              )}
              {actionType === "reinvite" && (
                <>
                  Resend password setup invitation to <strong>{selectedUser?.email}</strong>?
                  <br />
                  <span className="mt-2 block text-muted-foreground">
                    A new secure single-use token will be generated and dispatched to the recipient's email address.
                  </span>
                </>
              )}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="ghost" onClick={() => { setSelectedUser(null); setActionType(null); }} disabled={actionPending}>
              Cancel
            </Button>
            <Button
              variant={actionType === "disable" ? "destructive" : "default"}
              onClick={handleAction}
              disabled={actionPending}
            >
              {actionPending && <RefreshCw className="mr-1.5 h-4 w-4 animate-spin" />}
              {actionType === "disable" ? "Confirm Disable" : actionType === "enable" ? "Confirm Enable" : "Dispatch Invitation"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
