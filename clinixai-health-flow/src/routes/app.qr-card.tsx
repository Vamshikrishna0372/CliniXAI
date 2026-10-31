import { createFileRoute, useNavigate, Link } from "@tanstack/react-router";
import { useCallback, useEffect, useState } from "react";
import {
  Download,
  Maximize2,
  Printer,
  RefreshCw,
  ShieldCheck,
  AlertTriangle,
  RotateCcw,
  UserCheck,
  Calendar,
  Phone,
  Heart,
  QrCode,
} from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/app-shell/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { BrandMark } from "@/components/brand-mark";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ErrorState, EmptyState } from "@/components/dashboard/states";
import { useAuth } from "@/lib/auth-context";
import { apiClient, ApiError } from "@/lib/api-client";

export const Route = createFileRoute("/app/qr-card")({
  head: () => ({
    meta: [
      { title: "QR Health Card — CliniXAI" },
      { name: "robots", content: "noindex" },
    ],
  }),
  component: QRCardPage,
  errorComponent: QRCardRouteError,
});

function QRCardRouteError({ error, reset }: { error: any; reset: () => void }) {
  return (
    <div className="space-y-6">
      <PageHeader
        title="QR Health Card"
        description="Show this at the CliniXAI reception for faster check-in."
      />
      <div className="mx-auto max-w-md">
        <ErrorState
          title="Failed to load QR Health Card"
          description={error?.message || "An unexpected error occurred while rendering your health card."}
          onRetry={reset}
        />
      </div>
    </div>
  );
}

interface PatientProfile {
  patient_id: string;
  user_id?: string;
  first_name?: string;
  last_name?: string;
  full_name?: string;
  email?: string;
  phone?: string;
  date_of_birth?: string;
  gender?: string;
  blood_group?: string;
  emergency_contact?: {
    name?: string;
    relationship?: string;
    phone?: string;
  };
}

interface QRData {
  token: string;
  payload: string;
  created_at: string;
}

