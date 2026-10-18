import { locale } from "@/i18n";

const wholeNumber = new Intl.NumberFormat(locale, { maximumFractionDigits: 0 });

// Quantities are always shown as whole numbers with thousands separators: 3892 -> "3,892".
export function formatNumber(value: number): string {
  return wholeNumber.format(value);
}
