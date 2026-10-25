import { t } from "@/i18n";
import { formatMoney, formatMonthDay, formatNumber } from "@/lib/format";

// What every alert carries, on the Today page, the Alerts page and in Ask answers.
export type AlertFacts = {
  kind: string;
  numbers: Record<string, unknown>;
  started_on: string;
  sentence: string; // the server's English sentence, used only for a kind this file doesn't know
  money_at_stake?: number; // absent for staff
};

function count(value: unknown): string {
  return formatNumber(Number(value ?? 0));
}

function pieces(value: unknown): string {
  return t.common.pieces(Number(value ?? 0), count(value));
}

// The alert in the person's language, from its own numbers, e.g. "Sold 40 in the 7 days to 18 Oct,
// usually 8 to 15." Owners and managers also get the money at stake: "About 1 200 DH of sales above usual."
export function alertSentence(alert: AlertFacts, currency: string): string {
  const n = alert.numbers;
  const since = formatMonthDay(alert.started_on);
  let sentence: string;
  switch (alert.kind) {
    case "sales_spike":
    case "sales_drop":
      sentence = t.alerts.sales(count(n.sold), formatMonthDay(String(n.week_end)), count(n.usual_low), count(n.usual_high));
      break;
    case "negative_stock":
      sentence = t.alerts.negativeStock(count(n.quantity), since);
      break;
    case "sold_at_zero":
      sentence = t.alerts.soldAtZero(pieces(n.sold), t.common.days(Number(n.days), count(n.days)), since);
      break;
    case "stock_frozen":
      sentence = t.alerts.stockFrozen(count(n.quantity), since, pieces(n.sold));
      break;
    default:
      return alert.sentence;
  }
  const money = t.alerts.money[alert.kind];
  return alert.money_at_stake === undefined || !money
    ? sentence
    : `${sentence} ${money(formatMoney(alert.money_at_stake, currency, true))}`;
}
