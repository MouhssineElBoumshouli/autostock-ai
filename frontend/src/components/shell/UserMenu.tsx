import { ChevronsUpDownIcon, KeyRoundIcon, LogOutIcon } from "lucide-react";
import { Link, useNavigate } from "react-router";

import { useLogout } from "@/api/auth";
import { useSignedIn } from "@/components/SignedIn";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { t } from "@/i18n";
import { initials } from "@/lib/format";

// The logged-in person at the bottom of the sidebar, with Change password and Log out.
export function UserMenu({ onNavigate }: { onNavigate?: () => void }) {
  const user = useSignedIn().user;
  const logout = useLogout();
  const navigate = useNavigate();

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        aria-label={t.account.menuLabel(user.name)}
        className="flex w-full items-center gap-3 rounded-lg p-2 text-start transition-colors hover:bg-muted md:max-xl:justify-center"
      >
        <span
          aria-hidden="true"
          className="flex size-9 shrink-0 items-center justify-center rounded-full bg-accent text-xs font-semibold text-accent-foreground"
        >
          {initials(user.name)}
        </span>
        <span className="grid min-w-0 flex-1 md:max-xl:hidden">
          <span className="truncate text-sm font-medium">{user.name}</span>
          <span className="truncate text-xs text-muted-foreground">{t.roles[user.role]}</span>
        </span>
        <ChevronsUpDownIcon aria-hidden="true" className="size-4 shrink-0 text-muted-foreground md:max-xl:hidden" />
      </DropdownMenuTrigger>
      <DropdownMenuContent side="top" align="start">
        <DropdownMenuItem asChild>
          <Link to="/change-password" onClick={onNavigate}>
            <KeyRoundIcon aria-hidden="true" />
            {t.account.changePassword}
          </Link>
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          onSelect={() => logout.mutate(undefined, { onSuccess: () => navigate("/login", { replace: true }) })}
        >
          <LogOutIcon aria-hidden="true" />
          {t.account.logOut}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
