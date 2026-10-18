import { type FormEvent, useState } from "react";
import { toast } from "sonner";

import { type NewUser, type Role, roles, useAddUser } from "@/api/users";
import { FormError } from "@/components/FormError";
import { FormField } from "@/components/FormField";
import { PasswordInput } from "@/components/PasswordInput";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { t } from "@/i18n";
import { emailError, passwordError, requiredError } from "@/lib/validation";

const empty: NewUser = { name: "", email: "", role: "staff", temporary_password: "" };

function findErrors(form: NewUser) {
  return {
    name: requiredError(form.name),
    email: emailError(form.email),
    temporary_password: passwordError(form.temporary_password),
  };
}

export function AddPersonDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const addUser = useAddUser();
  const [form, setForm] = useState(empty);
  const [showErrors, setShowErrors] = useState(false);
  const errors: Partial<ReturnType<typeof findErrors>> = showErrors ? findErrors(form) : {};

  function close(nextOpen: boolean) {
    if (!nextOpen) {
      setForm(empty);
      setShowErrors(false);
      addUser.reset();
    }
    onOpenChange(nextOpen);
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    setShowErrors(true);
    if (Object.values(findErrors(form)).some(Boolean)) return;
    addUser.mutate(form, {
      onSuccess: (user) => {
        toast.success(t.team.added(user.name));
        close(false);
      },
    });
  }

  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t.team.addTitle}</DialogTitle>
          <DialogDescription>{t.team.addText}</DialogDescription>
        </DialogHeader>
        <form noValidate onSubmit={submit} className="grid gap-5">
          <FormField label={t.fields.name} error={errors.name}>
            {(field) => <Input {...field} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />}
          </FormField>
          <FormField label={t.fields.email} error={errors.email}>
            {(field) => (
              <Input
                {...field}
                type="email"
                autoComplete="off"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
              />
            )}
          </FormField>
          <FormField label={t.fields.role}>
            {(field) => (
              <Select value={form.role} onValueChange={(role) => setForm({ ...form, role: role as Role })}>
                <SelectTrigger {...field}>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {roles.map((role) => (
                    <SelectItem key={role} value={role}>
                      {t.roles[role]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          </FormField>
          <FormField
            label={t.fields.temporaryPassword}
            help={t.team.temporaryPasswordHelp}
            error={errors.temporary_password}
          >
            {(field) => (
              <PasswordInput
                {...field}
                autoComplete="new-password"
                value={form.temporary_password}
                onChange={(e) => setForm({ ...form, temporary_password: e.target.value })}
              />
            )}
          </FormField>
          <FormError message={addUser.error?.message} />
          <DialogFooter>
            <Button type="button" variant="subtle" onClick={() => close(false)}>
              {t.common.cancel}
            </Button>
            <Button type="submit" variant="primary" loading={addUser.isPending}>
              {t.team.addPerson}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
