import { type FormEvent, useState } from "react";
import { toast } from "sonner";

import { type Currency, currencies, type ShopSettings, useSaveSettings, useSettings } from "@/api/settings";
import { ErrorState } from "@/components/ErrorState";
import { FormError } from "@/components/FormError";
import { FormField } from "@/components/FormField";
import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { t } from "@/i18n";
import { requiredError } from "@/lib/validation";

import { BranchesCard } from "./settings/BranchesCard";
import { OrderingCard } from "./settings/OrderingCard";
import { SuppliersCard } from "./settings/SuppliersCard";
import { SynonymsCard } from "./settings/SynonymsCard";

// Owners only: shop name, currency, branches, suppliers and search words.
export function SettingsPage() {
  const settings = useSettings();

  return (
    <div className="grid gap-8">
      <PageHeader title={t.nav.settings} subtitle={t.settings.subtitle} />
      <Card className="max-w-2xl">
        <CardHeader>
          <CardTitle>{t.settings.cardTitle}</CardTitle>
        </CardHeader>
        {settings.isError ? (
          <ErrorState onRetry={() => settings.refetch()} retrying={settings.isFetching} />
        ) : settings.isPending ? (
          <CardContent className="grid gap-5" aria-busy="true">
            <Skeleton className="h-16 w-full" />
            <Skeleton className="h-16 w-full" />
          </CardContent>
        ) : (
          // Remounts with fresh values after saving.
          <SettingsForm key={JSON.stringify(settings.data)} saved={settings.data} />
        )}
      </Card>
      <BranchesCard />
      <SuppliersCard />
      <SynonymsCard />
      <OrderingCard />
    </div>
  );
}

function SettingsForm({ saved }: { saved: ShopSettings }) {
  const save = useSaveSettings();
  const [form, setForm] = useState(saved);
  const [showErrors, setShowErrors] = useState(false);
  const nameError = showErrors ? requiredError(form.name) : undefined;

  function submit(event: FormEvent) {
    event.preventDefault();
    setShowErrors(true);
    if (requiredError(form.name)) return;
    save.mutate({ ...form, name: form.name.trim() }, { onSuccess: () => toast.success(t.settings.saved) });
  }

  return (
    <form noValidate onSubmit={submit} className="grid gap-6">
      <CardContent className="grid gap-5">
        <FormField label={t.settings.shopName} help={t.settings.shopNameHelp} error={nameError}>
          {(field) => <Input {...field} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />}
        </FormField>
        <FormField label={t.settings.currency} help={t.settings.currencyHelp}>
          {(field) => (
            <Select value={form.currency} onValueChange={(currency) => setForm({ ...form, currency: currency as Currency })}>
              <SelectTrigger {...field}>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {currencies.map((currency) => (
                  <SelectItem key={currency} value={currency}>
                    {t.settings.currencies[currency]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
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
