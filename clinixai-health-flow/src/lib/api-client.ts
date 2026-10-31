/**
 * CliniXAI Standardized Production-Ready API Client
 * Centralizes HTTP requests, Authorization headers, Base URL, Timeouts, and Error Handling.
 */

const LOCAL_API_URL = "http://localhost:8000/api/v1";
const PROD_API_URL = "https://clinixai-2qfy.onrender.com/api/v1";

/**
 * Dynamically resolves the API base URL depending on environment and host.
 * 
 * Guarantees:
 * - Public / Cloud deployments (Vercel, custom domain) NEVER call localhost or 127.0.0.1.
 * - Local development (localhost, 127.0.0.1) ALWAYS calls local backend (port 8000).
 * - Zero silent fallback to user's computer in production.
 */
export function getApiBaseUrl(): string {
  // Normalize any explicit environment variable
  const rawEnv = (import.meta.env?.VITE_API_URL || import.meta.env?.VITE_API_BASE_URL as string | undefined)?.trim();
  const normalizedEnv = rawEnv
    ? (rawEnv.replace(/\/+$/, "").endsWith("/api/v1") ? rawEnv.replace(/\/+$/, "") : `${rawEnv.replace(/\/+$/, "")}/api/v1`)
    : null;

  // 1. Browser Runtime Detection (Authoritative Ground Truth)
  if (typeof window !== "undefined" && window.location?.hostname) {
    const hostname = window.location.hostname.toLowerCase();

    // Explicit local development check
    if (hostname === "localhost" || hostname === "127.0.0.1") {
      if (normalizedEnv && (normalizedEnv.includes("localhost") || normalizedEnv.includes("127.0.0.1"))) {
        return normalizedEnv;
      }
      return LOCAL_API_URL;
    }

    // Public / Cloud Deployment (clini-xai.vercel.app, preview branches, custom domains)
    // STRICT: NEVER allow localhost or 127.0.0.1 to be returned in a deployed web browser!
    if (normalizedEnv && !normalizedEnv.includes("localhost") && !normalizedEnv.includes("127.0.0.1")) {
      return normalizedEnv;
    }
    return PROD_API_URL;
  }

  // 2. Build-Time / SSR Fallback
  if (import.meta.env?.PROD) {
    return PROD_API_URL;
  }
  if (normalizedEnv && !normalizedEnv.includes("localhost") && !normalizedEnv.includes("127.0.0.1")) {
    return normalizedEnv;
  }
  return LOCAL_API_URL;
}

export function getWebSocketUrl(_token?: string): string {
  const apiBase = getApiBaseUrl().replace(/\/+$/, "");
  const wsProtocol = apiBase.startsWith("https:") ? "wss:" : "ws:";
  const cleanBase = apiBase.replace(/^https?:/i, "").replace(/\/+$/, "");
  return `${wsProtocol}${cleanBase}/notifications/ws`;
}

export interface ApiErrorDetail {
  loc?: (string | number)[];
  msg?: string;
  type?: string;
}

export class ApiError extends Error {
  public status: number;
  public details: ApiErrorDetail[] | any;

  constructor(status: number, message: string, details?: any) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.details = details;
  }
}

export interface AuthTokens {
  accessToken: string;
  refreshToken: string;
}

const TOKENS_STORAGE_KEY = "clinixai.tokens";

export function getStoredTokens(): AuthTokens | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(TOKENS_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (parsed.accessToken && parsed.refreshToken) {
      return {
        accessToken: parsed.accessToken,
        refreshToken: parsed.refreshToken,
      };
    }
    return null;
  } catch {
    return null;
  }
}

export function setStoredTokens(tokens: AuthTokens | null): void {
  if (typeof window === "undefined") return;
  if (!tokens) {
    localStorage.removeItem(TOKENS_STORAGE_KEY);
  } else {
    localStorage.setItem(TOKENS_STORAGE_KEY, JSON.stringify(tokens));
  }
}

export interface RequestOptions extends RequestInit {
  skipAuth?: boolean;
  timeoutMs?: number;
  _isRetry?: boolean;
}

let isRefreshing = false;
let refreshPromise: Promise<AuthTokens | null> | null = null;

