import { cn } from "cn";
import { NavLink } from "react-router";

import { useSignedIn } from "@/components/SignedIn";
import { t } from "@/i18n";

import { navItems } from "./navigation";

// The menu links. On tablets (md to xl) only icons show; the label stays for screen readers and as a tooltip.
export function SidebarNav({ onNavigate }: { onNavigate?: () => void }) {
  const role = useSignedIn().user.role;

  return (
    <nav aria-label={t.nav.mainMenu}>
      <ul className="grid gap-1">
        {navItems
          .filter((item) => item.roles.includes(role))
          .map(({ to, label, icon: Icon }) => (
            <li key={to}>
              <NavLink
                to={to}
                end={to === "/"}
                title={label}
                onClick={onNavigate}
                className={({ isActive }) =>
                  cn(
                    "relative flex h-11 items-center gap-3 rounded-lg px-3 text-sm font-medium transition-colors md:max-xl:justify-center md:max-xl:px-0",
                    isActive
                      ? "bg-accent text-accent-foreground before:absolute before:inset-y-2.5 before:start-0 before:w-1 before:rounded-full before:bg-primary"
                      : "text-muted-foreground hover:bg-muted hover:text-foreground",
                  )
                }
              >
                <Icon aria-hidden="true" className="size-5 shrink-0" />
                <span className="md:max-xl:sr-only">{label}</span>
              </NavLink>
            </li>
          ))}
      </ul>
    </nav>
  );
}
