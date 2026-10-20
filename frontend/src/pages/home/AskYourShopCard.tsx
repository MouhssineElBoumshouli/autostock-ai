import { cn } from "cn";
import { SendIcon } from "lucide-react";
import { type FormEvent, useState } from "react";
import { useNavigate } from "react-router";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { fieldClasses } from "@/components/ui/input";
import { t } from "@/i18n";

// A small box on Today: asking here opens the Ask page with the question already asked.
export function AskYourShopCard() {
  const navigate = useNavigate();
  const [text, setText] = useState("");

  function submit(event: FormEvent) {
    event.preventDefault();
    const question = text.trim();
    if (!question) return;
    navigate(`/ask?q=${encodeURIComponent(question)}`);
  }

  return (
    <Card>
      <CardContent>
        <form onSubmit={submit} className="flex gap-2">
          <input
            aria-label={t.ask.homeBox.inputLabel}
            placeholder={t.ask.homeBox.placeholder}
            value={text}
            onChange={(event) => setText(event.target.value)}
            className={cn(fieldClasses, "h-12 flex-1 rounded-full px-5 text-body-medium")}
          />
          <Button type="submit" variant="tonal" className="shrink-0" disabled={!text.trim()}>
            <SendIcon aria-hidden="true" />
            {t.ask.homeBox.submit}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
