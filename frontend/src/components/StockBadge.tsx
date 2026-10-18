import { Badge } from "@/components/ui/badge";
import { t } from "@/i18n";

export type StockStatus = "healthy" | "low" | "out" | "inactive";

const variants = { healthy: "success", low: "warning", out: "error", inactive: "neutral" } as const;

export function StockBadge({ status }: { status: StockStatus }) {
  return <Badge variant={variants[status]}>{t.stock[status]}</Badge>;
}
