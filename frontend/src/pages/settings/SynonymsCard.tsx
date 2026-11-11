import { cn } from "cn";
import { type FormEvent, useState } from "react";
import { toast } from "sonner";

import { type SynonymList, useSaveSynonyms, useSynonyms } from "@/api/synonyms";
import { ErrorState } from "@/components/ErrorState";
import { FormError } from "@/components/FormError";
import { FormField } from "@/components/FormField";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { fieldClasses } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { t } from "@/i18n";

// The shop's search words: one line per group, words separated by commas.
export function SynonymsCard() {
  const synonyms = useSynonyms();

  return (
    <Card className="max-w-2xl">
      <CardHeader>
        <CardTitle>{t.settings.synonyms.title}</CardTitle>
        <CardDescription>{t.settings.synonyms.description}</CardDescription>
      </CardHeader>
      {synonyms.isError ? (
        <ErrorState onRetry={() => synonyms.refetch()} retrying={synonyms.isFetching} />
      ) : synonyms.isPending ? (
        <CardContent aria-busy="true">
          <Skeleton className="h-64 w-full" />
        </CardContent>
      ) : (
        // Remounts with fresh values after saving.
        <SynonymsForm key={JSON.stringify(synonyms.data)} saved={synonyms.data} />
      )}
    </Card>
  );
}

function toText(list: SynonymList): string {
  return list.groups.map((words) => words.join(", ")).join("\n");
}

function toList(text: string): SynonymList {
  return { groups: text.split("\n").map((line) => line.split(",").map((word) => word.trim())) };
}

function SynonymsForm({ saved }: { saved: SynonymList }) {
  const save = useSaveSynonyms();
  const [text, setText] = useState(() => toText(saved));

  function submit(event: FormEvent) {
    event.preventDefault();
    save.mutate(toList(text), { onSuccess: () => toast.success(t.settings.synonyms.saved) });
  }

  return (
    <form noValidate onSubmit={submit} className="grid gap-6">
      <CardContent className="grid gap-5">
        <FormField label={t.settings.synonyms.field} help={t.settings.synonyms.help}>
          {(field) => (
            <textarea
              {...field}
              dir="auto"
              rows={12}
              value={text}
              onChange={(event) => setText(event.target.value)}
              className={cn(fieldClasses, "h-auto py-4 leading-relaxed")}
            />
          )}
        </FormField>
        <FormError message={save.error?.message} />
      </CardContent>
      <CardFooter className="border-t pt-6">
        <Button type="submit" variant="filled" loading={save.isPending}>
          {t.common.save}
        </Button>
      </CardFooter>
    </form>
  );
}
