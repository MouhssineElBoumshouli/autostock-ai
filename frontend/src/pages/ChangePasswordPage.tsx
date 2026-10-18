import { type FormEvent, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";
import { toast } from "sonner";

import { useChangePassword, useLogout, useMe } from "@/api/auth";
import { CenteredCard } from "@/components/CenteredCard";
import { FormError } from "@/components/FormError";
import { FormField } from "@/components/FormField";
import { PasswordInput } from "@/components/PasswordInput";
import { Button } from "@/components/ui/button";
import { t } from "@/i18n";
import { passwordError, requiredError, safeNextPath } from "@/lib/validation";

type PasswordForm = { current: string; next: string; repeat: string };

function findErrors(form: PasswordForm) {
  return {
    current: requiredError(form.current),
    next: passwordError(form.next),
    repeat: form.repeat === form.next ? undefined : t.validation.passwordsDiffer,
  };
}

// Change your own password. Also the forced screen after the owner set a temporary password.
export function ChangePasswordPage() {
  const forced = useMe().data!.user.must_change_password;
  const changePassword = useChangePassword();
  const logout = useLogout();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [form, setForm] = useState<PasswordForm>({ current: "", next: "", repeat: "" });
  const [showErrors, setShowErrors] = useState(false);
  const errors: Partial<ReturnType<typeof findErrors>> = showErrors ? findErrors(form) : {};

  function submit(event: FormEvent) {
    event.preventDefault();
    setShowErrors(true);
    if (Object.values(findErrors(form)).some(Boolean)) return;
    changePassword.mutate(
      { current_password: form.current, new_password: form.next },
      {
        onSuccess: () => {
          toast.success(t.changePassword.done);
          navigate(safeNextPath(searchParams.get("next")), { replace: true });
        },
      },
    );
  }

  return (
    <CenteredCard
      title={forced ? t.changePassword.forcedTitle : t.changePassword.title}
      subtitle={forced ? t.changePassword.forcedSubtitle : t.changePassword.subtitle}
    >
      <form noValidate onSubmit={submit} className="grid gap-5">
        <FormField label={forced ? t.fields.temporaryPassword : t.fields.currentPassword} error={errors.current}>
          {(field) => (
            <PasswordInput
              {...field}
              autoComplete="current-password"
              value={form.current}
              onChange={(e) => setForm({ ...form, current: e.target.value })}
            />
          )}
        </FormField>
        <FormField label={t.fields.newPassword} help={t.changePassword.newPasswordHelp} error={errors.next}>
          {(field) => (
            <PasswordInput
              {...field}
              autoComplete="new-password"
              value={form.next}
              onChange={(e) => setForm({ ...form, next: e.target.value })}
            />
          )}
        </FormField>
        <FormField label={t.fields.repeatNewPassword} error={errors.repeat}>
          {(field) => (
            <PasswordInput
              {...field}
              autoComplete="new-password"
              value={form.repeat}
              onChange={(e) => setForm({ ...form, repeat: e.target.value })}
            />
          )}
        </FormField>
        <FormError message={changePassword.error?.message} />
        <div className="grid gap-2">
          <Button type="submit" variant="primary" loading={changePassword.isPending} className="w-full">
            {t.changePassword.submit}
          </Button>
          {forced ? (
            // Not you, or not now: the only other way out of this screen.
            <Button
              type="button"
              variant="subtle"
              className="w-full"
              loading={logout.isPending}
              onClick={() => logout.mutate(undefined, { onSuccess: () => navigate("/login", { replace: true }) })}
            >
              {t.home.logOut}
            </Button>
          ) : (
            <Button variant="subtle" asChild className="w-full">
              <Link to="/">{t.common.cancel}</Link>
            </Button>
          )}
        </div>
      </form>
    </CenteredCard>
  );
}
