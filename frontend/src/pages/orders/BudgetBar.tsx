import { useState } from "react";

import type { OrderRun } from "@/api/orders";
import { useSignedIn } from "@/components/SignedIn";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { t } from "@/i18n";
import { formatMoney, moneyInputValue, parseMoneyInput } from "@/lib/format";

// A budget limit (optional) and the button that asks AutoStock to work out what to order.
export function BudgetBar({
  run,
  onRun,
  loading,
}: {
  run: OrderRun | null | undefined;
  onRun: (budget: number | null) => void;
  loading: boolean;
}) {
  const currency = useSignedIn().organization.currency;
  const [budget, setBudget] = useState(moneyInputValue(run?.budget ?? null));
  const parsed = parseMoneyInput(budget);

  return (
    <Card>
      <CardContent className="flex flex-wrap items-end gap-4">
        <div className="grid gap-1">
          <label htmlFor="budget" className="text-body-small text-on-surface-variant">
            {t.orders.budget.label}
          </label>
          <Input
            id="budget"
            inputMode="decimal"
            placeholder={t.orders.budget.placeholder}
            value={budget}
            onChange={(event) => setBudget(event.target.value)}
            className="h-10 w-40"
          />
        </div>
        <Button variant="filled" loading={loading} disabled={parsed === "invalid"} onClick={() => onRun(parsed === "invalid" ? null : parsed)}>
          {t.orders.getSuggestions}
        </Button>
        {run && (
          <div className="ms-auto grid gap-0.5 text-end text-body-medium">
            <span className="text-on-surface-variant">{t.orders.budget.suggestedTotal}: {formatMoney(run.suggested_cost, currency)}</span>
            <span className="font-medium">{t.orders.budget.keptTotal}: {formatMoney(run.kept_cost, currency)}</span>
          </div>
        )}
      </CardContent>
      <CardContent className="pt-0 text-body-small text-on-surface-variant">{t.orders.budget.help}</CardContent>
    </Card>
  );
}
