import { type FormEvent, useState } from "react";
import { toast } from "sonner";

import { type PartDetail, useChangePart, useStockFilterChoices } from "@/api/stock";
import { CheckboxField } from "@/components/CheckboxField";
import { FormError } from "@/components/FormError";
import { FormField } from "@/components/FormField";
import { useSignedIn } from "@/components/SignedIn";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { SheetTitle } from "@/components/ui/sheet";
import { t } from "@/i18n";
import { moneyInputValue, parseMoneyInput } from "@/lib/format";
import { requiredError } from "@/lib/validation";

const NO_SUPPLIER = "none";

function wholeNumber(text: string): number | "invalid" {
  return /^\d+$/.test(text.trim()) ? Number(text.trim()) : "invalid";
}

// Edit one part: names, prices, minimum, supplier, active, and how many are in each branch.
export function PartEditForm({ part, onDone }: { part: PartDetail; onDone: () => void }) {
  const currency = useSignedIn().organization.currency;
  const suppliers = useStockFilterChoices().data?.suppliers ?? [];
  const changePart = useChangePart(part.id);
  const [form, setForm] = useState({
    name: part.name,
    brand: part.brand ?? "",
    category: part.category ?? "",
    oem_reference: part.oem_reference ?? "",
    unit_cost: moneyInputValue(part.unit_cost),
    sale_price: moneyInputValue(part.sale_price),
    min_stock: String(part.min_stock),
    supplier_id: part.supplier?.id ?? NO_SUPPLIER,
    is_active: part.is_active,
    stock: Object.fromEntries(part.stock.map((row) => [row.branch_id, String(row.quantity)])),
  });
  const [showErrors, setShowErrors] = useState(false);

  const unitCost = parseMoneyInput(form.unit_cost);
  const salePrice = parseMoneyInput(form.sale_price);
  const minStock = wholeNumber(form.min_stock);
  const errors = {
    name: requiredError(form.name),
    unit_cost: unitCost === "invalid" ? t.part.moneyError : undefined,
    sale_price: salePrice === "invalid" ? t.part.moneyError : undefined,
    min_stock: minStock === "invalid" ? t.part.quantityError : undefined,
    stock: Object.fromEntries(
      Object.entries(form.stock).map(([id, value]) => [id, wholeNumber(value) === "invalid" ? t.part.quantityError : undefined]),
    ),
  };
  const hasErrors =
    Boolean(errors.name || errors.unit_cost || errors.sale_price || errors.min_stock) ||
    Object.values(errors.stock).some(Boolean);
  const shown = (error: string | undefined) => (showErrors ? error : undefined);
  const text = (value: string) => value.trim() || null;

  function submit(event: FormEvent) {
    event.preventDefault();
    setShowErrors(true);
    if (hasErrors) return;
    changePart.mutate(
      {
        name: form.name.trim(),
        brand: text(form.brand),
        category: text(form.category),
        oem_reference: text(form.oem_reference),
        unit_cost: unitCost as number | null,
        sale_price: salePrice as number | null,
        min_stock: minStock as number,
        supplier_id: form.supplier_id === NO_SUPPLIER ? null : form.supplier_id,
        is_active: form.is_active,
        stock: Object.entries(form.stock).map(([branch_id, value]) => ({ branch_id, quantity: Number(value) })),
      },
      {
        onSuccess: () => {
          toast.success(t.part.saved);
          onDone();
        },
      },
    );
  }

  return (
    <form noValidate onSubmit={submit} className="flex min-h-full flex-col">
      <header className="border-b p-6">
        <SheetTitle className="text-lg font-semibold">{t.part.editTitle(part.name)}</SheetTitle>
        <p className="text-sm text-muted-foreground">{part.sku}</p>
      </header>

      <div className="grid flex-1 content-start gap-5 p-6">
        <FormField label={t.part.name} error={shown(errors.name)}>
          {(field) => <Input {...field} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />}
        </FormField>
        <div className="grid gap-5 sm:grid-cols-2">
          <FormField label={t.part.brand}>
            {(field) => <Input {...field} value={form.brand} onChange={(e) => setForm({ ...form, brand: e.target.value })} />}
          </FormField>
          <FormField label={t.part.category}>
            {(field) => (
              <Input {...field} value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} />
            )}
          </FormField>
        </div>
        <FormField label={t.part.oem}>
          {(field) => (
            <Input {...field} value={form.oem_reference} onChange={(e) => setForm({ ...form, oem_reference: e.target.value })} />
          )}
        </FormField>
        <div className="grid gap-5 sm:grid-cols-2">
          <FormField label={t.part.unitCost} help={t.part.moneyHelp(currency)} error={shown(errors.unit_cost)}>
            {(field) => (
              <Input
                {...field}
                inputMode="decimal"
                value={form.unit_cost}
                onChange={(e) => setForm({ ...form, unit_cost: e.target.value })}
              />
            )}
          </FormField>
          <FormField label={t.part.salePrice} help={t.part.moneyHelp(currency)} error={shown(errors.sale_price)}>
            {(field) => (
              <Input
                {...field}
                inputMode="decimal"
                value={form.sale_price}
                onChange={(e) => setForm({ ...form, sale_price: e.target.value })}
              />
            )}
          </FormField>
        </div>
        <FormField label={t.part.minStock} help={t.part.minStockHelp} error={shown(errors.min_stock)}>
          {(field) => (
            <Input
              {...field}
              inputMode="numeric"
              value={form.min_stock}
              onChange={(e) => setForm({ ...form, min_stock: e.target.value })}
            />
          )}
        </FormField>
        <FormField label={t.part.supplier}>
          {(field) => (
            <Select value={form.supplier_id} onValueChange={(supplier_id) => setForm({ ...form, supplier_id })}>
              <SelectTrigger {...field}>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={NO_SUPPLIER}>{t.part.noSupplier}</SelectItem>
                {suppliers.map((supplier) => (
                  <SelectItem key={supplier.id} value={supplier.id}>
                    {supplier.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        </FormField>

        <fieldset className="grid gap-3">
          <legend className="mb-2 text-sm font-semibold">{t.part.stockPerBranch}</legend>
          {part.stock.map((row) => (
            <FormField key={row.branch_id} label={row.branch} error={shown(errors.stock[row.branch_id])}>
              {(field) => (
                <Input
                  {...field}
                  inputMode="numeric"
                  value={form.stock[row.branch_id]}
                  onChange={(e) => setForm({ ...form, stock: { ...form.stock, [row.branch_id]: e.target.value } })}
                />
              )}
            </FormField>
          ))}
        </fieldset>

        <CheckboxField
          label={t.part.active}
          help={t.part.activeHelp}
          checked={form.is_active}
          onCheckedChange={(is_active) => setForm({ ...form, is_active })}
        />
        <FormError message={changePart.error?.message} />
      </div>

      <footer className="sticky bottom-0 flex justify-end gap-2 border-t bg-card p-4">
        <Button type="button" variant="subtle" onClick={onDone}>
          {t.common.cancel}
        </Button>
        <Button type="submit" variant="primary" loading={changePart.isPending}>
          {t.part.save}
        </Button>
      </footer>
    </form>
  );
}
