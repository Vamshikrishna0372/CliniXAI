import { useState } from "react";
import { Link } from "@tanstack/react-router";
import { Clock, IndianRupee, GraduationCap, Calendar, Edit3, Settings } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/lib/auth-context";
import { apiClient } from "@/lib/api-client";
import { toast } from "sonner";
import type { Doctor } from "@/lib/mock/domain";

export function DoctorCard({ doctor }: { doctor: Doctor }) {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const isPatient = user?.role === "patient";

  const [editOpen, setEditOpen] = useState(false);
  const [availOpen, setAvailOpen] = useState(false);
  const [updating, setUpdating] = useState(false);

  const [editForm, setEditForm] = useState({
    specialization: doctor.specialization,
    qualification: doctor.qualification,
    experienceYears: String(doctor.experienceYears),
    consultationFee: String(doctor.consultationFee),
  });

  const handleEditSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setUpdating(true);
    try {
      await apiClient.doctors.update(doctor.id, {
        specialization: editForm.specialization,
        qualification: editForm.qualification,
        experience_years: parseInt(editForm.experienceYears, 10) || doctor.experienceYears,
        consultation_fee: parseFloat(editForm.consultationFee) || doctor.consultationFee,
      });
      toast.success("Doctor profile updated successfully!");
      setEditOpen(false);
      window.location.reload();
    } catch (err: any) {
      toast.error(err?.message || "Failed to update doctor profile");
    } finally {
      setUpdating(false);
    }
  };

  return (
    <Card className="card-hover relative flex flex-col justify-between">
      <CardContent className="p-4 sm:p-5 flex-1 flex flex-col justify-between space-y-4">
        <div className="space-y-3">
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-start gap-3 min-w-0">
              <Avatar className="h-12 w-12 shrink-0 ring-2 ring-primary/20">
                <AvatarFallback className="bg-primary/10 text-primary font-bold text-sm">
                  {doctor.photoInitial}
                </AvatarFallback>
              </Avatar>
              <div className="min-w-0 flex-1">
                <p className="truncate font-display text-base font-semibold text-foreground" title={doctor.name}>
                  {doctor.name}
                </p>
                <p className="truncate text-xs text-muted-foreground font-medium">{doctor.specialization}</p>
                <p className="mt-0.5 truncate text-xs text-muted-foreground">{doctor.department}</p>
              </div>
            </div>
            <Badge variant={doctor.status === "inactive" ? "secondary" : "default"} className="shrink-0 text-[10px] uppercase">
              {doctor.status || "active"}
            </Badge>
          </div>

          <div className="grid grid-cols-2 gap-2 text-xs text-muted-foreground rounded-lg bg-muted/40 p-2.5">
            <span className="flex items-center gap-1.5 truncate" title={doctor.qualification}>
              <GraduationCap className="h-3.5 w-3.5 shrink-0 text-primary" /> {doctor.qualification}
            </span>
            <span className="flex items-center gap-1.5 truncate">
              <Clock className="h-3.5 w-3.5 shrink-0 text-primary" /> {doctor.experienceYears} yrs exp
            </span>
            <span className="flex items-center gap-1.5 truncate font-medium text-foreground">
              <IndianRupee className="h-3.5 w-3.5 shrink-0 text-primary" /> ₹{doctor.consultationFee}
            </span>
            <span className="flex items-center gap-1.5 truncate text-emerald-600 font-medium">
              <Calendar className="h-3.5 w-3.5 shrink-0" /> {doctor.nextAvailable}
            </span>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="pt-2 border-t border-border flex flex-wrap items-center gap-1.5">
          <Button asChild size="sm" variant="outline" className="flex-1 text-xs">
            <Link to="/app/doctors/$id" params={{ id: doctor.id }}>View Profile</Link>
          </Button>

          {isAdmin ? (
            <>
              <Button size="sm" variant="secondary" className="text-xs" onClick={() => setEditOpen(true)}>
                <Edit3 className="mr-1 h-3.5 w-3.5" /> Edit
              </Button>
              <Button size="sm" variant="ghost" className="text-xs text-muted-foreground" onClick={() => setAvailOpen(true)}>
                <Settings className="mr-1 h-3.5 w-3.5" /> Schedule
              </Button>
              <Button asChild size="sm" variant="outline" className="text-xs">
                <Link to="/app/appointments">Appointments</Link>
              </Button>
            </>
          ) : isPatient ? (
            <Button asChild size="sm" className="flex-1 text-xs">
              <Link to="/app/book" search={{ doctorId: doctor.id, step: 1 }}>Book</Link>
            </Button>
          ) : (
            <Button asChild size="sm" variant="outline" className="text-xs">
              <Link to="/app/appointments">Appointments</Link>
            </Button>
          )}
        </div>
      </CardContent>

      {/* Edit Doctor Dialog */}
      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>Edit Doctor Profile — {doctor.name}</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleEditSubmit} className="space-y-4 py-2">
            <div className="space-y-1">
              <Label>Specialization</Label>
              <Input
                value={editForm.specialization}
                onChange={(e) => setEditForm({ ...editForm, specialization: e.target.value })}
                required
              />
            </div>
            <div className="space-y-1">
              <Label>Qualification</Label>
              <Input
                value={editForm.qualification}
                onChange={(e) => setEditForm({ ...editForm, qualification: e.target.value })}
                required
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label>Experience (Years)</Label>
                <Input
                  type="number"
                  value={editForm.experienceYears}
                  onChange={(e) => setEditForm({ ...editForm, experienceYears: e.target.value })}
                  required
                />
              </div>
              <div className="space-y-1">
                <Label>Consultation Fee (₹)</Label>
                <Input
                  type="number"
                  value={editForm.consultationFee}
                  onChange={(e) => setEditForm({ ...editForm, consultationFee: e.target.value })}
                  required
                />
              </div>
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setEditOpen(false)}>Cancel</Button>
              <Button type="submit" disabled={updating}>
                {updating ? "Saving..." : "Save Changes"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Manage Availability Dialog */}
      <Dialog open={availOpen} onOpenChange={setAvailOpen}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>Manage Availability — {doctor.name}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 py-2 text-sm text-muted-foreground">
            <p>Weekly Working Schedule:</p>
            <div className="rounded-md border p-3 space-y-1.5 text-xs">
              <p className="font-semibold text-foreground">Monday – Friday: 09:00 AM – 05:00 PM</p>
              <p>Saturday: 09:00 AM – 01:00 PM</p>
              <p>Slot Duration: 30 Minutes</p>
            </div>
            <p className="text-xs text-emerald-600 font-medium">Status: Active & Available for Appointments</p>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAvailOpen(false)}>Close</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
