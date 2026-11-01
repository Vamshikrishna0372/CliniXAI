import { useState, useEffect, useRef, useCallback } from "react";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { useAuth } from "@/lib/auth-context";
import { getApiBaseUrl } from "@/lib/api-client";
import { useNavigate } from "@tanstack/react-router";

declare global {
  interface Window {
    google?: any;
    _googleGisScriptLoaded?: boolean;
  }
}

function isMobileDevice(): boolean {
  if (typeof window === "undefined" || typeof navigator === "undefined") return false;
  const ua = navigator.userAgent || "";
  const isMobileUA = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini|Mobile|mobile/i.test(ua);
  const isTouch = "ontouchstart" in window || navigator.maxTouchPoints > 0;
  const isSmallScreen = window.innerWidth <= 768;
  return isMobileUA || (isSmallScreen && isTouch);
}

export function GoogleButton({
  label = "Continue with Google",
  onDone,
}: {
  label?: string;
  onDone?: () => void;
}) {
  const navigate = useNavigate();
  const { signInWithGoogle } = useAuth();
  const [isMobile, setIsMobile] = useState<boolean>(false);
  const [loading, setLoading] = useState(false);
  const [gisReady, setGisReady] = useState(false);
  const googleBtnContainerRef = useRef<HTMLDivElement>(null);
  const isHoveredRef = useRef(false);
  const isAuthenticatingRef = useRef(false);
  const safetyTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const focusTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const googleClientId =
    (import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined)?.trim() ||
    "324988442926-buco01m14qgqijkgeabg9lkbvrlna40i.apps.googleusercontent.com";

  // Check device type on client mount
  useEffect(() => {
    setIsMobile(isMobileDevice());
  }, []);

  const handleCredentialResponse = useCallback(
    async (response: { credential?: string }) => {
      if (!response.credential) {
        toast.error("Google authentication failed: no credential received.");
        setLoading(false);
        isAuthenticatingRef.current = false;
        return;
      }
      isAuthenticatingRef.current = true;
      setLoading(true);
      try {
        const user = await signInWithGoogle(response.credential);
        toast.success(`Welcome, ${user.fullName || user.firstName}!`);
        onDone?.();
        navigate({ to: "/app" });
      } catch (err: any) {
        const msg = err?.message || "Google sign-in failed. Please try again.";
        toast.error(msg);
        setLoading(false);
        isAuthenticatingRef.current = false;
      }
    },
    [signInWithGoogle, onDone, navigate]
  );

  const initiateOAuthRedirect = useCallback(() => {
    setLoading(true);
    isAuthenticatingRef.current = true;
    try {
      const isLocal =
        typeof window !== "undefined" &&
        (window.location.hostname === "localhost" ||
          window.location.hostname === "127.0.0.1");
      const redirectUri = isLocal
        ? "http://localhost:8000/api/v1/auth/google/callback"
        : "https://clinixai-2qfy.onrender.com/api/v1/auth/google/callback";

      // Non-blocking background wake-up ping to backend
      const apiBase = getApiBaseUrl();
      try {
        fetch(`${apiBase}/health`, { mode: "no-cors" }).catch(() => {});
      } catch {}

      const params = new URLSearchParams({
        client_id: googleClientId,
        redirect_uri: redirectUri,
        response_type: "code",
        scope: "openid email profile",
        access_type: "offline",
        prompt: "select_account",
        state: `clinixai_oauth_${Date.now()}`,
      });

      window.location.assign(`https://accounts.google.com/o/oauth2/v2/auth?${params.toString()}`);
    } catch {
      setLoading(false);
      isAuthenticatingRef.current = false;
      toast.error("Unable to initiate Google sign-in redirect.");
    }
  }, [googleClientId]);

  const handleCustomButtonClick = () => {
    if (loading) return;
    setLoading(true);
    isAuthenticatingRef.current = true;
    initiateOAuthRedirect();
  };

  // Listen for window blur/focus on desktop to trigger loading when Google popup opens,
  // and safely restore idle state if the popup is closed or cancelled.
  useEffect(() => {
    if (isMobile) return;

    const handleWindowBlur = () => {
      if (isHoveredRef.current && !loading) {
        setLoading(true);
        if (safetyTimeoutRef.current) clearTimeout(safetyTimeoutRef.current);
        safetyTimeoutRef.current = setTimeout(() => {
          if (!isAuthenticatingRef.current) {
            setLoading(false);
          }
        }, 45000);
      }
    };

    const handleWindowFocus = () => {
      if (focusTimeoutRef.current) clearTimeout(focusTimeoutRef.current);
      focusTimeoutRef.current = setTimeout(() => {
        if (!isAuthenticatingRef.current) {
          setLoading(false);
        }
      }, 1500);
    };

    window.addEventListener("blur", handleWindowBlur);
    window.addEventListener("focus", handleWindowFocus);

    return () => {
      window.removeEventListener("blur", handleWindowBlur);
      window.removeEventListener("focus", handleWindowFocus);
      if (safetyTimeoutRef.current) clearTimeout(safetyTimeoutRef.current);
      if (focusTimeoutRef.current) clearTimeout(focusTimeoutRef.current);
    };
  }, [isMobile, loading]);

  useEffect(() => {
    // On mobile devices, do not initialize GIS popup iframe to prevent accounts.google.com/gsi/transform blank page
    if (isMobile) {
      setGisReady(false);
      return;
    }

    let isMounted = true;

    const initGis = () => {
      if (!isMounted || !window.google?.accounts?.id) return;
      try {
        window.google.accounts.id.initialize({
          client_id: googleClientId,
          callback: handleCredentialResponse,
          auto_select: false,
          cancel_on_tap_outside: true,
        });

        if (googleBtnContainerRef.current) {
          googleBtnContainerRef.current.innerHTML = "";
          const containerWidth = googleBtnContainerRef.current.offsetWidth || 380;
          const validWidth = Math.min(400, Math.max(200, Math.floor(containerWidth)));

          window.google.accounts.id.renderButton(googleBtnContainerRef.current, {
            type: "standard",
            theme: "outline",
            size: "large",
            text: "continue_with",
            shape: "rectangular",
            logo_alignment: "left",
            width: String(validWidth),
          });
        }
        setGisReady(true);
      } catch (err) {
        setGisReady(false);
      }
    };

    if (window.google?.accounts?.id) {
      initGis();
      return () => {
        isMounted = false;
      };
    }

    const existingScript = document.getElementById("google-gis-client");
    if (!existingScript) {
      const script = document.createElement("script");
      script.id = "google-gis-client";
      script.src = "https://accounts.google.com/gsi/client";
      script.async = true;
      script.defer = true;
      script.onload = () => {
        window._googleGisScriptLoaded = true;
        initGis();
      };
      script.onerror = () => {
        setGisReady(false);
      };
      document.head.appendChild(script);
    } else {
      existingScript.addEventListener("load", initGis);
    }

    return () => {
      isMounted = false;
    };
  }, [isMobile, googleClientId, handleCredentialResponse]);

  return (
    <div className="w-full relative min-h-[44px]">
      {/* Official GIS container rendered only for Desktop */}
      {!isMobile && (
        <div
          ref={googleBtnContainerRef}
          onPointerEnter={() => {
            isHoveredRef.current = true;
          }}
          onPointerLeave={() => {
            isHoveredRef.current = false;
          }}
          onPointerDown={() => {
            isHoveredRef.current = true;
          }}
          className={`w-full flex justify-center transition-opacity duration-150 ${
            gisReady
              ? loading
                ? "opacity-0 pointer-events-none absolute inset-0 -z-10"
                : "opacity-100"
              : "hidden"
          }`}
          style={{ minHeight: "44px" }}
        />
      )}

      {/* Immediate visible loading state replacing button during authentication */}
      {loading && (
        <Button
          type="button"
          variant="outline"
          disabled
          aria-busy="true"
          className="h-11 w-full gap-3 border-border bg-muted/40 cursor-wait text-sm font-medium"
        >
          <Loader2 className="h-4 w-4 animate-spin text-primary shrink-0" />
          <span>Signing in with Google...</span>
        </Button>
      )}

      {/* Mobile button and desktop fallback button matching CliniXAI theme */}
      {(isMobile || !gisReady) && !loading && (
        <Button
          type="button"
          variant="outline"
          className="h-11 w-full gap-3 border-border hover:bg-muted/40 transition-colors"
          onClick={handleCustomButtonClick}
          disabled={loading}
          aria-label={label}
        >
          <svg className="h-4 w-4 shrink-0" viewBox="0 0 48 48" aria-hidden>
            <path
              fill="#FFC107"
              d="M43.6 20.5H42V20H24v8h11.3C33.7 32.9 29.3 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.9 1.2 8 3.1l5.7-5.7C34.5 6.1 29.5 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.2-.1-2.3-.4-3.5z"
            />
            <path
              fill="#FF3D00"
              d="m6.3 14.7 6.6 4.8C14.7 16 19 13 24 13c3.1 0 5.9 1.2 8 3.1l5.7-5.7C34.5 7.1 29.5 5 24 5 16.3 5 9.7 9 6.3 14.7z"
            />
            <path
              fill="#4CAF50"
              d="M24 44c5.3 0 10.1-2 13.7-5.3l-6.3-5.2C29.3 35.1 26.8 36 24 36c-5.3 0-9.7-3.1-11.3-7.5l-6.5 5C9.5 39.9 16.2 44 24 44z"
            />
            <path
              fill="#1976D2"
              d="M43.6 20.5H42V20H24v8h11.3c-.8 2.3-2.3 4.2-4.2 5.5l6.3 5.2C41.4 35.5 44 30.2 44 24c0-1.2-.1-2.3-.4-3.5z"
            />
          </svg>
          <span>{label}</span>
        </Button>
      )}
    </div>
  );
}
