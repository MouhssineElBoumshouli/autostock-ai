import { ArrowRightIcon } from "lucide-react";
import { Link } from "react-router";

import type { AskFilters, AskOut } from "@/api/ask";
import type { Choice } from "@/api/stock";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableRow } from "@/components/ui/table";
import { t } from "@/i18n";

import { formatAskNumber } from "./askFormat";
import { relatedScreen } from "./questionTypes";
import { UnderstoodChips } from "./UnderstoodChips";

export type HistoryEntry = { id: string; question: string; data: AskOut };

// One question and its answer: what was understood (editable), the plain sentence, the real
// numbers behind it, then either "Did you mean" buttons or a button to the related screen.
export function AnswerCard({
  entry,
  categories,
  branches,
  currency,
  onRefine,
  onPickType,
  onAskExample,
}: {
  entry: HistoryEntry;
  categories: string[];
  branches: Choice[];
  currency: string;
  onRefine: (filters: AskFilters) => void;
  onPickType: (questionType: string) => void;
  onAskExample: (question: string) => void;
}) {
  const data = entry.data;
  const understood = data.question_type !== "not_sure" && data.question_type !== "cannot_answer";
  const related = understood ? relatedScreen(data.question_type, data.filters, branches) : null;

  return (
    <Card className="py-0">
      <CardContent className="grid grid-cols-1 gap-4 py-6">
        <p className="text-label-large text-on-surface-variant">{t.ask.asked(entry.question)}</p>

        {understood && (
          <UnderstoodChips
            questionType={data.question_type}
            filters={data.filters}
            categories={categories}
            branches={branches}
            onChange={onRefine}
          />
        )}

        <div className="grid gap-1">
          {data.understood && <p className="text-body-large text-on-surface">{data.understood}</p>}
          <p className="text-body-large text-on-surface">{data.sentence}</p>
        </div>

        {data.numbers.length > 0 && (
          <div className="overflow-x-auto rounded-sm border border-outline-variant">
            <Table>
              <TableBody>
                {data.numbers.map((number, index) => (
                  <TableRow key={index}>
                    <TableCell className="text-on-surface-variant">{number.label}</TableCell>
                    <TableCell className="text-end font-medium tabular-nums">
                      {formatAskNumber(number, currency)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}

        {data.question_type === "cannot_answer" && (
          <div className="grid gap-2">
            <p className="text-label-large text-on-surface-variant">{t.ask.tryInstead}</p>
            <div className="flex flex-wrap gap-2">
              {t.ask.examples.slice(0, 3).map((example) => (
                <Button key={example} variant="tonal" size="sm" onClick={() => onAskExample(example)}>
                  {example}
                </Button>
              ))}
            </div>
          </div>
        )}

        {data.suggestions.length > 0 && (
          <div className="grid gap-2">
            {data.question_type !== "not_sure" && (
              <p className="text-label-large text-on-surface-variant">{t.ask.didYouMean}</p>
            )}
            <div className="flex flex-wrap gap-2">
              {data.suggestions.map((suggestion) => (
                <Button
                  key={suggestion.question_type}
                  variant="outlined"
                  size="sm"
                  onClick={() => onPickType(suggestion.question_type)}
                >
                  {suggestion.label}
                </Button>
              ))}
            </div>
          </div>
        )}

        {related && (
          <div>
            <Button asChild variant="text" size="sm">
              <Link to={related.to}>
                {t.ask.relatedScreen[related.labelKey]}
                <ArrowRightIcon aria-hidden="true" />
              </Link>
            </Button>
          </div>
        )}

        {data.ai_note && <p className="text-label-medium text-on-surface-variant">{data.ai_note}</p>}
      </CardContent>
    </Card>
  );
}
