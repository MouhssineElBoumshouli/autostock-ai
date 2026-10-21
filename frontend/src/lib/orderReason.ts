import type { OrderLine } from "@/api/orders";
import { t } from "@/i18n";
import { formatNumber } from "@/lib/format";

const words = t.orders.reasons;

// "Sells about 9 a week", or a month for slow sellers. Mirrors backend/app/ordering/reasons.py.
function sellingRate(expected: number, days: number): string {
  const weekly = days ? (expected * 7) / days : 0;
  if (weekly >= 1) return words.sellsPerWeek(formatNumber(Math.round(weekly)));
  const monthly = (weekly * 30) / 7;
  if (monthly >= 1) return words.sellsPerMonth(formatNumber(Math.round(monthly)));
  return words.sellsLessThanMonthly;
}

// Why this part and why this number, in the person's language, from the line's own numbers.
export function orderReason(line: OrderLine): string {
  const quantity = formatNumber(line.quantity);
  let reason: string;
  if (line.rule === "slow_out_of_stock") {
    reason = words.slowOutOfStock(formatNumber(line.sold_last_90_days), quantity);
  } else if (line.rule === "slow_skip") {
    reason = words.slowSkip;
  } else {
    reason = words.forecast({
      rate: sellingRate(line.expected, line.days_covered),
      deliveryDays: formatNumber(line.delivery_days),
      onHand: formatNumber(line.on_hand),
      onOrder: line.on_order ? formatNumber(line.on_order) : null,
      quantity,
      packSize: line.pack_size > 1 ? formatNumber(line.pack_size) : null,
      days: formatNumber(line.days_covered),
      cushion: formatNumber(Math.round(line.cushion)),
    });
  }
  return line.status === "cut_by_budget" ? `${reason} ${words.cutByBudget}` : reason;
}
