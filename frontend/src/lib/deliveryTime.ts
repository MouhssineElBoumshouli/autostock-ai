import { t } from "@/i18n";
import { formatNumber } from "@/lib/format";

// Where a supplier's delivery time came from. Mirrors backend/app/ordering/delivery_time.py.
export type DeliverySource = "estimated" | "file" | "learned" | "owner";

export type DeliveryTime = { days: number; source: DeliverySource; learned_from: number };

const words = t.common.deliveryTime;

export function deliveriesText(count: number): string {
  return words.deliveries(count, formatNumber(count));
}

// "about 7 days (estimated)", "6 days (learned from 4 deliveries)", "12 days (from your file)", "5 days".
// `source` is null on order lines made before it was kept: just the days.
export function deliveryTimeText(days: number, source: DeliverySource | null, learnedFrom: number): string {
  const shown = t.common.days(days, formatNumber(days));
  if (source === "estimated") return words.estimated(shown);
  if (source === "learned") return words.learned(shown, deliveriesText(learnedFrom));
  if (source === "file") return words.fromFile(shown);
  return shown;
}
