import { ShieldIcon } from "lucide-react";
import { Link, Outlet } from "react-router";

import { useSignedIn } from "@/components/SignedIn";
import type { Role } from "@/api/users";
import { EmptyState } from "@/components/EmptyState";
import { Button } from "@/components/ui/button";
import { t } from "@/i18n";

// Says exactly who can: the same two combinations the server itself checks (app/auth/permissions.py).
function whoCanLabel(roles: Role[]): string {
  if (roles.length === 1 && roles[0] === "owner") return t.common.onlyOwner;
  if (roles.includes("owner") && roles.includes("manager")) return t.common.onlyOwnerOrManager;
  return t.common.noAccess;
}

// Pages for some roles only. Others see a plain "no access" message (the server blocks them too).
export function RequireRole({ roles }: { roles: Role[] }) {
  const role = useSignedIn().user.role;

  if (!roles.includes(role)) {
    return (
      <EmptyState
        icon={ShieldIcon}
        title={whoCanLabel(roles)}
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
