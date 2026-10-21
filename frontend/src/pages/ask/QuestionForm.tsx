import { cn } from "cn";
import { SendIcon } from "lucide-react";
import { type FormEvent, useState } from "react";

import { Button } from "@/components/ui/button";
import { fieldClasses } from "@/components/ui/input";
import { t } from "@/i18n";

// One big question box, and the example questions as chips under it. Clicking an example asks it
// right away, without going through the box.
export function QuestionForm({ onAsk, asking }: { onAsk: (question: string) => void; asking: boolean }) {
  const [text, setText] = useState("");

  function submit(event: FormEvent) {
    event.preventDefault();
    const question = text.trim();
    if (!question) return;
    onAsk(question);
    setText("");
  }

  return (
    <div className="grid gap-3">
      <form onSubmit={submit} className="flex gap-2">
        <input
          aria-label={t.ask.inputLabel}
          placeholder={t.ask.inputPlaceholder}
          value={text}
          onChange={(event) => setText(event.target.value)}
          className={cn(fieldClasses, "h-14 flex-1 rounded-full px-6 text-body-large")}
        />
        <Button type="submit" variant="filled" size="icon" className="shrink-0" disabled={!text.trim()} loading={asking}>
          <SendIcon aria-hidden="true" />
          <span className="sr-only">{t.ask.submit}</span>
        </Button>
      </form>
      <div className="flex flex-wrap gap-2">
        {t.ask.examples.map((example) => (
          <Button key={example} type="button" variant="tonal" size="sm" onClick={() => onAsk(example)}>
            {example}
          </Button>
        ))}
      </div>
    </div>
  );
}