async function performTokenRefresh(): Promise<AuthTokens | null> {
  const tokens = getStoredTokens();
  if (!tokens?.refreshToken) {
    setStoredTokens(null);
    return null;
  }

  try {
    const baseUrl = getApiBaseUrl().replace(/\/+$/, "");
    const res = await fetch(`${baseUrl}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: tokens.refreshToken }),
      credentials: "include",
    });

    if (!res.ok) {
      setStoredTokens(null);
      return null;
    }

    const data = await res.json();
    if (!data?.access_token || !data?.refresh_token) {
      setStoredTokens(null);
      return null;
    }

    const newTokens: AuthTokens = {
      accessToken: data.access_token,
      refreshToken: data.refresh_token,
    };
    setStoredTokens(newTokens);
    return newTokens;
  } catch {
    setStoredTokens(null);
    return null;
  }
}

export async function refreshTokenMutex(): Promise<AuthTokens | null> {
  if (!isRefreshing) {
    isRefreshing = true;
    refreshPromise = performTokenRefresh().finally(() => {
      isRefreshing = false;
      refreshPromise = null;
    });
  }
  return refreshPromise;
}

async function fetchWithTimeout(url: string, options: RequestOptions = {}): Promise<Response> {
  const { timeoutMs = 60000, _isRetry, skipAuth, ...fetchOptions } = options;
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(url, {
      credentials: "include",
      ...fetchOptions,
      signal: controller.signal,
    });
    clearTimeout(timeoutId);
    return response;
  } catch (err: any) {
    clearTimeout(timeoutId);
    if (err.name === "AbortError") {
      throw new ApiError(408, "Request timed out. The server may be waking up from sleep; please try again.", { originalError: err.message });
    }
    // Auto-retry once for login / health endpoints if backend was sleeping or experiencing transient network latency
    if (!_isRetry && (url.includes("/auth/login") || url.includes("/health"))) {
      try {
        await new Promise((r) => setTimeout(r, 2000));
        return await fetchWithTimeout(url, { ...options, _isRetry: true, timeoutMs: 60000 });
      } catch {
        // Fall through to error
      }
    }
    throw new ApiError(0, "Network error: Unable to connect to backend server.", { originalError: err.message });
  }
}

export async function apiRequest<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
  const baseUrl = getApiBaseUrl().replace(/\/+$/, "");
  const path = endpoint.startsWith("/") ? endpoint : `/${endpoint}`;
  const url = `${baseUrl}${path}`;

  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  };

  if (!(options.body instanceof FormData) && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }

  if (!options.skipAuth) {
    const tokens = getStoredTokens();
    if (tokens?.accessToken) {
      headers["Authorization"] = `Bearer ${tokens.accessToken}`;
    }
  }

  let response: Response;
  try {
    response = await fetchWithTimeout(url, {
      ...options,
      headers,
    });
  } catch (err: any) {
    if (err instanceof ApiError) throw err;
    throw new ApiError(0, "Network unavailable", err);
  }

  // Handle 401 Unauthorized with token refresh & retry (once)
  if (
    response.status === 401 &&
    !options.skipAuth &&
    !options._isRetry &&
    !path.startsWith("/auth/login") &&
    !path.startsWith("/auth/refresh") &&
    !path.startsWith("/auth/register")
  ) {
    const newTokens = await refreshTokenMutex();
    if (newTokens?.accessToken) {
      const retryHeaders = {
        ...headers,
        Authorization: `Bearer ${newTokens.accessToken}`,
      };
      return apiRequest<T>(endpoint, {
        ...options,
        headers: retryHeaders,
        _isRetry: true,
      });
    }
  }

  if (response.status === 204) {
    return {} as T;
  }

  let data: any;
  const contentType = response.headers.get("content-type");
  if (contentType && contentType.includes("application/json")) {
    try {
      data = await response.json();
    } catch {
      data = null;
    }
  } else {
    try {
      const text = await response.text();
      data = { message: text };
    } catch {
      data = null;
    }
  }

  if (!response.ok) {
    let errorMessage = "An unexpected error occurred.";
    if (data?.detail) {
      if (typeof data.detail === "string") {
        errorMessage = data.detail;
      } else if (Array.isArray(data.detail)) {
        errorMessage = data.detail.map((d: any) => d.msg || JSON.stringify(d)).join("; ");
      } else {
        errorMessage = JSON.stringify(data.detail);
      }
    } else if (data?.message) {
      errorMessage = data.message;
    } else if (data?.error?.message) {
      errorMessage = data.error.message;
    } else if (response.status === 401) {
      errorMessage = "Unauthorized access. Please log in.";
    } else if (response.status === 403) {
      errorMessage = "Forbidden: You do not have permission to perform this action.";
    } else if (response.status === 404) {
      errorMessage = "Requested resource not found.";
    } else if (response.status === 409) {
      errorMessage = "Conflict: The requested operation conflicted with the current resource state.";
    } else if (response.status === 422) {
      errorMessage = "Validation error: Please check your input parameters.";
    } else if (response.status === 503) {
      errorMessage = "Service temporarily unavailable. Please try again later.";
    } else if (response.status >= 500) {
      errorMessage = "Internal server error. Please try again later.";
    }

    throw new ApiError(response.status, errorMessage, data?.detail || data);
  }

  return data as T;
}

export async function apiBlobRequest(endpoint: string, options: RequestOptions = {}): Promise<Blob> {
  const baseUrl = getApiBaseUrl().replace(/\/+$/, "");
  const path = endpoint.startsWith("/") ? endpoint : `/${endpoint}`;
  const url = `${baseUrl}${path}`;

  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  };

  if (!options.skipAuth) {
    const tokens = getStoredTokens();
    if (tokens?.accessToken) {
      headers["Authorization"] = `Bearer ${tokens.accessToken}`;
    }
  }

  let response: Response;
  try {
    response = await fetchWithTimeout(url, {
      ...options,
      headers,
    });
  } catch (err: any) {
    if (err instanceof ApiError) throw err;
    throw new ApiError(0, "Network unavailable", err);
  }

  if (
    response.status === 401 &&
    !options.skipAuth &&
    !options._isRetry
  ) {
    const newTokens = await refreshTokenMutex();
    if (newTokens?.accessToken) {
      const retryHeaders = {
        ...headers,
        Authorization: `Bearer ${newTokens.accessToken}`,
      };
      return apiBlobRequest(endpoint, {
        ...options,
        headers: retryHeaders,
        _isRetry: true,
      });
    }
  }

  if (!response.ok) {
    throw new ApiError(response.status, `Failed to fetch binary asset: HTTP ${response.status}`);
  }

  return await response.blob();
}

export const apiClient = {
  get: <T>(endpoint: string, options?: RequestOptions) =>
    apiRequest<T>(endpoint, { ...options, method: "GET" }),

  post: <T>(endpoint: string, body?: any, options?: RequestOptions) =>
    apiRequest<T>(endpoint, {
      ...options,
      method: "POST",
      body: body instanceof FormData ? body : JSON.stringify(body),
    }),

  put: <T>(endpoint: string, body?: any, options?: RequestOptions) =>
    apiRequest<T>(endpoint, {
      ...options,
      method: "PUT",
      body: body instanceof FormData ? body : JSON.stringify(body),
    }),

  patch: <T>(endpoint: string, body?: any, options?: RequestOptions) =>
    apiRequest<T>(endpoint, {
      ...options,
      method: "PATCH",
      body: body instanceof FormData ? body : JSON.stringify(body),
    }),

  delete: <T>(endpoint: string, options?: RequestOptions) =>
    apiRequest<T>(endpoint, { ...options, method: "DELETE" }),

  // Health check helper
  checkHealth: async () => {
    return apiRequest<{ status: string; database: string; version: string; environment: string }>("/health", {
      skipAuth: true,
      timeoutMs: 10000,
    });
  },

  // Patients Clinical APIs
  patients: {
    getMe: () => apiRequest<any>("/patients/me"),
    updateMe: (data: any) => apiRequest<any>("/patients/me", { method: "PATCH", body: JSON.stringify(data) }),
    list: (params?: Record<string, any>) => {
      const q = new URLSearchParams(params).toString();
      return apiRequest<any>(`/patients${q ? `?${q}` : ""}`);
    },
    getDetail: (patientId: string) => apiRequest<any>(`/patients/${patientId}`),
    getTimeline: (patientId: string) => apiRequest<any>(`/patients/${patientId}/timeline`),
    create: (data: any) => apiRequest<any>("/patients", { method: "POST", body: JSON.stringify(data) }),
  },

  // Doctors Clinical APIs
  doctors: {
    getMe: () => apiRequest<any>("/doctors/me"),
    updateMe: (data: any) => apiRequest<any>("/doctors/me", { method: "PATCH", body: JSON.stringify(data) }),
    updateMeSchedule: (data: any) => apiRequest<any>("/doctors/me/schedule", { method: "PATCH", body: JSON.stringify(data) }),
    list: (params?: Record<string, any>) => {
      const q = new URLSearchParams(params).toString();
      return apiRequest<any>(`/doctors${q ? `?${q}` : ""}`);
    },
    getDetail: (doctorId: string) => apiRequest<any>(`/doctors/${doctorId}`),
    getAvailability: (doctorId: string, date: string) =>
      apiRequest<any>(`/doctors/${doctorId}/availability?date=${encodeURIComponent(date)}`),
    create: (data: any) => apiRequest<any>("/doctors", { method: "POST", body: JSON.stringify(data) }),
    update: (doctorId: string, data: any) => apiRequest<any>(`/doctors/${doctorId}`, { method: "PATCH", body: JSON.stringify(data) }),
  },

  // Staff Clinical APIs
  staff: {
    getDashboardOverview: () => apiRequest<any>("/staff/dashboard-overview"),
    getMe: () => apiRequest<any>("/staff/me"),
    updateMe: (data: any) => apiRequest<any>("/staff/me", { method: "PATCH", body: JSON.stringify(data) }),
    list: (params?: Record<string, any>) => {
      const q = new URLSearchParams(params).toString();
      return apiRequest<any>(`/staff${q ? `?${q}` : ""}`);
    },
    getDetail: (staffId: string) => apiRequest<any>(`/staff/${staffId}`),
    create: (data: any) => apiRequest<any>("/staff", { method: "POST", body: JSON.stringify(data) }),
    update: (staffId: string, data: any) => apiRequest<any>(`/staff/${staffId}`, { method: "PATCH", body: JSON.stringify(data) }),
  },

  // Departments Clinical APIs
  departments: {
    list: () => apiRequest<any>("/departments"),
    create: (data: any) => apiRequest<any>("/departments", { method: "POST", body: JSON.stringify(data) }),
    update: (departmentId: string, data: any) =>
      apiRequest<any>(`/departments/${departmentId}`, { method: "PATCH", body: JSON.stringify(data) }),
  },

  // Appointments Clinical APIs
  appointments: {
    book: (data: any) => apiRequest<any>("/appointments", { method: "POST", body: JSON.stringify(data) }),
    list: (params?: Record<string, any>) => {
      const q = new URLSearchParams(params).toString();
      return apiRequest<any>(`/appointments${q ? `?${q}` : ""}`);
    },
    getQueue: (params?: Record<string, any>) => {
      const q = new URLSearchParams(params).toString();
      return apiRequest<any>(`/appointments/queue${q ? `?${q}` : ""}`);
    },
    getDetail: (appointmentId: string) => apiRequest<any>(`/appointments/${appointmentId}`),
    confirm: (appointmentId: string) =>
      apiRequest<any>(`/appointments/${appointmentId}/confirm`, { method: "POST" }),
    checkIn: (appointmentId: string, data?: any) =>
      apiRequest<any>(`/appointments/${appointmentId}/check-in`, { method: "POST", body: JSON.stringify(data || {}) }),
    callPatient: (appointmentId: string) =>
      apiRequest<any>(`/appointments/${appointmentId}/call`, { method: "POST" }),
    complete: (appointmentId: string) =>
      apiRequest<any>(`/appointments/${appointmentId}/complete`, { method: "POST" }),
    updateStatus: (appointmentId: string, status: string) =>
      apiRequest<any>(`/appointments/${appointmentId}/status`, { method: "PATCH", body: JSON.stringify({ status }) }),
    cancel: (appointmentId: string, reason?: string) =>
      apiRequest<any>(`/appointments/${appointmentId}/cancel`, { method: "POST", body: JSON.stringify({ reason: reason || "User cancelled" }) }),
    reschedule: (appointmentId: string, data: any) =>
      apiRequest<any>(`/appointments/${appointmentId}/reschedule`, { method: "POST", body: JSON.stringify(data) }),
  },

  // Consultations Clinical APIs
  consultations: {
    start: (appointmentId: string) =>
      apiRequest<any>(`/consultations/start/${appointmentId}`, { method: "POST" }),
    list: (params?: Record<string, any>) => {
      const q = params ? new URLSearchParams(params).toString() : "";
      return apiRequest<any>(`/consultations${q ? `?${q}` : ""}`);
    },
    getDetail: (consultationId: string) => apiRequest<any>(`/consultations/${consultationId}`),
    getPatientContext: (patientId: string) =>
      apiRequest<any>(`/consultations/patient-context/${patientId}`),
    updateChiefComplaint: (consultationId: string, data: any) =>
      apiRequest<any>(`/consultations/${consultationId}/chief-complaint`, { method: "PATCH", body: JSON.stringify(data) }),
    updateSymptoms: (consultationId: string, data: any) =>
      apiRequest<any>(`/consultations/${consultationId}/symptoms`, { method: "PATCH", body: JSON.stringify(data) }),
    updateVitals: (consultationId: string, data: any) =>
      apiRequest<any>(`/consultations/${consultationId}/vitals`, { method: "PATCH", body: JSON.stringify(data) }),
    updateNotes: (consultationId: string, notes: string) =>
      apiRequest<any>(`/consultations/${consultationId}/clinical-notes`, { method: "PATCH", body: JSON.stringify({ notes }) }),
    updateClinicalNotes: (consultationId: string, data: { notes?: string; clinical_notes?: string; expected_version?: number }) =>
      apiRequest<any>(`/consultations/${consultationId}/clinical-notes`, { method: "PATCH", body: JSON.stringify(data) }),
    updateAssessment: (consultationId: string, data: any) =>
      apiRequest<any>(`/consultations/${consultationId}/assessment`, { method: "PATCH", body: JSON.stringify(data) }),
    updateDiagnoses: (consultationId: string, data: any) =>
      apiRequest<any>(`/consultations/${consultationId}/diagnoses`, { method: "PATCH", body: JSON.stringify(data) }),
    updateInstructions: (consultationId: string, doctorInstructions: string[] | string) =>
      apiRequest<any>(`/consultations/${consultationId}/instructions`, {
        method: "PATCH",
        body: JSON.stringify({ doctor_instructions: Array.isArray(doctorInstructions) ? doctorInstructions : [doctorInstructions] })
      }),
    updateCarePlan: (consultationId: string, data: { care_plan: string; follow_up_required?: boolean; follow_up_date?: string }) =>
      apiRequest<any>(`/consultations/${consultationId}/care-plan`, { method: "PATCH", body: JSON.stringify(data) }),
    linkAIAnalysis: (consultationId: string, analysisId: string) =>
      apiRequest<any>(`/consultations/${consultationId}/link-ai-analysis`, { method: "POST", body: JSON.stringify({ ai_analysis_id: analysisId }) }),
    linkMedicalRecord: (consultationId: string, recordId: string) =>
      apiRequest<any>(`/consultations/${consultationId}/link-medical-record`, { method: "POST", body: JSON.stringify({ record_id: recordId }) }),
    complete: (consultationId: string) =>
      apiRequest<any>(`/consultations/${consultationId}/complete`, { method: "POST" }),
    cancel: (consultationId: string, reason?: string) =>
      apiRequest<any>(`/consultations/${consultationId}/cancel`, { method: "POST", body: JSON.stringify({ reason: reason || "Doctor cancelled" }) }),
  },

  // Prescriptions Clinical APIs
  prescriptions: {
    create: (arg1: string | any, arg2?: any) => {
      if (typeof arg1 === "string") {
        return apiRequest<any>(`/prescriptions/consultation/${arg1}`, {
          method: "POST",
          body: JSON.stringify(arg2 || {}),
        });
      }
      const cId = arg1?.consultation_id;
      if (cId) {
        return apiRequest<any>(`/prescriptions/consultation/${cId}`, {
          method: "POST",
          body: JSON.stringify(arg1),
        });
      }
      return apiRequest<any>("/prescriptions", { method: "POST", body: JSON.stringify(arg1) });
    },
    cancel: (prescriptionId: string, data: { cancellation_reason?: string; reason?: string }) =>
      apiRequest<any>(`/prescriptions/${prescriptionId}/cancel`, { method: "POST", body: JSON.stringify(data) }),
    list: (params?: Record<string, any>) => {
      const q = new URLSearchParams(params).toString();
      return apiRequest<any>(`/prescriptions${q ? `?${q}` : ""}`);
    },
    getDetail: (prescriptionId: string) => apiRequest<any>(`/prescriptions/${prescriptionId}`),
    getByConsultation: (consultationId: string) => apiRequest<any>(`/prescriptions/consultation/${consultationId}`),
  },

  // Medical Records Clinical APIs
  medicalRecords: {
    upload: (formData: FormData) => apiRequest<any>("/medical-records", { method: "POST", body: formData }),
    create: (data: any) => apiRequest<any>("/medical-records", { method: "POST", body: JSON.stringify(data) }),
    list: (params?: Record<string, any>) => {
      const q = new URLSearchParams(params).toString();
      return apiRequest<any>(`/medical-records${q ? `?${q}` : ""}`);
    },
    getDetail: (recordId: string) => apiRequest<any>(`/medical-records/${recordId}`),
    update: (recordId: string, data: any) => apiRequest<any>(`/medical-records/${recordId}`, { method: "PATCH", body: JSON.stringify(data) }),
    archive: (recordId: string) => apiRequest<any>(`/medical-records/${recordId}/archive`, { method: "PATCH" }),
    delete: (recordId: string) => apiRequest<any>(`/medical-records/${recordId}`, { method: "DELETE" }),
    downloadUrl: (recordId: string) => {
      return `${getApiBaseUrl().replace(/\/+$/, "")}/medical-records/${recordId}/file`;
    },
    getFileBlob: (recordId: string) => apiBlobRequest(`/medical-records/${recordId}/file`),
  },

  // Notifications APIs
  notifications: {
    list: (params?: Record<string, any>) => {
      const q = new URLSearchParams(params).toString();
      return apiRequest<any>(`/notifications${q ? `?${q}` : ""}`);
    },
    getDetail: (id: string) => apiRequest<any>(`/notifications/${id}`),
    getUnreadCount: () => apiRequest<any>("/notifications/unread-count"),
    markRead: (id: string) => apiRequest<any>(`/notifications/${id}/read`, { method: "POST" }),
    markUnread: (id: string) => apiRequest<any>(`/notifications/${id}/unread`, { method: "POST" }),
    markAllRead: () => apiRequest<any>("/notifications/read-all", { method: "POST" }),
    delete: (id: string) => apiRequest<any>(`/notifications/${id}`, { method: "DELETE" }),
  },

  // Medical Documents APIs
  documents: {
    upload: (formData: FormData) => apiRequest<any>("/documents", { method: "POST", body: formData }),
    list: (params?: Record<string, any>) => {
      const q = new URLSearchParams(params).toString();
      return apiRequest<any>(`/documents${q ? `?${q}` : ""}`);
    },
    getDetail: (id: string) => apiRequest<any>(`/documents/${id}`),
    downloadUrl: (id: string) => {
      return `${getApiBaseUrl().replace(/\/+$/, "")}/documents/${id}/download`;
    },
    getFileBlob: (id: string) => apiBlobRequest(`/documents/${id}/download`),
    updateMetadata: (id: string, data: any) => apiRequest<any>(`/documents/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
    delete: (id: string) => apiRequest<any>(`/documents/${id}`, { method: "DELETE" }),
  },

  // Billing & Payments APIs
  billing: {
    list: (params?: Record<string, any>) => {
      const q = new URLSearchParams(params).toString();
      return apiRequest<any>(`/billing${q ? `?${q}` : ""}`);
    },
    getDetail: (id: string) => apiRequest<any>(`/billing/${id}`),
    create: (data: any) => apiRequest<any>("/billing", { method: "POST", body: JSON.stringify(data) }),
    createFromConsultation: (consultationId: string) => apiRequest<any>(`/billing/from-consultation/${consultationId}`, { method: "POST" }),
    issue: (id: string) => apiRequest<any>(`/billing/${id}/issue`, { method: "POST" }),
    addLineItem: (id: string, data: any) => apiRequest<any>(`/billing/${id}/line-items`, { method: "POST", body: JSON.stringify(data) }),
    recordPayment: (id: string, data: any) => apiRequest<any>(`/billing/${id}/payments`, { method: "POST", body: JSON.stringify(data) }),
    voidPayment: (id: string, paymentId: string, data: { reason: string }) =>
      apiRequest<any>(`/billing/${id}/payments/${paymentId}/void`, { method: "POST", body: JSON.stringify(data) }),
    cancel: (id: string, data?: { reason?: string }) =>
      apiRequest<any>(`/billing/${id}/cancel`, { method: "POST", body: JSON.stringify(data || {}) }),
    getReceipt: (id: string, paymentId?: string) => {
      const q = paymentId ? `?payment_id=${encodeURIComponent(paymentId)}` : "";
      return apiRequest<any>(`/billing/${id}/receipt${q}`);
    },
  },

  // Global Search API
  search: {
    query: (q: string, resourceTypes?: string[], limitPerResource = 10) => {
      const params = new URLSearchParams({ q, limit_per_resource: String(limitPerResource) });
      if (resourceTypes) {
        resourceTypes.forEach((rt) => params.append("resource_type", rt));
      }
      return apiRequest<any>(`/search?${params.toString()}`);
    },
  },

  // Audit Logs API
  auditLogs: {
    list: (params?: Record<string, any>) => {
      const q = new URLSearchParams(params).toString();
      return apiRequest<any>(`/audit-logs${q ? `?${q}` : ""}`);
    },
  },

  // Admin & Soft Delete APIs
  admin: {
    listDeleted: (collectionName: string, params?: Record<string, any>) => {
      const q = new URLSearchParams(params).toString();
      return apiRequest<any>(`/admin/deleted/${collectionName}${q ? `?${q}` : ""}`);
    },
    restore: (collectionName: string, resourceId: string) =>
      apiRequest<any>(`/admin/restore/${collectionName}/${resourceId}`, { method: "POST" }),
    purge: (collectionName: string, resourceId: string) =>
      apiRequest<any>(`/admin/permanent-delete/${collectionName}/${resourceId}`, { method: "DELETE" }),
    getOperationalSummary: () => apiRequest<any>("/admin/summary"),
    getDashboardOverview: () => apiRequest<any>("/admin/dashboard"),
    listUsers: (params?: Record<string, any>) => {
      const q = new URLSearchParams(params).toString();
      return apiRequest<any>(`/admin/users${q ? `?${q}` : ""}`);
    },
    getUser: (userId: string) => apiRequest<any>(`/admin/users/${userId}`),
    updateUserStatus: (userId: string, data: { account_status: string }) =>
      apiRequest<any>(`/admin/users/${userId}/status`, { method: "PATCH", body: JSON.stringify(data) }),
    reinviteUser: (userId: string) =>
      apiRequest<any>(`/admin/users/${userId}/reinvite`, { method: "POST" }),
    getSettings: () => apiRequest<any>("/admin/settings"),
    updateSettings: (data: any) =>
      apiRequest<any>("/admin/settings", { method: "PATCH", body: JSON.stringify(data) }),
    cancelAppointment: (id: string, data: { reason: string }) =>
      apiRequest<any>(`/admin/appointments/${id}/cancel`, { method: "PATCH", body: JSON.stringify(data) }),
    search: (q: string) => apiRequest<any>(`/admin/search?q=${encodeURIComponent(q)}`),
    getFinancialSummary: (params?: Record<string, any>) => {
      const q = new URLSearchParams(params).toString();
      return apiRequest<any>(`/admin/financial-summary${q ? `?${q}` : ""}`);
    },
    getRevenueByDepartment: () => apiRequest<any>("/admin/revenue-by-department"),
    getPaymentMethodMix: () => apiRequest<any>("/admin/payment-method-mix"),
    getAppointmentAnalytics: () => apiRequest<any>("/admin/appointment-analytics"),
    exportBillingCsv: () => apiRequest<any>("/admin/reports/csv"),
  },

  // Follow-ups APIs
  followUps: {
    list: (params?: Record<string, any>) => {
      const q = new URLSearchParams(params).toString();
      return apiRequest<any>(`/follow-ups${q ? `?${q}` : ""}`);
    },
    create: (data: any) => apiRequest<any>("/follow-ups", { method: "POST", body: JSON.stringify(data) }),
    getDetail: (id: string) => apiRequest<any>(`/follow-ups/${id}`),
    update: (id: string, data: any) => apiRequest<any>(`/follow-ups/${id}`, { method: "PUT", body: JSON.stringify(data) }),
    delete: (id: string) => apiRequest<any>(`/follow-ups/${id}`, { method: "DELETE" }),
  },

  // AI Clinical Decision Support APIs
  ai: {
    getHealth: () => apiRequest<any>("/ai/health", { skipAuth: true }),
    listModules: () => apiRequest<any[]>("/ai/modules", { skipAuth: true }),
    createAnalysis: (data: { medical_record_id?: string; document_id?: string; patient_id?: string; appointment_id?: string; analysis_type?: string; consultation_id?: string }) =>
      apiRequest<any>("/ai-analyses", { method: "POST", body: JSON.stringify(data) }),
    listAnalyses: (params?: Record<string, any>) => {
      const q = new URLSearchParams(params).toString();
      return apiRequest<any>(`/ai-analyses${q ? `?${q}` : ""}`);
    },
    getDetail: (analysisId: string) => apiRequest<any>(`/ai-analyses/${analysisId}`),
    review: (analysisId: string, data: { decision: string; clinical_interpretation: string; notes?: string; release_to_patient?: boolean }) =>
      apiRequest<any>(`/ai-analyses/${analysisId}/review`, { method: "POST", body: JSON.stringify(data) }),
    release: (analysisId: string) =>
      apiRequest<any>(`/ai-analyses/${analysisId}/release`, { method: "POST" }),
    getPatientReport: (analysisId: string) => apiRequest<any>(`/ai-analyses/${analysisId}/report`),
    getGradcamBlob: (analysisId: string) => apiBlobRequest(`/ai-analyses/${analysisId}/gradcam`),
    getOriginalImageBlob: (analysisId: string) => apiBlobRequest(`/ai-analyses/${analysisId}/image`),
    getGradcamUrl: (analysisId: string) => {
      return `${getApiBaseUrl().replace(/\/+$/, "")}/ai-analyses/${analysisId}/gradcam`;
    },
    getInsights: () => apiRequest<any>("/ai/analytics"),
    /**
     * POST /ai/infer — stateless direct-upload inference.
     * Sends a raw image file + analysis_type, returns prediction + base64 Grad-CAM.
     * Preserves patient context and uploader provenance.
     */
    directInfer: (
      imageFile: File,
      analysisType: string = "BRAIN_MRI",
      patientId?: string,
      documentId?: string
    ): Promise<{
      analysis_id?: string;
      module_id: string;
      display_name: string;
      architecture: string;
      model_version: string;
      predicted_class: string;
      confidence: number;
      probabilities: { label: string; probability: number }[];
      gradcam_available: boolean;
      gradcam_b64: string | null;
      disclaimer: string;
    }> => {
      const fd = new FormData();
      fd.append("image", imageFile);
      fd.append("analysis_type", analysisType);
      if (patientId) fd.append("patient_id", patientId);
      if (documentId) fd.append("document_id", documentId);
      return apiRequest("/ai/infer", { method: "POST", body: fd });
    },
  },

  // QR & Check-In Clinical APIs
  qr: {
    getPatientQr: () =>
      apiRequest<{ token: string; payload: string; created_at: string }>("/patients/me/qr"),
    getPatientQrImageBlob: async (): Promise<Blob> => {
      const baseUrl = getApiBaseUrl().replace(/\/+$/, "");
      const tokens = getStoredTokens();
      const headers: Record<string, string> = {};
      if (tokens?.accessToken) {
        headers["Authorization"] = `Bearer ${tokens.accessToken}`;
      }
      const res = await fetch(`${baseUrl}/patients/me/qr/image`, {
        headers,
        credentials: "include",
      });
      if (!res.ok) {
        throw new ApiError(res.status, "Failed to load QR image");
      }
      return res.blob();
    },
    regeneratePatientQr: () =>
      apiRequest<{ token: string; payload: string; created_at: string }>("/patients/me/qr/regenerate", {
        method: "POST",
      }),
    resolvePatientQr: (token: string) =>
      apiRequest<any>("/qr/resolve-patient", { method: "POST", body: JSON.stringify({ token }) }),
    getAppointmentQr: (appointmentId: string) =>
      apiRequest<{ token: string; payload: string; created_at: string }>(`/appointments/${appointmentId}/qr`),
    checkInAppointmentQr: (token: string) =>
      apiRequest<any>("/check-in/qr", { method: "POST", body: JSON.stringify({ token }) }),
  },
};


