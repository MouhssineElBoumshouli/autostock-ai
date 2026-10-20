import type { AskFilters } from "@/api/ask";
import type { Choice } from "@/api/stock";
import { t } from "@/i18n";

// A small mirror of backend/app/ask/question.py's QUESTION_TYPES: which filters each question
// type takes, so the "I understood:" chips know which ones can be changed.
export const ASK_FILTERS: Record<string, readonly string[]> = {
  sales_of: ["part", "category", "branch", "period"],
  best_sellers: ["category", "branch", "period"],
  running_out: ["category", "branch"],
  what_to_order: ["category", "branch"],
  stock_of_part: ["part", "branch"],
  dead_stock: ["category", "branch"],
  open_alerts: ["part", "branch"],
  late_deliveries: [],
  forecast_of_part: ["part", "branch"],
  sales_vs_last: ["part", "category", "branch", "period"],
};

export const ASK_PERIODS = ["today", "yesterday", "this_week", "last_week", "this_month", "last_month", "this_year"] as const;
export type AskPeriod = (typeof ASK_PERIODS)[number];

// The plain name of a question type for its chip ("Stock", "Best sellers"). Falls back to the
// raw type so an answer never breaks if the server ever adds one this file hasn't caught up to.
export function typeLabel(questionType: string): string {
  return (t.ask.types as Record<string, string>)[questionType] ?? questionType;
}

type RelatedScreen = { to: string; labelKey: "stock" | "orders" | "alerts" };

function stockLink(params: URLSearchParams): string {
  const query = params.toString();
  return query ? `/stock?${query}` : "/stock";
}

// Where a "open the related screen" button should go, reusing each screen's own filters.
// Branches are matched by name since that's what the shop's answer carries, not an id.
export function relatedScreen(questionType: string, filters: AskFilters, branches: Choice[]): RelatedScreen | null {
  const branchId = filters.branch ? branches.find((branch) => branch.name === filters.branch)?.id : undefined;
  const stockParams = new URLSearchParams();
  if (filters.part) stockParams.set("search", filters.part);
  if (filters.category) stockParams.set("category", filters.category);
  if (branchId) stockParams.set("branch", branchId);

  switch (questionType) {
    case "sales_of":
    case "best_sellers":
    case "stock_of_part":
    case "sales_vs_last":
    case "forecast_of_part":
      return { to: stockLink(stockParams), labelKey: "stock" };
    case "dead_stock":
      stockParams.set("status", "dead");
      return { to: stockLink(stockParams), labelKey: "stock" };
    case "running_out":
      stockParams.set("running_out", "true");
      return { to: stockLink(stockParams), labelKey: "stock" };
    case "what_to_order":
    case "late_deliveries":
      return { to: "/orders", labelKey: "orders" };
    case "open_alerts":
      return { to: "/alerts", labelKey: "alerts" };
    default:
      return null;
  }
}
