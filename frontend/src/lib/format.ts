import { language, locale, t } from "@/i18n";

// Shops are in Morocco: times are shown in Moroccan time, whatever the computer's own clock says.
// This used to ask Intl.DateTimeFormat for "Africa/Casablanca" directly, trusting the browser's
// (or the shop PC's) own copy of the time zone database. Morocco moved to permanent UTC+0 on 20
// Sep 2026, and a computer whose copy is older still thinks it's UTC+1 -- every time on the page
// would read an hour ahead until that computer happens to update itself. So instead the server
// says what the shop's offset from UTC is right now (GET /api/shop-time, asked once at startup;
// see main.tsx), this file shifts every moment by that many minutes, and every formatter below
// is told the result is already "UTC" -- which every browser, old or new, always gets right.
let shopOffsetMinutes = 0; // correct already for Morocco since 20 Sep 2026, until the real answer arrives
export function setShopUtcOffsetMinutes(minutes: number): void {
  shopOffsetMinutes = minutes;
}

function shopMoment(value: string | number | Date): Date {
  const date = value instanceof Date ? value : new Date(value);
  return new Date(date.getTime() + shopOffsetMinutes * 60_000);
}

const timeZone = "UTC"; // every Date given to a formatter below has already been shifted by shopMoment()
// French and Arabic write numbers and dates the same way: "1 250,00", "21/10/2026".
const numberLocale = language === "en" ? "en-US" : "fr-FR";

const wholeNumber = new Intl.NumberFormat(numberLocale, { maximumFractionDigits: 0 });

const dateTime =
  language === "en"
    ? new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short", timeZone })
    : new Intl.DateTimeFormat(numberLocale, { dateStyle: "short", timeStyle: "short", timeZone });

// Arabic fonts have no narrow space, so "88 200" would show as "88200": Arabic gets a normal fixed space.
function spaced(text: string): string {
  return language === "ar" ? text.replace(/ /g, " ") : text;
}

// A shop's own words (a part, a supplier, a branch) inside a sentence keep their own direction:
// "Brake pads - Dacia Logan" stays left to right inside an Arabic sentence.
export function isolate(text: string): string {
  return `⁨${text}⁩`;
}

// Arabic text runs right to left: an isolate keeps "1 250,00 DH" or "21/10/2026" in one piece inside it.
function keepTogether(text: string): string {
  return language === "ar" ? `⁦${text}⁩` : text;
}

// Quantities are always shown as whole numbers with thousands separators: 3892 -> "3,892" or "3 892".
export function formatNumber(value: number): string {
  return keepTogether(spaced(wholeNumber.format(value)));
}

// "2026-10-18T12:30:00Z" -> "Oct 18, 2026, 1:30 PM" / "18/10/2026 13:30", in Moroccan time.
export function formatDateTime(value: string): string {
  return keepTogether(dateTime.format(shopMoment(value)));
}

const relative = new Intl.RelativeTimeFormat(locale, { numeric: "auto" });

// Calendar days ("2026-03-15") have no time of day: read and shown as the same day everywhere.
function calendarDay(value: string): Date {
  return new Date(`${value.slice(0, 10)}T00:00:00Z`);
}

function dateFormat(zone: string): Intl.DateTimeFormat {
  return language === "en"
    ? new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeZone: zone })
    : new Intl.DateTimeFormat(numberLocale, { day: "2-digit", month: "2-digit", year: "numeric", timeZone: zone });
}

const dateOnly = dateFormat("UTC"); // calendar days, see calendarDay
const dateOfMoment = dateFormat(timeZone);

