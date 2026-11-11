import { CheckCircle2Icon, CircleIcon } from "lucide-react";
import { Link } from "react-router";

import { type StepKey, useSetStartHereHidden, useStartHere } from "@/api/startHere";
import { Button } from "@/components/ui/button";
import { Card, CardAction, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useSignedIn } from "@/components/SignedIn";
import { t } from "@/i18n";

const STEP_LINKS: Record<StepKey, string> = {
  branches: "/settings",
  import_parts: "/stock/import?kind=parts",
  import_sales: "/stock/import?kind=sales",
  suppliers: "/settings",
  team: "/team",
};

// A real, brand-new shop (never the demo) sees this instead of Today's otherwise-empty sections,
// until every step is done or an owner/manager hides it. Each tick comes from real data.
export function StartHereChecklist() {
  const me = useSignedIn();
  const canReview = me.user.role !== "staff";
  const startHere = useStartHere();
  const setHidden = useSetStartHereHidden();
  const words = t.startHere;

  if (me.organization.is_demo || !canReview) return null;
  if (startHere.isPending) {
    return (
      <Card>
        <CardContent aria-busy="true">
          <Skeleton className="h-32 w-full" />
        </CardContent>
      </Card>
    );
  }
  if (!startHere.data || startHere.data.hidden || startHere.data.all_done) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>{words.title}</CardTitle>
        <CardAction>
          <Button variant="text" size="sm" loading={setHidden.isPending} onClick={() => setHidden.mutate(true)}>
            {words.hide}
          </Button>
        </CardAction>
      </CardHeader>
      <CardContent className="grid gap-1">
        <p className="pb-2 text-body-medium text-on-surface-variant">{words.subtitle}</p>
        <ul className="grid gap-1">
          {startHere.data.steps.map((step) => (
            <li key={step.key}>
              <Link
                to={STEP_LINKS[step.key]}
                className="flex items-start gap-3 rounded-md p-3 transition-colors hover:bg-on-surface/8"
              >
                {step.done ? (
                  <CheckCircle2Icon aria-hidden="true" className="mt-0.5 size-5 shrink-0 text-primary" />
                ) : (
                  <CircleIcon aria-hidden="true" className="mt-0.5 size-5 shrink-0 text-on-surface-variant" />
                )}
                <span className="grid gap-0.5">
                  <span className={step.done ? "text-title-small text-on-surface-variant line-through" : "text-title-small"}>
                    {words.steps[step.key].title}
                  </span>
                  <span className="text-body-small text-on-surface-variant">{words.steps[step.key].text}</span>
                </span>
              </Link>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}
