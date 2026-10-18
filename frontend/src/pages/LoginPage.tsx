import { type FormEvent, useState } from "react";
import { Navigate, useNavigate, useSearchParams } from "react-router";

import { useLogin, useMe, useSetupNeeded } from "@/api/auth";
import { CenteredCard } from "@/components/CenteredCard";
import { FormError } from "@/components/FormError";
import { FormField } from "@/components/FormField";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { t } from "@/i18n";
import { emailError, requiredError, safeNextPath } from "@/lib/validation";

export function LoginPage() {
  const me = useMe();
  const setupNeeded = useSetupNeeded();
  const login = useLogin();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const next = safeNextPath(searchParams.get("next"));
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showErrors, setShowErrors] = useState(false);

  if (setupNeeded.data === true) return <Navigate to="/setup" replace />;
  if (me.data) return <Navigate to={next} replace />;

  const errors = showErrors ? { email: emailError(email), password: requiredError(password) } : {};

  function submit(event: FormEvent) {
    event.preventDefault();
    setShowErrors(true);
    if (emailError(email) || requiredError(password)) return;
    login.mutate({ email, password }, { onSuccess: () => navigate(next, { replace: true }) });
  }

  return (
    <CenteredCard title={t.login.title} subtitle={t.login.subtitle}>
      <form noValidate onSubmit={submit} className="grid gap-5">
        <FormField label={t.fields.email} error={errors.email}>
          {(field) => (
            <Input
              {...field}
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          )}
        </FormField>
        <FormField label={t.fields.password} error={errors.password}>
          {(field) => (
            <Input
              {...field}
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          )}
        </FormField>
        <FormError message={login.error?.message} />
        <Button type="submit" variant="primary" loading={login.isPending} className="w-full">
          {t.login.submit}
        </Button>
      </form>
    </CenteredCard>
  );
}
