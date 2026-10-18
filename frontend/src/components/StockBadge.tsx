import { Badge } from "@/components/ui/badge";
import { t } from "@/i18n";

export type StockStatus = "healthy" | "low" | "out";

const variants = { healthy: "success", low: "warning", out: "destructive" } as const;

export function StockBadge({ status }: { status: StockStatus }) {
  return <Badge variant={variants[status]}>{t.stock[status]}</Badge>;
}
