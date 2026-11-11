import { cn } from "cn";
import { NavLink } from "react-router";

import { useSignedIn } from "@/components/SignedIn";
import { t } from "@/i18n";

import { navItems } from "./navigation";

// The menu links, in two Material 3 shapes:
// - navigation drawer (desktop, and the phone menu): a row with icon and label, a pill when active;
// - navigation rail (tablets, md to xl): the icon in a small pill with the label under it.
export function SidebarNav({ onNavigate }: { onNavigate?: () => void }) {
  const role = useSignedIn().user.role;

  return (
    <nav aria-label={t.nav.mainMenu}>
      <ul className="grid gap-1 md:max-xl:gap-3">
        {navItems
          .filter((item) => item.roles.includes(role))
          .map(({ to, label, icon: Icon }) => (
            <li key={to}>
              <NavLink
                to={to}
                end={to === "/"}
                onClick={onNavigate}
                className={({ isActive }) =>
                  cn(
                    "group flex h-14 items-center gap-3 rounded-full px-4 text-label-large transition-colors",
                    "md:max-xl:h-auto md:max-xl:flex-col md:max-xl:gap-1 md:max-xl:rounded-none md:max-xl:px-0 md:max-xl:text-label-medium",
                    isActive
                      ? "text-on-secondary-container max-md:bg-secondary-container xl:bg-secondary-container md:max-xl:text-on-surface"
                      : "text-on-surface-variant max-md:hover:bg-on-surface/8 xl:hover:bg-on-surface/8",
                  )
                }
              >
                {({ isActive }) => (
                  <>
                    <span
                      className={cn(
                        "flex shrink-0 items-center justify-center transition-colors md:max-xl:h-8 md:max-xl:w-14 md:max-xl:rounded-full",
                        isActive
                          ? "md:max-xl:bg-secondary-container md:max-xl:text-on-secondary-container"
                          : "md:max-xl:group-hover:bg-on-surface/8",
                      )}
                    >
                      <Icon aria-hidden="true" className="size-6" />
                    </span>
                    <span>{label}</span>
                  </>
                )}
              </NavLink>
            </li>
          ))}
      </ul>
    </nav>
  );
}
