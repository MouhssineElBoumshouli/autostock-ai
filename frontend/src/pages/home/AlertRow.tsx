import { toast } from "sonner";

import { type AlertGroup, type AlertStatus, useReviewAlert } from "@/api/alerts";
import { useSignedIn } from "@/components/SignedIn";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { t } from "@/i18n";
import { type AlertFacts, alertSentence } from "@/lib/alertSentence";
import { formatDateTime, formatTimeAgo } from "@/lib/format";

const statusVariant = { open: "neutral", looked_at: "success", not_a_problem: "neutral" } as const;

type AlertLike = AlertFacts & { id: string; part_name: string; branch_name: string; group?: AlertGroup };

// One alert: its sentence, which part and branch, and (for owners and managers) the two
// decisions. Used on the Today page (open alerts only) and the Alerts page (every status).
export function AlertRow({
  alert,
  canReview,
  status = "open",
  reviewedByName,
  reviewedAt,
}: {
  alert: AlertLike;
  canReview: boolean;
  status?: AlertStatus;
  reviewedByName?: string | null;
  reviewedAt?: string | null;
}) {
  const review = useReviewAlert();
  const currency = useSignedIn().organization.currency;

  function mark(next: "looked_at" | "not_a_problem") {
    review.mutate(
      { id: alert.id, status: next },
      {
        onSuccess: () => toast.success(next === "looked_at" ? t.home.lookedAtItDone : t.home.notAProblemDone),
        onError: (error) => toast.error(error.message),
      },
    );
  }

  return (
    <li className="grid gap-2 px-6 py-3 sm:flex sm:items-center sm:justify-between sm:gap-4">
      <div className="min-w-0 grid gap-0.5">
        {alert.group && <Badge variant="neutral">{t.alertsPage.groups[alert.group]}</Badge>}
        <p className="text-body-large">{alertSentence(alert, currency)}</p>
        <p className="text-body-small text-on-surface-variant">
          <bdi dir="auto">{alert.part_name}</bdi> · <bdi dir="auto">{alert.branch_name}</bdi>
        </p>
        {status !== "open" && reviewedByName && (
          <p className="text-body-small text-on-surface-variant">
            {t.alertsPage.markedBy(reviewedByName)}
            {reviewedAt && (
              <>
                {" · "}
                <time dateTime={reviewedAt} title={formatDateTime(reviewedAt)}>
                  {formatTimeAgo(reviewedAt)}
                </time>
              </>
            )}
          </p>
        )}
      </div>
      <div className="flex shrink-0 items-center gap-2">
        {status !== "open" && <Badge variant={statusVariant[status]}>{t.alertsPage.statuses[status]}</Badge>}
        {canReview && status === "open" && (
          <>
            <Button size="sm" variant="outlined" disabled={review.isPending} onClick={() => mark("not_a_problem")}>
              {t.home.notAProblem}
            </Button>
            <Button size="sm" variant="tonal" disabled={review.isPending} onClick={() => mark("looked_at")}>
              {t.home.lookedAtIt}
            </Button>
          </>
        )}
      </div>
    </li>
  );
}
