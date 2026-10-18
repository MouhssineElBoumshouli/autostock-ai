import { locale, t } from "@/i18n";

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

const relative = new Intl.RelativeTimeFormat(locale, { numeric: "auto" });
const dateOnly = new Intl.DateTimeFormat(locale, { dateStyle: "medium" });

// "just now", "5 minutes ago", "2 hours ago", "yesterday", then the date after a week.
export function formatTimeAgo(value: string, now: number = Date.now()): string {
  const seconds = Math.round((new Date(value).getTime() - now) / 1000);
  const abs = Math.abs(seconds);
  if (abs < 60) return t.time.justNow;
  if (abs < 3600) return relative.format(Math.round(seconds / 60), "minute");
  if (abs < 86400) return relative.format(Math.round(seconds / 3600), "hour");
  if (abs < 7 * 86400) return relative.format(Math.round(seconds / 86400), "day");
  return dateOnly.format(new Date(value));
}

// "Sara Benali" -> "SB", for small round avatars.
export function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((word) => word[0].toUpperCase())
    .join("");
}
