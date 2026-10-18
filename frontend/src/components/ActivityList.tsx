import type { ActivityItem } from "@/api/activity";
import { Skeleton } from "@/components/ui/skeleton";
import { activitySentence } from "@/lib/activitySentence";
import { formatDateTime, formatTimeAgo, initials } from "@/lib/format";

// Shop history as plain sentences: who, what, and when ("2 hours ago", full date on hover).
export function ActivityList({
  items,
  loading = false,
  loadingRows = 5,
}: {
  items: ActivityItem[];
  loading?: boolean;
  loadingRows?: number;
}) {
  if (loading) {
    return (
      <ul aria-busy="true" className="divide-y">
        {Array.from({ length: loadingRows }, (_, index) => (
          <li key={index} className="flex items-center gap-3 px-6 py-4">
            <Skeleton className="size-9 shrink-0 rounded-full" />
            <div className="grid flex-1 gap-2">
              <Skeleton className="h-4 w-3/4" />
              <Skeleton className="h-3 w-24" />
            </div>
          </li>
        ))}
      </ul>
    );
  }

  return (
    <ul className="divide-y">
      {items.map((item) => (
        <li key={item.id} className="flex items-start gap-3 px-6 py-4">
          <span
            aria-hidden="true"
            className="flex size-9 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-semibold text-foreground"
          >
            {initials(item.actor?.name ?? "?")}
          </span>
          <div className="grid min-w-0 gap-0.5">
            <p className="text-sm">{activitySentence(item)}</p>
            <time dateTime={item.created_at} title={formatDateTime(item.created_at)} className="w-fit text-xs text-muted-foreground">
              {formatTimeAgo(item.created_at)}
            </time>
          </div>
        </li>
      ))}
    </ul>
  );
}
