import type { LucideIcon } from "lucide-react";
import { Bell, Brain, Calendar, Pill, CalendarClock, ReceiptText, Settings } from "lucide-react";

export type NotifCategory = "appointment" | "ai-report" | "prescription" | "follow-up" | "billing" | "system";

export type Notification = {
  id: string;
  category: NotifCategory;
  title: string;
  body: string;
  time: string;
  read: boolean;
  referenceId?: string;
  referenceType?: string;
};

export const NOTIF_ICON: Record<NotifCategory, LucideIcon> = {
  appointment: Calendar,
  "ai-report": Brain,
  prescription: Pill,
  "follow-up": CalendarClock,
  billing: ReceiptText,
  system: Settings,
};

export { Bell };
