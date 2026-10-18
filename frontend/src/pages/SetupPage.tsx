import { type FormEvent, useState } from "react";
import { Navigate, useNavigate } from "react-router";

import { type SetupForm, useSetup, useSetupNeeded } from "@/api/auth";
import { CenteredCard } from "@/components/CenteredCard";
import { ErrorState } from "@/components/ErrorState";
import { FormError } from "@/components/FormError";
import { FormField } from "@/components/FormField";
import { PasswordInput } from "@/components/PasswordInput";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { t } from "@/i18n";
import { emailError, passwordError, requiredError } from "@/lib/validation";

const empty: SetupForm = { shop_name: "", name: "", email: "", password: "" };

function findErrors(form: SetupForm) {
  return {
    shop_name: requiredError(form.shop_name),
    name: requiredError(form.name),
    email: emailError(form.email),
    password: passwordError(form.password),
  };
}

// Shown only once, when nobody has an account yet: creates the shop and its first owner.
export function SetupPage() {
  const setupNeeded = useSetupNeeded();
  const setup = useSetup();
  const navigate = useNavigate();
  const [form, setForm] = useState(empty);
  const [showErrors, setShowErrors] = useState(false);
  const errors: Partial<ReturnType<typeof findErrors>> = showErrors ? findErrors(form) : {};

  if (setupNeeded.isPending) {
    return (
      <CenteredCard title={t.setup.title}>
        <Skeleton className="h-40 w-full" />
      </CenteredCard>
    );
  }
  if (setupNeeded.isError) {
    return <ErrorState onRetry={() => setupNeeded.refetch()} retrying={setupNeeded.isFetching} />;
  }
  if (!setupNeeded.data && !setup.isSuccess) {
    return <Navigate to="/login" replace />;
  }

  function update(field: keyof SetupForm, value: string) {
    setForm({ ...form, [field]: value });
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    setShowErrors(true);
    if (Object.values(findErrors(form)).some(Boolean)) return;
    setup.mutate(form, { onSuccess: () => navigate("/", { replace: true }) });
  }

  return (
    <CenteredCard title={t.setup.title} subtitle={t.setup.subtitle}>
      <form noValidate onSubmit={submit} className="grid gap-5">
        <FormField label={t.fields.shopName} help={t.setup.shopNameHelp} error={errors.shop_name}>
          {(field) => <Input {...field} value={form.shop_name} onChange={(e) => update("shop_name", e.target.value)} />}
        </FormField>
        <FormField label={t.fields.yourName} error={errors.name}>
          {(field) => (
            <Input {...field} autoComplete="name" value={form.name} onChange={(e) => update("name", e.target.value)} />
          )}
        </FormField>
        <FormField label={t.fields.email} error={errors.email}>
          {(field) => (
            <Input
              {...field}
              type="email"
              autoComplete="email"
              value={form.email}
              onChange={(e) => update("email", e.target.value)}
            />
          )}
        </FormField>
        <FormField label={t.fields.password} help={t.setup.passwordHelp} error={errors.password}>
          {(field) => (
            <PasswordInput
              {...field}
              autoComplete="new-password"
              value={form.password}
              onChange={(e) => update("password", e.target.value)}
            />
          )}
        </FormField>
        <FormError message={setup.error?.message} />
        <Button type="submit" variant="filled" loading={setup.isPending} className="w-full">
          {t.setup.submit}
        </Button>
      </form>
    </CenteredCard>
  );
}
