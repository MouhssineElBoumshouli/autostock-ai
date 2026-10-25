import { InfoIcon, MessageCircleQuestionIcon } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router";

import { type AskRequest, type AskedBefore, askAssistant, useAiOn, useAsk } from "@/api/ask";
import { useStockFilterChoices } from "@/api/stock";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { PageHeader } from "@/components/PageHeader";
import { useSignedIn } from "@/components/SignedIn";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { t } from "@/i18n";

import { AnswerCard, type HistoryEntry } from "./AnswerCard";
import { type AssistantEntry, AssistantCard } from "./AssistantCard";
import { QuestionForm } from "./QuestionForm";

const HISTORY_LIMIT = 10;

type RuleEntry = HistoryEntry & { kind: "rule" };
type Entry = RuleEntry | AssistantEntry;

// One big question box and this visit's questions, newest on top. With the local AI on, the
// assistant answers in its own words and follow-ups keep the conversation; with it off, the keyword
// rule answers (with a note at the top saying so). "?q=" (from the box on Today) asks right away, once.
export function AskPage() {
  const currency = useSignedIn().organization.currency;
  const choices = useStockFilterChoices();
  const aiOn = useAiOn();
  const ask = useAsk();
  const [history, setHistory] = useState<Entry[]>([]);
  // The last question the app understood in this conversation: "and in Rabat?" changes it.
  const [previous, setPrevious] = useState<AskedBefore | null>(null);
  const [writing, setWriting] = useState(false);
  const [lastRule, setLastRule] = useState<{ request: AskRequest; question: string } | null>(null);
  const [params, setParams] = useSearchParams();
  const askedFromLink = useRef(false);
  const aiOff = aiOn.data?.ai_on === false;

  function addEntry(entry: Entry) {
    setHistory((previous) => [entry, ...previous].slice(0, HISTORY_LIMIT));
  }

  function askRule(request: AskRequest, question: string) {
    setLastRule({ request, question });
    ask.mutate(request, {
      onSuccess: (data) => addEntry({ kind: "rule", id: crypto.randomUUID(), question, data }),
    });
  }

  function update(id: string, change: (entry: AssistantEntry) => AssistantEntry) {
    setHistory((previous) => previous.map((entry) => (entry.id === id && entry.kind === "assistant" ? change(entry) : entry)));
  }

  async function askAi(question: string) {
    const id = crypto.randomUUID();
    addEntry({ id, kind: "assistant", question, lookingUp: [], text: "", done: null, failed: false });
    setWriting(true);
    try {
      await askAssistant(question, previous, (event) => {
        if (event.type === "ai_off") {
          setHistory((previous) => previous.filter((entry) => entry.id !== id));
          void aiOn.refetch();
          askRule({ question }, question);
        } else if (event.type === "looking_up") {
          update(id, (entry) => ({ ...entry, lookingUp: [...entry.lookingUp, { tool: event.tool, filters: event.filters }] }));
        } else if (event.type === "text") {
          update(id, (entry) => ({ ...entry, text: entry.text + event.text }));
        } else {
          update(id, (entry) => ({ ...entry, done: event }));
          if (event.question && event.question.type !== "cannot_answer") setPrevious(event.question);
        }
      });
    } catch {
      update(id, (entry) => ({ ...entry, failed: true }));
    } finally {
      setWriting(false);
    }
  }

  function submit(question: string) {
    if (aiOff) askRule({ question }, question);
    else void askAi(question);
  }

  function newConversation() {
    setPrevious(null);
    setHistory([]);
  }

  useEffect(() => {
    const prefilled = params.get("q");
    if (!prefilled || askedFromLink.current || aiOn.isPending) return;
    askedFromLink.current = true;
    submit(prefilled);
    const next = new URLSearchParams(params);
    next.delete("q");
    setParams(next, { replace: true });
    // Runs once, as soon as it is known whether the AI is on.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [aiOn.isPending]);

  const thinking = ask.isPending;
  const failed = ask.isError && !thinking;

  return (
    <div className="grid grid-cols-1 gap-8">
      <PageHeader title={t.nav.ask} subtitle={t.ask.subtitle} />
      {aiOff && (
        <div className="flex items-start gap-3 rounded-md bg-surface-container-high p-4 text-body-medium text-on-surface">
          <InfoIcon aria-hidden="true" className="mt-0.5 size-5 shrink-0 text-on-surface-variant" />
          <p>{t.ask.assistant.aiOffNote}</p>
        </div>
      )}
      <QuestionForm onAsk={submit} asking={thinking || writing} />

      {previous && !aiOff && (
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-body-medium text-on-surface-variant">{t.ask.assistant.followUpHint}</p>
          <Button variant="text" size="sm" onClick={newConversation} disabled={writing}>
            {t.ask.assistant.newConversation}
          </Button>
        </div>
      )}

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
            onRetry={() => lastRule && askRule(lastRule.request, lastRule.question)}
          />
        </Card>
      )}

      {history.length === 0 && !thinking && !failed ? (
        <EmptyState icon={MessageCircleQuestionIcon} title={t.ask.emptyTitle} description={t.ask.emptyDescription} />
      ) : (
        <div className="grid grid-cols-1 gap-4">
          {history.map((entry) =>
            entry.kind === "assistant" ? (
              <AssistantCard
                key={entry.id}
                entry={entry}
                branches={choices.data?.branches ?? []}
                currency={currency}
                onRetry={() => submit(entry.question)}
              />
            ) : (
              <AnswerCard
                key={entry.id}
                entry={entry}
                categories={choices.data?.categories ?? []}
                branches={choices.data?.branches ?? []}
                currency={currency}
                onRefine={(filters) =>
                  askRule({ question: entry.question, question_type: entry.data.question_type, filters }, entry.question)
                }
                onPickType={(questionType) => askRule({ question: entry.question, question_type: questionType }, entry.question)}
                onAskExample={submit}
              />
            ),
          )}
        </div>
      )}
    </div>
  );
}
