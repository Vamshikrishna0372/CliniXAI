import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import type { Role } from "./roles";
import { apiClient, getStoredTokens, setStoredTokens, ApiError } from "./api-client";

export interface BackendUserResponse {
  user_id: string;
  patient_id?: string | null;
  doctor_id?: string | null;
  email: string;
  full_name: string;
  role: string;
  email_verified: boolean;
  account_status: string;
  created_at: string;
  last_login_at?: string | null;
}

export interface BackendTokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: BackendUserResponse;
}

export type User = {
  id: string;
  patientId?: string;
  doctorId?: string;
  firstName: string;
  lastName: string;
  fullName: string;
  email: string;
  role: Role;
  rawRole: string;
  emailVerified: boolean;
  accountStatus: string;
  avatarUrl?: string;
};

export function normalizeRole(backendRole: string): Role {
  const r = (backendRole || "").toLowerCase().trim();
  if (r === "hospital_admin" || r === "admin") return "admin";
  if (r === "hospital_staff" || r === "staff") return "staff";
  if (r === "doctor") return "doctor";
  return "patient";
}

export function parseUserFromBackend(bUser: BackendUserResponse): User {
  const nameParts = (bUser.full_name || "").trim().split(" ");
  const firstName = nameParts[0] || bUser.full_name || "User";
  const lastName = nameParts.slice(1).join(" ");
  return {
    id: bUser.user_id,
    patientId: bUser.patient_id || undefined,
    doctorId: bUser.doctor_id || undefined,
    firstName,
    lastName,
    fullName: bUser.full_name,
    email: bUser.email,
    role: normalizeRole(bUser.role),
    rawRole: bUser.role,
    emailVerified: bUser.email_verified,
    accountStatus: bUser.account_status,
  };
}

type AuthState = {
  user: User | null;
  isAuthenticated: boolean;
  hydrated: boolean;
  signIn: (email: string, password: string) => Promise<User>;
  register: (data: { firstName: string; lastName: string; email: string; password: string }) => Promise<User>;
  signOut: () => Promise<void>;
  forgotPassword: (email: string) => Promise<any>;
  resetPassword: (token: string, newPassword: string) => Promise<any>;
  confirmEmail: (token: string) => Promise<any>;
  refreshSession: () => Promise<User | null>;
  switchRole: (role: Role) => void;
};

const AuthContext = createContext<AuthState | null>(null);

/**
 * Demo accounts directory for convenient UI prefilling.
 * Authentication logic always executes against FastAPI endpoints.
 */
type DemoAccount = { email: string; password: string; firstName: string; lastName: string; role: Role };
export const DEMO_ACCOUNTS: DemoAccount[] = [
  { email: "patient.one@clinixai.com", password: "Patient@123", firstName: "Patient", lastName: "One", role: "patient" },
  { email: "doctor.arjun@clinixai.com", password: "Doctor@123", firstName: "Arjun", lastName: "Rao", role: "doctor" },
  { email: "staff.one@clinixai.com", password: "Staff@123", firstName: "Staff", lastName: "One", role: "staff" },
  { email: "admin@clinixai.com", password: "admin123", firstName: "Primary", lastName: "Admin", role: "admin" },
];

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [hydrated, setHydrated] = useState(false);

  const restoreSession = useCallback(async (): Promise<User | null> => {
    const tokens = getStoredTokens();
    if (!tokens?.accessToken) {
      setUser(null);
      setHydrated(true);
      return null;
    }

    try {
      const bUser = await apiClient.get<BackendUserResponse>("/auth/me");
      const parsedUser = parseUserFromBackend(bUser);
      setUser(parsedUser);
      setHydrated(true);
      return parsedUser;
    } catch (err: any) {
      if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
        setStoredTokens(null);
        setUser(null);
      }
      setHydrated(true);
      return null;
    }
  }, []);

  useEffect(() => {
    restoreSession();
  }, [restoreSession]);

  const signIn = useCallback(async (email: string, password: string): Promise<User> => {
    const res = await apiClient.post<BackendTokenResponse>(
      "/auth/login",
      { email, password },
      { skipAuth: true }
    );
    setStoredTokens({ accessToken: res.access_token, refreshToken: res.refresh_token });
    const parsedUser = parseUserFromBackend(res.user);
    setUser(parsedUser);
    return parsedUser;
  }, []);

  const register = useCallback(
    async ({
      firstName,
      lastName,
      email,
      password,
    }: {
      firstName: string;
      lastName: string;
      email: string;
      password: string;
    }): Promise<User> => {
      const fullName = `${firstName.trim()} ${lastName.trim()}`.trim();
      const res = await apiClient.post<BackendTokenResponse>(
        "/auth/register",
        { email, password, full_name: fullName },
        { skipAuth: true }
      );
      setStoredTokens({ accessToken: res.access_token, refreshToken: res.refresh_token });
      const parsedUser = parseUserFromBackend(res.user);
      setUser(parsedUser);
      return parsedUser;
    },
    []
  );

  const signOut = useCallback(async () => {
    const tokens = getStoredTokens();
    if (tokens?.refreshToken) {
      try {
        await apiClient.post("/auth/logout", { refresh_token: tokens.refreshToken });
      } catch {
        // Ignore logout network errors and clean local session
      }
    }
    setStoredTokens(null);
    setUser(null);
  }, []);

  const forgotPassword = useCallback(async (email: string) => {
    return apiClient.post("/auth/password/forgot", { email }, { skipAuth: true });
  }, []);

  const resetPassword = useCallback(async (token: string, newPassword: string) => {
    return apiClient.post("/auth/password/reset", { token, new_password: newPassword }, { skipAuth: true });
  }, []);

  const confirmEmail = useCallback(async (token: string) => {
    return apiClient.post("/auth/email-verification/confirm", { token }, { skipAuth: true });
  }, []);

  const switchRole = useCallback((role: Role) => {
    setUser((u) => {
      if (!u) return u;
      return { ...u, role };
    });
  }, []);

  const value = useMemo<AuthState>(
    () => ({
      user,
      isAuthenticated: !!user,
      hydrated,
      signIn,
      register,
      signOut,
      forgotPassword,
      resetPassword,
      confirmEmail,
      refreshSession: restoreSession,
      switchRole,
    }),
    [user, hydrated, signIn, register, signOut, forgotPassword, resetPassword, confirmEmail, restoreSession, switchRole]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