// "just now", "5 minutes ago", "2 hours ago", "yesterday", then the date after a week.
export function formatTimeAgo(value: string, now: number = Date.now()): string {
  const seconds = Math.round((new Date(value).getTime() - now) / 1000);
  const abs = Math.abs(seconds);
  if (abs < 60) return t.time.justNow;
  if (abs < 3600) return relative.format(Math.round(seconds / 60), "minute");
  if (abs < 86400) return relative.format(Math.round(seconds / 3600), "hour");
  if (abs < 7 * 86400) return relative.format(Math.round(seconds / 86400), "day");
  return keepTogether(dateOfMoment.format(shopMoment(value)));
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

const moneyFormats = new Map<string, Intl.NumberFormat>();

function moneyFormat(currency: string, whole: boolean): Intl.NumberFormat {
  const key = `${currency}-${whole}`;
  if (!moneyFormats.has(key)) {
    const digits = whole ? 0 : 2;
    const options: Intl.NumberFormatOptions =
      language !== "en" && currency === "MAD"
        ? { minimumFractionDigits: digits, maximumFractionDigits: digits }
        : { style: "currency", currency, minimumFractionDigits: digits, maximumFractionDigits: digits };
    moneyFormats.set(key, new Intl.NumberFormat(numberLocale, options));
  }
  return moneyFormats.get(key)!;
}

// Money is stored in centimes: 125000 -> "MAD 1,250.00" in English, "1 250,00 DH" in French and Arabic.
// `whole` drops the centimes, for rough amounts: "About 140 DH".
export function formatMoney(centimes: number | null | undefined, currency: string, whole = false): string {
  if (centimes === null || centimes === undefined) return "—";
  const amount = spaced(moneyFormat(currency, whole).format(whole ? Math.round(centimes / 100) : centimes / 100));
  return keepTogether(language !== "en" && currency === "MAD" ? `${amount} DH` : amount);
}

// "2026-03-15" -> "Mar 15, 2026" / "15/03/2026"
export function formatDay(value: string): string {
  return keepTogether(dateOnly.format(calendarDay(value)));
}

const monthDay = new Intl.DateTimeFormat(locale, { month: "short", day: "numeric", timeZone: "UTC" });

// "2026-03-15" -> "Mar 15" / "15 mars" / "15 مارس". For chart ticks and sentences, where the year would be noise.
export function formatMonthDay(value: string): string {
  return monthDay.format(calendarDay(value));
}

// "2026-10-01/2026-10-20" -> "Oct 1 – Oct 20" (one day: just that day).
export function formatDayRange(range: string): string {
  const [first, last] = range.split("/");
  return first === last ? formatMonthDay(first) : `${formatMonthDay(first)} – ${formatMonthDay(last)}`;
}

// What someone types in a money field -> centimes. "12,50" and "12.50" -> 1250. Empty -> null.
export function parseMoneyInput(text: string): number | null | "invalid" {
  const cleaned = text.replace(/\s/g, "").replace(",", ".");
  if (!cleaned) return null;
  if (!/^\d+(\.\d{1,2})?$/.test(cleaned)) return "invalid";
  return Math.round(Number(cleaned) * 100);
}

// Centimes -> what goes in a money field: 1250 -> "12,50".
export function moneyInputValue(centimes: number | null): string {
  return centimes === null ? "" : (centimes / 100).toFixed(2).replace(".", ",");
}

const timeOfDay = new Intl.DateTimeFormat(numberLocale, { hour: "2-digit", minute: "2-digit", hourCycle: "h23", timeZone });
const shopDay = new Intl.DateTimeFormat("en-CA", { timeZone }); // "2026-10-29", the day in the shop

// "today 02:00", "yesterday 02:00", then "27/10/2026 02:00": a moment in the shop's time.
export function formatDayAndTime(value: string, now: number = Date.now()): string {
  const moment = shopMoment(value);
  const today = shopMoment(now);
  const daysAgo = Math.round((calendarDay(shopDay.format(today)).getTime() - calendarDay(shopDay.format(moment)).getTime()) / 86_400_000);
  const day = daysAgo === 0 || daysAgo === 1 ? relative.format(-daysAgo, "day") : dateOfMoment.format(moment);
  return keepTogether(`${day} ${timeOfDay.format(moment)}`);
}
