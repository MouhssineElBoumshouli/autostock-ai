import type { AskFilters, AskNumber, AskOut } from "@/api/ask";
import { type AnswerWords, t } from "@/i18n";
import { alertSentence } from "@/lib/alertSentence";
import { formatDayRange, formatMoney, formatMonthDay, formatNumber } from "@/lib/format";

type Subject = { kind: "part" | "matching" | "category" | "all"; name?: string; words?: string; count?: number };

function subjectWords(subject: Subject | undefined): string {
  const words = t.ask.subjects;
  const count = subject?.count === undefined ? null : formatNumber(subject.count);
  switch (subject?.kind) {
    case "part":
      return words.part(subject.name ?? "", count);
    case "matching":
      return words.matching(subject.words ?? "", count ?? "");
    case "category":
      return words.category(subject.name ?? "");
    default:
      return words.all;
  }
}

function capitalized(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function asNumber(value: unknown): number {
  return Number(value ?? 0);
}

// The answer's sentence in the person's language, from the real numbers the server sent with it.
// Falls back to the server's English sentence for an answer this file doesn't know yet.
export function answerSentence(data: AskOut, currency: string): string {
  const build = t.ask.answers[data.key];
  if (!build) return data.sentence;
  const v = data.values;
  const pieces = (value: unknown) => t.common.pieces(asNumber(value), formatNumber(asNumber(value)));
  const alert = v.alert as { kind: string; numbers: Record<string, unknown>; started_on: string } | undefined;
  const subject = subjectWords(v.subject as Subject | undefined);
  const words: AnswerWords = {
    subject,
    Subject: capitalized(subject),
    branch: (v.branch as string | undefined) ?? null,
    period: t.ask.periodWords[v.period as string] ?? "",
    range: v.range ? formatDayRange(String(v.range)) : "",
    pieces: pieces(v.pieces),
    money: typeof v.money === "number" ? formatMoney(v.money, currency, true) : null,
    count: asNumber(v.count),
    shownCount: formatNumber(asNumber(v.count)),
    name: String(v.name ?? ""),
    sku: String(v.sku ?? ""),
    beforePieces: pieces(v.before_pieces),
    beforeRange: v.before_range ? formatDayRange(String(v.before_range)) : "",
    percent: typeof v.percent === "number" ? v.percent : null,
    days: formatNumber(asNumber(v.days)),
    daysLeft: formatNumber(asNumber(v.days_left)),
    low: formatNumber(asNumber(v.low)),
    high: formatNumber(asNumber(v.high)),
    madeFrom: v.made_from ? formatMonthDay(String(v.made_from)) : "",
    madeOn: v.made_on ? formatMonthDay(String(v.made_on)) : "",
    part: String(v.part ?? ""),
    alertBranch: String(v.alert_branch ?? ""),
    alert: alert ? alertSentence({ ...alert, sentence: "" }, currency) : "",
    orderNumber: String(v.order_number ?? ""),
    supplier: String(v.supplier ?? ""),
    words: (v.words as string | undefined) ?? null,
  };
  return build(words);
}

// "I understood: Sales of brake pads · Rabat - Agdal · this week". Mirrors backend/app/ask/understood_line.py.
export function understoodHeading(questionType: string, filters: AskFilters, period: string | null): string {
  const build = t.ask.headings[questionType];
  if (!build) return questionType;
  const subject = filters.part ?? (filters.category ? t.ask.categorySubject(filters.category) : null);
  const pieces = [build(subject)];
  if (filters.branch) pieces.push(filters.branch);
  if (period) pieces.push(t.ask.periodWords[period] ?? period);
  return pieces.join(" · ");
}

export function understoodLine(data: AskOut): string | null {
  if (!data.understood) return null;
  const line = t.ask.understood(understoodHeading(data.question_type, data.filters, data.period));
  return data.understood_by === "model" ? `${t.ask.bestGuess} ${line}` : line;
}

// The label of one of the answer's real numbers.
export function numberLabel(number: AskNumber): string {
  if (!number.key) return number.label;
  const about = t.ask.numberLabelsAbout[number.key];
  if (about) return about(number.about ?? "");
  return t.ask.numberLabels[number.key] ?? number.label;
}
