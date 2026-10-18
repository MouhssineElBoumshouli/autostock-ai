import { ShieldIcon } from "lucide-react";
import { Link, Navigate, Outlet, useLocation } from "react-router";

import { useMe } from "@/api/auth";
import type { Role } from "@/api/users";
import { CenteredCard } from "@/components/CenteredCard";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { t } from "@/i18n";

// Wraps every private page. Not logged in: go to login, then come back here.
// With `roles`: people with another role see a "no access" message (the server blocks them too).
export function RequireLogin({ roles }: { roles?: Role[] }) {
  const me = useMe();
  const location = useLocation();

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
    const next = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/login?next=${next}`} replace />;
  }
  if (roles && !roles.includes(me.data.user.role)) {
    return (
      <main className="flex min-h-screen items-center justify-center px-4">
        <EmptyState
          icon={ShieldIcon}
          title={t.team.noAccess}
          action={
            <Button variant="primary" asChild>
              <Link to="/">{t.common.goHome}</Link>
            </Button>
          }
        />
      </main>
    );
  }
  return <Outlet />;
}
