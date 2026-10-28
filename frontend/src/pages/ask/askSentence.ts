import type { AskFilters, AskNumber, AskOut } from "@/api/ask";
import { t } from "@/i18n";
import { isolate } from "@/lib/format";

// "I understood: Sales of brake pads · Rabat - Agdal · this week". Mirrors backend/app/ask/understood_line.py.
export function understoodHeading(questionType: string, filters: AskFilters, period: string | null): string {
  const build = t.ask.headings[questionType];
  if (!build) return questionType;
  const subject = filters.part
    ? isolate(filters.part)
    : filters.category
      ? t.ask.categorySubject(isolate(filters.category))
      : null;
  const pieces = [build(subject)];
  if (filters.branch) pieces.push(isolate(filters.branch));
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
  if (about) return about(isolate(number.about ?? ""));
  return t.ask.numberLabels[number.key] ?? number.label;
}
