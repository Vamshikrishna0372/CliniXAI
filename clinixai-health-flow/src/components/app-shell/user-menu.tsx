import { useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { LogOut, User, Settings, LifeBuoy, Sun, Moon, Monitor, ChevronDown } from "lucide-react";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel,
  DropdownMenuSeparator, DropdownMenuSub, DropdownMenuSubContent, DropdownMenuSubTrigger,
  DropdownMenuTrigger, DropdownMenuRadioGroup, DropdownMenuRadioItem,
} from "@/components/ui/dropdown-menu";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { useAuth } from "@/lib/auth-context";
import { useTheme } from "@/lib/theme-context";
import { ROLE_LABEL } from "@/lib/roles";

export function UserMenu() {
  const { user, signOut } = useAuth();
  const { theme, setTheme } = useTheme();
  const [confirm, setConfirm] = useState(false);
  const navigate = useNavigate();

  if (!user) return null;
  const initials = (user.firstName[0] || "?") + (user.lastName[0] || "");

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" className="h-10 gap-2 px-2 sm:px-3" aria-label="Open user menu">
            <Avatar className="h-8 w-8">
              <AvatarFallback className="bg-primary/10 text-primary text-xs font-semibold">{initials}</AvatarFallback>
            </Avatar>
            <span className="hidden min-w-0 max-w-[9rem] text-left lg:block">
              <span className="block truncate text-sm font-medium text-foreground">{user.firstName} {user.lastName}</span>
              <span className="block truncate text-[11px] text-muted-foreground">{ROLE_LABEL[user.role]}</span>
            </span>
            <ChevronDown className="hidden h-4 w-4 shrink-0 text-muted-foreground lg:block" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-64">
          <DropdownMenuLabel>
            <div className="flex items-center gap-2">
              <Avatar className="h-9 w-9"><AvatarFallback className="bg-primary/10 text-primary text-xs font-semibold">{initials}</AvatarFallback></Avatar>
              <div className="min-w-0">
                <p className="truncate text-sm font-medium">{user.firstName} {user.lastName}</p>
                <p className="truncate text-xs text-muted-foreground">{user.email}</p>
              </div>
            </div>
          </DropdownMenuLabel>
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={() => navigate({ to: "/app/profile" })}><User className="h-4 w-4" /> My Profile</DropdownMenuItem>
          <DropdownMenuItem onClick={() => navigate({ to: "/app/settings" })}><Settings className="h-4 w-4" /> Settings</DropdownMenuItem>
          <DropdownMenuItem><LifeBuoy className="h-4 w-4" /> Help & Support</DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuSub>
            <DropdownMenuSubTrigger>
              {theme === "dark" ? <Moon className="h-4 w-4" /> : theme === "light" ? <Sun className="h-4 w-4" /> : <Monitor className="h-4 w-4" />}
              Theme
            </DropdownMenuSubTrigger>
            <DropdownMenuSubContent>
              <DropdownMenuRadioGroup value={theme} onValueChange={(v) => setTheme(v as "light" | "dark" | "system")}>
                <DropdownMenuRadioItem value="light"><Sun className="h-4 w-4" /> Light</DropdownMenuRadioItem>
                <DropdownMenuRadioItem value="dark"><Moon className="h-4 w-4" /> Dark</DropdownMenuRadioItem>
                <DropdownMenuRadioItem value="system"><Monitor className="h-4 w-4" /> System</DropdownMenuRadioItem>
              </DropdownMenuRadioGroup>
            </DropdownMenuSubContent>
          </DropdownMenuSub>
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={() => setConfirm(true)} className="text-error focus:text-error">
            <LogOut className="h-4 w-4" /> Log out
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <AlertDialog open={confirm} onOpenChange={setConfirm}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Log out of CliniXAI?</AlertDialogTitle>
            <AlertDialogDescription>You'll need to sign in again to access your workspace.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={async () => { await signOut(); navigate({ to: "/auth/login" }); }}>Log out</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
