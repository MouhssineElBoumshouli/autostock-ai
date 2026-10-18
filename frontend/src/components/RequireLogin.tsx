import { Navigate, Outlet, useLocation } from "react-router";

import { useMe } from "@/api/auth";
import { CenteredCard } from "@/components/CenteredCard";
import { ErrorState } from "@/components/ErrorState";
import { SignedInContext } from "@/components/SignedIn";
import { Skeleton } from "@/components/ui/skeleton";
import { t } from "@/i18n";

// Wraps every private page. Not logged in: go to login, then come back here.
export function RequireLogin() {
  const me = useMe();
  const location = useLocation();
  const here = encodeURIComponent(location.pathname + location.search);

  if (me.isPending) {
    return (
      <CenteredCard title={t.appName}>
        <div className="grid gap-3" aria-busy="true">
          <Skeleton className="h-4 w-2/3" />
          <Skeleton className="h-4 w-1/2" />
        </div>
      </CenteredCard>
    );
  }
  if (me.isError) {
    return <ErrorState onRetry={() => me.refetch()} retrying={me.isFetching} />;
  }
  if (me.data === null) {
    return <Navigate to={`/login?next=${here}`} replace />;
  }
  // The owner set this person's password: they must choose their own before anything else.
  if (me.data.user.must_change_password && location.pathname !== "/change-password") {
    return <Navigate to={`/change-password?next=${here}`} replace />;
  }
  return (
    <SignedInContext value={me.data}>
      <Outlet />
    </SignedInContext>
  );
}
