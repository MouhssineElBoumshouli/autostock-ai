import { ArrowRightIcon, SearchIcon } from "lucide-react";
import { Link } from "react-router";

import type { AskFilters, AssistantEvent, AssistantLookup } from "@/api/ask";
import type { Choice } from "@/api/stock";
import { ErrorState } from "@/components/ErrorState";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableRow } from "@/components/ui/table";
import { t } from "@/i18n";

import { formatAskNumber } from "./askFormat";
import { answerSentence, numberLabel, understoodHeading } from "./askSentence";
import { relatedScreen } from "./questionTypes";

type Done = Extract<AssistantEvent, { type: "done" }>;
export type AssistantEntry = {
  id: string;
  kind: "assistant";
  question: string;
  lookingUp: { tool: string; filters: AskFilters }[];
  text: string;
  done: Done | null;
  failed: boolean;
};

function lookupHeading(tool: string, filters: AskFilters): string {
  return understoodHeading(tool, filters, filters.period ?? null);
}

// The model writes plain text; a stray "**bold**" from it is shown as plain words.
function plainText(text: string): string {
  return text.replace(/\*\*/g, "");
}

// One question to the assistant: what it is looking up, the answer as it is written, and under it
// the real numbers it used. If a written number didn't match the shop's data, the app's own
// sentences from the same lookups replace the written answer.
export function AssistantCard({
  entry,
  branches,
  currency,
  onRetry,
}: {
  entry: AssistantEntry;
  branches: Choice[];
  currency: string;
  onRetry: () => void;
}) {
  const done = entry.done;
  const lookups = done?.lookups ?? [];
  const writing = !done && !entry.failed;
  const related = lookups.length ? relatedScreen(lookups[0].tool, lookups[0].filters, branches) : null;

  return (
    <Card className="py-0">
      <CardContent className="grid grid-cols-1 gap-4 py-6">
        <p className="text-label-large text-on-surface-variant">{t.ask.asked(entry.question)}</p>

        {entry.lookingUp.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {entry.lookingUp.map((lookup, index) => (
              <span
                key={index}
                className="inline-flex min-w-0 items-center gap-1.5 rounded-sm bg-secondary-container px-3 py-1 text-label-medium text-on-secondary-container"
              >
                <SearchIcon aria-hidden="true" className="size-4 shrink-0" />
                <span className="min-w-0 break-words">{lookupHeading(lookup.tool, lookup.filters)}</span>
              </span>
            ))}
          </div>
        )}

        {entry.failed ? (
          <ErrorState onRetry={onRetry} />
        ) : done && !done.checked ? (
          <div className="grid gap-2">
            <p className="text-body-medium text-on-surface-variant">
              {lookups.length
                ? t.ask.assistant.notChecked
                : done.question?.type === "cannot_answer"
                  ? answerSentence({ key: "cannot_answer", values: {}, sentence: "" }, currency)
                  : t.ask.assistant.noLookup}
            </p>
            {lookups.map((lookup, index) => (
              <p key={index} className="text-body-large text-on-surface">
                {answerSentence(lookup, currency)}
              </p>
            ))}
          </div>
        ) : (
          <div aria-live="polite" aria-busy={writing}>
            {entry.text && (
              <p dir="auto" className="whitespace-pre-line text-body-large text-on-surface">
                {plainText(done ? done.text : entry.text)}
              </p>
            )}
            {writing && (
              <div className="mt-2 flex items-center gap-3 text-body-medium text-on-surface-variant">
                <Skeleton className="size-5 shrink-0 rounded-full" />
                {entry.text ? t.ask.assistant.writing : t.ask.thinking}
              </div>
            )}
          </div>
        )}

        {lookups.length > 0 && <BasedOn lookups={lookups} currency={currency} />}

        {related && (
          <div>
            <Button asChild variant="text" size="sm">
              <Link to={related.to}>
                {t.ask.relatedScreen[related.labelKey]}
                <ArrowRightIcon aria-hidden="true" className="rtl:rotate-180" />
              </Link>
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// "Based on:" each lookup's heading and its real numbers.
function BasedOn({ lookups, currency }: { lookups: AssistantLookup[]; currency: string }) {
  return (
    <div className="grid gap-3">
      <p className="text-label-large text-on-surface-variant">{t.ask.assistant.basedOn}</p>
      {lookups.map((lookup, index) => (
        <div key={index} className="grid gap-1">
          <p className="text-label-medium text-on-surface-variant">{lookupHeading(lookup.tool, lookup.filters)}</p>
          {lookup.numbers.length > 0 && (
            <div className="overflow-x-auto rounded-sm border border-outline-variant">
              <Table>
                <TableBody>
                  {lookup.numbers.map((number, row) => (
                    <TableRow key={row}>
                      <TableCell dir={number.key ? undefined : "auto"} className="text-on-surface-variant">
                        {numberLabel(number)}
                      </TableCell>
                      <TableCell className="text-end font-medium tabular-nums">{formatAskNumber(number, currency)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
