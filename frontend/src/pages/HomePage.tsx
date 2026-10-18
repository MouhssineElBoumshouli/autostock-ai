import { UsersIcon } from "lucide-react";
import { Link, useNavigate } from "react-router";

import { useLogout, useMe } from "@/api/auth";
import { CenteredCard } from "@/components/CenteredCard";
import { ServerStatus } from "@/components/ServerStatus";
import { Button } from "@/components/ui/button";
import { t } from "@/i18n";

// Temporary home until the app layout arrives in Step 1d.
export function HomePage() {
  const me = useMe().data!;
  const logout = useLogout();
  const navigate = useNavigate();

  return (
    <CenteredCard title={t.appName} subtitle={t.tagline}>
      <div className="grid gap-6">
        <p className="text-sm text-muted-foreground">
          {t.home.signedInAs}{" "}
          <span className="font-medium text-foreground">{me.user.name}</span> ·{" "}
          {t.roles[me.user.role]} · {me.organization.name}
        </p>
        <div className="border-t pt-6">
          <ServerStatus />
        </div>
        <div className="flex flex-wrap gap-3">
          {me.user.role === "owner" && (
            <Button variant="primary" asChild>
              <Link to="/team">
                <UsersIcon aria-hidden="true" />
                {t.home.manageTeam}
              </Link>
            </Button>
          )}
          <Button variant="secondary" asChild>
            <Link to="/change-password">{t.home.changePassword}</Link>
          </Button>
          <Button
            variant="subtle"
            loading={logout.isPending}
            onClick={() => logout.mutate(undefined, { onSuccess: () => navigate("/login", { replace: true }) })}
          >
            {t.home.logOut}
          </Button>
        </div>
      </div>
    </CenteredCard>
  );
}
