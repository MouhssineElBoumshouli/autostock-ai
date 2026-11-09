import { ArrowRightIcon, SearchIcon } from "lucide-react";
import { Link } from "react-router";

import type { AssistantEvent, AssistantLookup, LookupFilters } from "@/api/ask";
import type { Choice } from "@/api/stock";
import { ErrorState } from "@/components/ErrorState";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableRow } from "@/components/ui/table";
import { t } from "@/i18n";

import { formatAskNumber } from "./askFormat";
import { numberLabel } from "./askSentence";
import { lookupHeading } from "./lookupHeading";
import { relatedScreen } from "./questionTypes";

type Done = Extract<AssistantEvent, { type: "done" }>;
export type AssistantEntry = {
  id: string;
  kind: "assistant";
  question: string;
  lookingUp: { tool: string; filters: LookupFilters }[];
  text: string;
  done: Done | null;
  failed: boolean;
  // Why the online assistant couldn't answer this one (a key of t.ask.assistant.onlineOff): the app answered.
  onlineOff?: string;
};

// The online assistant writes plain text; a stray "**bold**" from it is shown as plain words.
function plainText(text: string): string {
  return text.replace(/\*\*/g, "");
}

// One question to the assistant: what it is looking up, the answer (in the question's own language, by the
// online assistant once every number passed the check, or by the app), and under it the real numbers it used.
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

        {entry.onlineOff && (
          <p className="text-body-small text-on-surface-variant">
            {t.ask.assistant.onlineOff[entry.onlineOff] ?? t.ask.assistant.onlineOff.error}
          </p>
        )}

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
        ) : (
          <div aria-live="polite" aria-busy={writing}>
            {(done?.text || entry.text) && (
              <p dir="auto" lang={done?.language} className="whitespace-pre-line text-body-large text-on-surface">
                {plainText(done ? done.text : entry.text)}
              </p>
            )}
            {writing && (
              <div className="mt-2 flex items-center gap-3 text-body-medium text-on-surface-variant">
                <Skeleton className="size-5 shrink-0 rounded-full" />
                {entry.text ? t.ask.assistant.writing : t.ask.thinking}
              </div>
            )}
            {done?.written_by === "groq" && (
              <p className="mt-2 text-body-small text-on-surface-variant">{t.ask.assistant.writtenByGroq}</p>
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
