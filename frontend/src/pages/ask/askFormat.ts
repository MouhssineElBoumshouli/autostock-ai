import type { AskNumber } from "@/api/ask";
import { t } from "@/i18n";
import { formatDay, formatMoney, formatNumber } from "@/lib/format";

// How one of the answer's real numbers is shown, by its unit. Money needs the shop's currency;
// staff never receive a money-unit number at all, so this is never asked to format one for them.
export function formatAskNumber(number: AskNumber, currency: string): string {
  switch (number.unit) {
    case "money":
      return formatMoney(number.value as number, currency);
    case "date":
      return formatDay(number.value as string);
    case "days":
      return t.ask.days(number.value as number);
    case "percent":
      return `${number.value}%`;
    case "pieces":
    case "count":
      return formatNumber(number.value as number);
    case "text":
      return String(number.value);
  }
}