function QRCardPage() {
  const { user, hydrated, isAuthenticated } = useAuth();
  const navigate = useNavigate();

  const [loading, setLoading] = useState(true);
  const [rotating, setRotating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [patient, setPatient] = useState<PatientProfile | null>(null);
  const [qrData, setQrData] = useState<QRData | null>(null);
  const [qrImageUrl, setQrImageUrl] = useState<string | null>(null);
  const [fullscreenOpen, setFullscreenOpen] = useState(false);

  const fetchHealthCard = useCallback(async () => {
    if (!isAuthenticated || !user) return;
    setLoading(true);
    setError(null);
    setNotFound(false);

    try {
      // 1. Authoritative Patient Self Profile from MongoDB
      const patRes = await apiClient.patients.getMe();
      const patientData: PatientProfile = patRes?.data || patRes;

      if (!patientData || !patientData.patient_id) {
        setNotFound(true);
        setLoading(false);
        return;
      }

      setPatient(patientData);

      // 2. Authoritative Patient Health QR Token
      const tokenRes = await apiClient.qr.getPatientQr();
      setQrData(tokenRes);

      // 3. Authoritative Patient Health QR PNG Image
      try {
        const blob = await apiClient.qr.getPatientQrImageBlob();
        const objectUrl = URL.createObjectURL(blob);
        setQrImageUrl((prev) => {
          if (prev) URL.revokeObjectURL(prev);
          return objectUrl;
        });
      } catch (imgErr) {
        console.warn("Could not load backend QR image:", imgErr);
      }
    } catch (err: any) {
      if (err instanceof ApiError) {
        if (err.status === 404 || err.status === 403) {
          setNotFound(true);
        } else {
          setError(err.message || "Failed to load health card from server.");
        }
      } else {
        setError(err?.message || "Failed to load health card.");
      }
    } finally {
      setLoading(false);
    }
  }, [isAuthenticated, user]);

  useEffect(() => {
    if (hydrated && !isAuthenticated) {
      navigate({ to: "/auth/login" });
      return;
    }
    if (hydrated && isAuthenticated) {
      fetchHealthCard();
    }
  }, [hydrated, isAuthenticated, navigate, fetchHealthCard]);

  // Clean up object URL when component unmounts or changes
  useEffect(() => {
    return () => {
      if (qrImageUrl) {
        URL.revokeObjectURL(qrImageUrl);
      }
    };
  }, [qrImageUrl]);

  const handleRegenerate = async () => {
    if (rotating) return;
    setRotating(true);
    try {
      const rotated = await apiClient.qr.regeneratePatientQr();
      setQrData(rotated);
      const blob = await apiClient.qr.getPatientQrImageBlob();
      const objectUrl = URL.createObjectURL(blob);
      setQrImageUrl((prev) => {
        if (prev) URL.revokeObjectURL(prev);
        return objectUrl;
      });
      toast.success("Health Card QR rotated and refreshed successfully.");
    } catch (err: any) {
      toast.error(err?.message || "Failed to rotate QR code. Please try again.");
    } finally {
      setRotating(false);
    }
  };

  const handleDownload = () => {
    if (!qrImageUrl) {
      toast.error("QR image is still loading.");
      return;
    }
    const a = document.createElement("a");
    a.href = qrImageUrl;
    a.download = `ClinixAI-HealthCard-${patient?.patient_id || "patient"}.png`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    toast.success("Health Card QR downloaded.");
  };

  // State: Loading skeleton
  if (!hydrated || loading) {
    return (
      <div className="space-y-6">
        <PageHeader
          title="QR Health Card"
          description="Show this at the CliniXAI reception for faster check-in."
        />
        <div className="mx-auto max-w-md">
          <Card className="overflow-hidden border border-border shadow-sm">
            <div className="gradient-primary p-5 text-primary-foreground">
              <div className="flex items-center justify-between">
                <BrandMark size="sm" labelClassName="text-primary-foreground" />
                <span className="rounded-full bg-white/20 px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide">
                  Health Card
                </span>
              </div>
            </div>
            <CardContent className="p-6 space-y-4">
              <div className="flex items-start justify-between">
                <div className="space-y-1.5">
                  <Skeleton className="h-6 w-36" />
                  <Skeleton className="h-4 w-24" />
                </div>
                <Skeleton className="h-7 w-12 rounded-lg" />
              </div>
              <div className="flex justify-center py-4">
                <Skeleton className="h-52 w-52 rounded-xl" />
              </div>
              <Skeleton className="h-14 w-full rounded-lg" />
              <Skeleton className="h-4 w-3/4 mx-auto" />
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  // State: Permanent missing profile (e.g. Doctor or Staff account without patient profile)
  if (notFound) {
    return (
      <div className="space-y-6">
        <PageHeader
          title="QR Health Card"
          description="Show this at the CliniXAI reception for faster check-in."
        />
        <div className="mx-auto max-w-md">
          <EmptyState
            icon={UserCheck}
            title="No Patient Profile Linked"
            description={`No patient record is associated with your account (${user?.email || "current user"}). The QR Health Card is reserved for registered patients.`}
            action={
              <div className="flex flex-wrap justify-center gap-2">
                <Button asChild variant="outline">
                  <Link to="/app">Back to Dashboard</Link>
                </Button>
                {user?.role === "patient" && (
                  <Button asChild>
                    <Link to="/app/patient-registration">Register Patient Profile</Link>
                  </Button>
                )}
              </div>
            }
          />
        </div>
      </div>
    );
  }

  // State: API / Network Request Error with meaningful recovery
  if (error || !patient) {
    return (
      <div className="space-y-6">
        <PageHeader
          title="QR Health Card"
          description="Show this at the CliniXAI reception for faster check-in."
        />
        <div className="mx-auto max-w-md">
          <ErrorState
            title="Unable to load your health card"
            description={error || "Could not retrieve authoritative patient card data. Please try again."}
            onRetry={fetchHealthCard}
          />
          <div className="mt-4 text-center">
            <Button asChild variant="ghost" size="sm">
              <Link to="/app">Return to Dashboard</Link>
            </Button>
          </div>
        </div>
      </div>
    );
  }

  const patientName =
    `${patient.first_name || ""} ${patient.last_name || ""}`.trim() ||
    patient.full_name ||
    "Patient";

  return (
    <div className="space-y-6">
      <PageHeader
        title="QR Health Card"
        description="Show this at the CliniXAI reception for faster check-in."
      />

      <div className="mx-auto max-w-md">
        <Card className="overflow-hidden border border-border/80 shadow-md transition-shadow hover:shadow-lg">
          {/* Card Header Banner */}
          <div className="gradient-primary p-5 text-primary-foreground">
            <div className="flex items-center justify-between">
              <BrandMark size="sm" labelClassName="text-primary-foreground" />
              <div className="flex items-center gap-1.5 rounded-full bg-white/20 px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide">
                <ShieldCheck className="h-3 w-3" />
                <span>Verified Health Card</span>
              </div>
            </div>
          </div>

          <CardContent className="p-6 space-y-4">
            {/* Patient Header Details */}
            <div className="flex items-start justify-between gap-3 border-b border-border/60 pb-3">
              <div className="min-w-0">
                <p className="font-display text-lg font-bold text-foreground truncate">
                  {patientName}
                </p>
                <p className="text-xs font-mono font-medium text-muted-foreground">
                  {patient.patient_id}
                </p>
              </div>
              <div className="flex flex-col items-end gap-1">
                <span className="rounded-lg bg-error/10 px-2.5 py-1 text-xs font-bold text-error">
                  {patient.blood_group || "N/A"}
                </span>
                {patient.gender && (
                  <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
                    {patient.gender}
                  </span>
                )}
              </div>
            </div>

            {/* QR Code Presentation */}
            <div className="flex flex-col items-center justify-center py-2">
              <div className="relative rounded-2xl border-2 border-border/80 bg-white p-3 shadow-inner">
                {qrImageUrl ? (
                  <img
                    src={qrImageUrl}
                    alt={`QR Code for ${patientName}`}
                    className="h-52 w-52 rounded-xl object-contain"
                  />
                ) : (
                  <div className="flex h-52 w-52 flex-col items-center justify-center gap-2 bg-muted/40 text-muted-foreground">
                    <QrCode className="h-12 w-12 animate-pulse" />
                    <span className="text-xs">Generating QR...</span>
                  </div>
                )}
              </div>

              {qrData?.token && (
                <p className="mt-2 text-center font-mono text-[11px] text-muted-foreground">
                  Token: {qrData.token.slice(0, 16)}...
                </p>
              )}
            </div>

            {/* Emergency Contact Section */}
            <div className="rounded-xl border border-border/70 bg-muted/30 p-3.5 text-xs space-y-1">
              <div className="flex items-center gap-1.5 font-semibold text-foreground">
                <Heart className="h-3.5 w-3.5 text-error" />
                <span>In Case of Emergency</span>
              </div>
              {patient.emergency_contact?.name ? (
                <p className="text-muted-foreground">
                  <span className="font-medium text-foreground">
                    {patient.emergency_contact.name}
                  </span>{" "}
                  ({patient.emergency_contact.relationship || "Contact"})
                  {patient.emergency_contact.phone ? ` — ${patient.emergency_contact.phone}` : " — contact via reception"}
                </p>
              ) : (
                <p className="text-muted-foreground italic">
                  No emergency contact registered — contact hospital reception.
                </p>
              )}
            </div>

            {/* Privacy Safeguard Note */}
            <p className="text-center text-[11px] text-muted-foreground">
              Encrypted token check-in only. Clinical history is protected and requires doctor authorization.
            </p>
          </CardContent>
        </Card>

        {/* Action Controls */}
        <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setFullscreenOpen(true)}
            className="w-full"
          >
            <Maximize2 className="mr-1 h-3.5 w-3.5" /> Fullscreen
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={handleDownload}
            disabled={!qrImageUrl}
            className="w-full"
          >
            <Download className="mr-1 h-3.5 w-3.5" /> Download
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={() => window.print()}
            className="w-full"
          >
            <Printer className="mr-1 h-3.5 w-3.5" /> Print
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={handleRegenerate}
            disabled={rotating}
            className="w-full"
          >
            <RefreshCw className={`mr-1 h-3.5 w-3.5 ${rotating ? "animate-spin" : ""}`} />
            {rotating ? "Rotating..." : "Rotate QR"}
          </Button>
        </div>
      </div>

      {/* Fullscreen QR Modal */}
      <Dialog open={fullscreenOpen} onOpenChange={setFullscreenOpen}>
        <DialogContent className="sm:max-w-md text-center">
          <DialogHeader>
            <DialogTitle className="text-center font-display text-lg">
              Patient Check-In QR Code
            </DialogTitle>
          </DialogHeader>
          <div className="py-4 flex flex-col items-center">
            {qrImageUrl ? (
              <img
                src={qrImageUrl}
                alt={`QR Code for ${patientName}`}
                className="h-72 w-72 rounded-2xl border-2 border-border bg-white p-3 shadow-md object-contain"
              />
            ) : null}
            <p className="mt-3 font-display text-base font-bold text-foreground">
              {patientName}
            </p>
            <p className="text-xs font-mono text-muted-foreground">{patient.patient_id}</p>
            <p className="mt-2 text-xs text-muted-foreground max-w-xs">
              Present this code at the kiosk scanner or front-desk check-in terminal.
            </p>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
