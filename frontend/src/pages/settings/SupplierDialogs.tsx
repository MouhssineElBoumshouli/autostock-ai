import type { UseMutationResult } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { toast } from "sonner";

import type { Supplier, SupplierDetails } from "@/api/suppliers";
import { FormError } from "@/components/FormError";
import { FormField } from "@/components/FormField";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { t } from "@/i18n";
import { deliveryTimeText } from "@/lib/deliveryTime";
import { formatNumber } from "@/lib/format";
import { requiredError } from "@/lib/validation";

type Form = { name: string; phone: string; email: string; deliveryDays: string };

function parseDeliveryDays(text: string): number | null | "invalid" {
  const cleaned = text.trim();
  if (!cleaned) return null;
  if (!/^\d+$/.test(cleaned)) return "invalid";
  return Number(cleaned);
}

// Phone, e-mail and delivery time are the same two fields on "Add" and "Edit", so one form
// serves both -- "Add" also asks for a name, "Edit" keeps the name as a plain heading instead.
function DetailsFields({ form, setForm }: { form: Form; setForm: (form: Form) => void }) {
  const words = t.settings.suppliers;
  return (
    <>
      <FormField label={words.phone}>
        {(field) => <Input {...field} value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />}
      </FormField>
      <FormField label={words.email}>
        {(field) => (
          <Input {...field} type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
        )}
      </FormField>
      <FormField label={words.deliveryDays} help={words.deliveryDaysHelp}>
        {(field) => (
          <Input
            {...field}
            inputMode="numeric"
            value={form.deliveryDays}
            onChange={(e) => setForm({ ...form, deliveryDays: e.target.value })}
          />
        )}
      </FormField>
    </>
  );
}

export function AddSupplierDialog({
  add,
}: {
  add: UseMutationResult<Supplier, Error, { name: string } & SupplierDetails>;
}) {
  const words = t.settings.suppliers;
  const empty: Form = { name: "", phone: "", email: "", deliveryDays: "" };
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(empty);
  const [showErrors, setShowErrors] = useState(false);
  const deliveryDays = parseDeliveryDays(form.deliveryDays);

  function changeOpen(next: boolean) {
    if (next) setForm(empty);
    setShowErrors(false);
    add.reset();
    setOpen(next);
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    setShowErrors(true);
    if (requiredError(form.name) || deliveryDays === "invalid") return;
    add.mutate(
      { name: form.name.trim(), phone: form.phone.trim() || null, email: form.email.trim() || null, delivery_days: deliveryDays },
      { onSuccess: (supplier) => { toast.success(words.added(supplier.name)); changeOpen(false); } },
    );
  }

  return (
    <Dialog open={open} onOpenChange={changeOpen}>
      <DialogTrigger asChild>
        <Button variant="tonal" size="sm">
          {words.add}
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{words.addTitle}</DialogTitle>
        </DialogHeader>
        <form noValidate onSubmit={submit} className="grid gap-5">
          <FormField label={t.settings.entities.nameField} error={showErrors ? requiredError(form.name) : undefined}>
            {(field) => <Input {...field} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />}
          </FormField>
          <DetailsFields form={form} setForm={setForm} />
          <FormError message={add.error?.message} />
          <DialogFooter>
            <Button type="button" variant="text" onClick={() => changeOpen(false)}>
              {t.common.cancel}
            </Button>
            <Button type="submit" variant="filled" loading={add.isPending}>
              {t.common.save}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// The owner typed a delivery time and 3+ real deliveries say otherwise: say what they say, and
// one click goes back to automatic, which then follows those deliveries.
export function DeliveriesSayNote({
  supplier,
  save,
}: {
  supplier: Supplier;
  save: UseMutationResult<Supplier, Error, { id: string } & SupplierDetails>;
}) {
  const words = t.settings.suppliers;
  if (!supplier.deliveries_say) return null;
  const days = supplier.deliveries_say.days;

  function followDeliveries() {
    save.mutate(
      { id: supplier.id, phone: supplier.phone, email: supplier.email, delivery_days: null },
      { onSuccess: () => toast.success(words.detailsSaved) },
    );
  }

  return (
    <div className="flex w-full flex-wrap items-center gap-x-2 text-body-medium text-on-surface-variant">
      <span>{words.deliveriesSay(t.common.days(days, formatNumber(days)))}</span>
      <Button size="sm" variant="text" loading={save.isPending} onClick={followDeliveries}>
        {words.useDeliveries}
      </Button>
    </div>
  );
}

export function DeliveryTimeButton({
  supplier,
  save,
}: {
  supplier: Supplier;
  save: UseMutationResult<Supplier, Error, { id: string } & SupplierDetails>;
}) {
  const words = t.settings.suppliers;
  const toForm = (): Form => ({
    name: supplier.name, phone: supplier.phone ?? "", email: supplier.email ?? "",
    deliveryDays: supplier.delivery_days === null ? "" : String(supplier.delivery_days),
  });
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(toForm);
  const deliveryDays = parseDeliveryDays(form.deliveryDays);

  function changeOpen(next: boolean) {
    if (next) setForm(toForm());
    save.reset();
    setOpen(next);
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    if (deliveryDays === "invalid") return;
    save.mutate(
      { id: supplier.id, phone: form.phone.trim() || null, email: form.email.trim() || null, delivery_days: deliveryDays },
      { onSuccess: () => { toast.success(words.detailsSaved); changeOpen(false); } },
    );
  }

  return (
    <Dialog open={open} onOpenChange={changeOpen}>
      <DialogTrigger asChild>
        <Button size="sm" variant="text" className="h-auto min-h-8 max-w-full whitespace-normal text-start">
          {deliveryTimeText(supplier.delivery.days, supplier.delivery.source, supplier.delivery.learned_from)}
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{words.deliveryTimeTitle(supplier.name)}</DialogTitle>
        </DialogHeader>
        <form noValidate onSubmit={submit} className="grid gap-5">
          <DetailsFields form={form} setForm={setForm} />
          <FormError message={save.error?.message} />
          <DialogFooter>
            <Button type="button" variant="text" onClick={() => changeOpen(false)}>
              {t.common.cancel}
            </Button>
            <Button type="submit" variant="filled" loading={save.isPending}>
              {t.common.save}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
