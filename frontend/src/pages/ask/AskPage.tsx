import { MessageCircleQuestionIcon } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router";

import { type AskRequest, useAsk } from "@/api/ask";
import { useStockFilterChoices } from "@/api/stock";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { PageHeader } from "@/components/PageHeader";
import { useSignedIn } from "@/components/SignedIn";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { t } from "@/i18n";

import { AnswerCard, type HistoryEntry } from "./AnswerCard";
import { QuestionForm } from "./QuestionForm";

const HISTORY_LIMIT = 10;

// One big question box, example chips, and the last 10 questions of this visit, newest on top.
// "?q=" (set by the small box on Today) asks that question right away, once.
export function AskPage() {
  const currency = useSignedIn().organization.currency;
  const choices = useStockFilterChoices();
  const ask = useAsk();
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [lastRequest, setLastRequest] = useState<{ request: AskRequest; question: string } | null>(null);
  const [params, setParams] = useSearchParams();
  const askedFromLink = useRef(false);

  function submit(request: AskRequest, question: string) {
    setLastRequest({ request, question });
    ask.mutate(request, {
      onSuccess: (data) => {
        setHistory((previous) => [{ id: crypto.randomUUID(), question, data }, ...previous].slice(0, HISTORY_LIMIT));
      },
    });
  }

  useEffect(() => {
    const prefilled = params.get("q");
    if (!prefilled || askedFromLink.current) return;
    askedFromLink.current = true;
    submit({ question: prefilled }, prefilled);
    const next = new URLSearchParams(params);
    next.delete("q");
    setParams(next, { replace: true });
    // Runs once, right when the page opens from "?q=".
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const thinking = ask.isPending;
  const failed = ask.isError && !thinking;

  return (
    <div className="grid grid-cols-1 gap-8">
      <PageHeader title={t.nav.ask} subtitle={t.ask.subtitle} />
      <QuestionForm onAsk={(question) => submit({ question }, question)} asking={thinking} />

      {thinking && (
        <div className="flex items-center gap-3 text-body-medium text-on-surface-variant" aria-busy="true">
          <Skeleton className="size-5 shrink-0 rounded-full" />
          {t.ask.thinking}
        </div>
      )}

      {failed && (
        <Card className="py-0">
          <ErrorState
            message={ask.error instanceof Error ? ask.error.message : undefined}
            onRetry={() => lastRequest && submit(lastRequest.request, lastRequest.question)}
          />
        </Card>
      )}

      {history.length === 0 && !thinking && !failed ? (
        <EmptyState icon={MessageCircleQuestionIcon} title={t.ask.emptyTitle} description={t.ask.emptyDescription} />
      ) : (
        <div className="grid grid-cols-1 gap-4">
          {history.map((entry) => (
            <AnswerCard
              key={entry.id}
              entry={entry}
              categories={choices.data?.categories ?? []}
              branches={choices.data?.branches ?? []}
              currency={currency}
              onRefine={(filters) =>
                submit({ question: entry.question, question_type: entry.data.question_type, filters }, entry.question)
              }
              onPickType={(questionType) =>
                submit({ question: entry.question, question_type: questionType }, entry.question)
              }
              onAskExample={(question) => submit({ question }, question)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
