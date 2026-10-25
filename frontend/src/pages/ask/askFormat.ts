import type { AskNumber } from "@/api/ask";
import { t } from "@/i18n";
import { formatDay, formatDayRange, formatMoney, formatNumber } from "@/lib/format";

// How one of the answer's real numbers is shown, by its unit. Money needs the shop's currency;
// staff never receive a money-unit number at all, so this is never asked to format one for them.
export function formatAskNumber(number: AskNumber, currency: string): string {
  switch (number.unit) {
    case "money":
      return formatMoney(number.value as number, currency);
    case "date":
      return formatDay(number.value as string);
    case "date_range":
      return formatDayRange(number.value as string);
    case "days":
      return t.common.days(number.value as number, formatNumber(number.value as number));
    case "alert_kind":
      return t.alerts.kinds[number.value as string] ?? String(number.value);
    case "percent":
      return `${number.value}%`;
    case "pieces":
    case "count":
      return formatNumber(number.value as number);
    case "text":
      return String(number.value);
  }
}
