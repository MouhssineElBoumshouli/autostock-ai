import { type FormEvent, useState } from "react";
import { toast } from "sonner";

import { type User, useResetPassword } from "@/api/users";
import { FormError } from "@/components/FormError";
import { FormField } from "@/components/FormField";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { t } from "@/i18n";
import { passwordError } from "@/lib/validation";

// Owner gives someone a new temporary password. They are logged out and must choose their own.
export function ResetPasswordDialog({ user }: { user: User }) {
  const resetPassword = useResetPassword();
  const [open, setOpen] = useState(false);
  const [password, setPassword] = useState("");
  const [showErrors, setShowErrors] = useState(false);

  function changeOpen(nextOpen: boolean) {
    if (!nextOpen) {
      setPassword("");
      setShowErrors(false);
      resetPassword.reset();
    }
    setOpen(nextOpen);
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    setShowErrors(true);
    if (passwordError(password)) return;
    resetPassword.mutate(
      { id: user.id, temporary_password: password },
      {
        onSuccess: () => {
          toast.success(t.team.resetDone(user.name));
          changeOpen(false);
        },
      },
    );
  }

  return (
    <Dialog open={open} onOpenChange={changeOpen}>
      <DialogTrigger asChild>
        <Button size="sm" variant="subtle">
          {t.team.resetPassword}
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t.team.resetTitle(user.name)}</DialogTitle>
          <DialogDescription>{t.team.resetText}</DialogDescription>
        </DialogHeader>
        <form noValidate onSubmit={submit} className="grid gap-5">
          <FormField
            label={t.fields.temporaryPassword}
            help={t.team.temporaryPasswordHelp}
            error={showErrors ? passwordError(password) : undefined}
          >
            {(field) => (
              <Input
                {...field}
                autoComplete="new-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            )}
          </FormField>
          <FormError message={resetPassword.error?.message} />
          <DialogFooter>
            <Button type="button" variant="subtle" onClick={() => changeOpen(false)}>
              {t.common.cancel}
            </Button>
            <Button type="submit" variant="danger" loading={resetPassword.isPending}>
              {t.team.resetPassword}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
