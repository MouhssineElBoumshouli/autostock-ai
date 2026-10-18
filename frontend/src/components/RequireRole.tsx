import { ShieldIcon } from "lucide-react";
import { Link, Outlet } from "react-router";

import { useSignedIn } from "@/components/SignedIn";
import type { Role } from "@/api/users";
import { EmptyState } from "@/components/EmptyState";
import { Button } from "@/components/ui/button";
import { t } from "@/i18n";

// Pages for some roles only. Others see a plain "no access" message (the server blocks them too).
export function RequireRole({ roles }: { roles: Role[] }) {
  const role = useSignedIn().user.role;

  if (!roles.includes(role)) {
    return (
      <EmptyState
        icon={ShieldIcon}
        title={t.common.noAccess}
        action={
          <Button variant="filled" asChild>
            <Link to="/">{t.common.goHome}</Link>
          </Button>
        }
      />
    );
  }
  return <Outlet />;
}
