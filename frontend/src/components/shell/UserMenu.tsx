import { ChevronsUpDownIcon, KeyRoundIcon, LogOutIcon } from "lucide-react";
import { Link, useNavigate } from "react-router";

import { useChooseLanguage, useLogout } from "@/api/auth";
import { useSignedIn } from "@/components/SignedIn";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { isLanguage, language, languageNames, languages, showLanguage, t } from "@/i18n";
import { initials } from "@/lib/format";

// The logged-in person at the bottom of the menu, with their language, Change password and Log out.
// On the tablet rail only the round avatar shows.
export function UserMenu({ onNavigate }: { onNavigate?: () => void }) {
  const user = useSignedIn().user;
  const logout = useLogout();
  const chooseLanguage = useChooseLanguage();

  function pickLanguage(value: string) {
    if (!isLanguage(value) || value === language) return;
    chooseLanguage.mutate(value, { onSuccess: () => showLanguage(value) });
  }
  const navigate = useNavigate();

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        aria-label={t.account.menuLabel(user.name)}
        className="state-layer flex w-full items-center gap-3 rounded-full p-2 text-start md:max-xl:w-auto"
      >
        <span
          aria-hidden="true"
          className="flex size-10 shrink-0 items-center justify-center rounded-full bg-primary-container text-title-small text-on-primary-container"
        >
          {initials(user.name)}
        </span>
        <span className="grid min-w-0 flex-1 md:max-xl:hidden">
          <span className="truncate text-label-large">{user.name}</span>
          <span className="truncate text-body-small text-on-surface-variant">{t.roles[user.role]}</span>
        </span>
        <ChevronsUpDownIcon aria-hidden="true" className="me-2 size-5 shrink-0 text-on-surface-variant md:max-xl:hidden" />
      </DropdownMenuTrigger>
      <DropdownMenuContent side="top" align="start">
        <DropdownMenuLabel>{t.account.language}</DropdownMenuLabel>
        <DropdownMenuRadioGroup value={language} onValueChange={pickLanguage}>
          {languages.map((choice) => (
            <DropdownMenuRadioItem key={choice} value={choice} lang={choice} disabled={chooseLanguage.isPending}>
              {languageNames[choice]}
            </DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
        <DropdownMenuSeparator />
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
