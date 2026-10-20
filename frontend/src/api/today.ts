import { useQuery } from "@tanstack/react-query";

import { apiRequest } from "@/api/client";

export type AlertSummary = {
  id: string;
  kind: string;
  sentence: string;
  part_name: string;
  branch_name: string;
  raised_on: string;
};

export type ToOrderSummary = { lines: number; total_cost: number };

export type LateDelivery = {
  id: string;
  order_number: string;
  supplier_name: string;
  sent_at: string;
  days_late: number;
};

export type WeekPoint = { week_start: string; quantity: number };

export type TopPart = { part_id: string; sku: string; name: string; quantity: number };

export type WeeklySales = {
  this_week: number;
  normal: number;
  weeks: WeekPoint[];
  top_parts: TopPart[];
};

export type Today = {
  needs_action: AlertSummary[];
  needs_action_total: number;
  worth_a_look: AlertSummary[];
  worth_a_look_total: number;
  to_order: ToOrderSummary | null;
  late_deliveries: LateDelivery[];
  weekly_sales: WeeklySales | null;
};

export function useToday() {
  return useQuery({ queryKey: ["today"], queryFn: () => apiRequest<Today>("/api/today") });
}

// How many things need a person today: open "needs action" alerts, late deliveries, and (as one
// thing) having a pending order to review. "Worth a look" is informational, so it isn't counted.
export function thingsNeedingYou(data: Today): number {
  return data.needs_action_total + data.late_deliveries.length + (data.to_order && data.to_order.lines > 0 ? 1 : 0);
}
