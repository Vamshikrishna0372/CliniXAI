import { Link } from "@tanstack/react-router";
import { Calendar, Clock, Stethoscope, ChevronRight } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { AppointmentBadge } from "./status-badge";
import { fmtDate, type Appointment } from "@/lib/mock/domain";
import { useClinix } from "@/lib/store/clinix-store";

export function AppointmentCard({ appointment, action }: { appointment: Appointment; action?: React.ReactNode }) {
  const { getDoctor } = useClinix();
  const doc = getDoctor(appointment.doctorId);
  return (
    <Card className="card-hover">
      <CardContent className="p-4 sm:p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <p className="truncate font-display text-base font-semibold text-foreground">{doc?.name}</p>
              <AppointmentBadge status={appointment.status} />
            </div>
            <p className="mt-0.5 truncate text-xs text-muted-foreground">
              {doc?.specialization} • {doc?.department}
            </p>
            <div className="mt-3 flex flex-wrap gap-x-3 gap-y-2 text-xs text-muted-foreground">
              <span className="flex items-center gap-1.5"><Calendar className="h-3.5 w-3.5" /> {fmtDate(appointment.date)}</span>
              <span className="flex items-center gap-1.5"><Clock className="h-3.5 w-3.5" /> {appointment.time}</span>
              <span className="flex items-center gap-1.5"><Stethoscope className="h-3.5 w-3.5" /> {appointment.id}</span>
              {appointment.token && <span className="rounded-md bg-primary/10 px-2 py-0.5 font-semibold text-primary">Token {appointment.token}</span>}
            </div>
          </div>
          {action ?? (
            <Button asChild variant="ghost" size="sm" className="shrink-0">
              <Link to="/app/appointments/$id" params={{ id: appointment.id }}>
                Details <ChevronRight className="ml-1 h-4 w-4" />
              </Link>
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
