import { locale } from "@/i18n";

const wholeNumber = new Intl.NumberFormat(locale, { maximumFractionDigits: 0 });

const dateTime = new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short" });

// Quantities are always shown as whole numbers with thousands separators: 3892 -> "3,892".
export function formatNumber(value: number): string {
  return wholeNumber.format(value);
}

// "2026-10-18T12:30:00Z" -> "Oct 18, 2026, 1:30 PM" in the viewer's time zone.
export function formatDateTime(value: string): string {
  return dateTime.format(new Date(value));
}
