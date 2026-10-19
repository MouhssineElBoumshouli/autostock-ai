import { Badge } from "@/components/ui/badge";
import { t } from "@/i18n";

export type StockStatus = "healthy" | "low" | "out" | "inactive" | "running_out";

const variants = {
  healthy: "success",
  low: "warning",
  out: "error",
  inactive: "neutral",
  running_out: "warning", // amber, like Low stock, but its own word: still above the minimum
} as const;

export function StockBadge({ status }: { status: StockStatus }) {
  return <Badge variant={variants[status]}>{t.stock[status]}</Badge>;
}
