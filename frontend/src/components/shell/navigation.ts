import { HistoryIcon, HomeIcon, type LucideIcon, PackageIcon, SettingsIcon, UsersIcon } from "lucide-react";

import type { Role } from "@/api/users";
import { t } from "@/i18n";

type NavItem = { to: string; label: string; icon: LucideIcon; roles: Role[] };

// The menu. Only pages that exist, and only for roles allowed to open them (the server checks too).
export const navItems: NavItem[] = [
  { to: "/", label: t.nav.home, icon: HomeIcon, roles: ["owner", "manager", "staff"] },
  { to: "/stock", label: t.nav.stock, icon: PackageIcon, roles: ["owner", "manager", "staff"] },
  { to: "/activity", label: t.nav.activity, icon: HistoryIcon, roles: ["owner", "manager"] },
  { to: "/team", label: t.nav.team, icon: UsersIcon, roles: ["owner"] },
  { to: "/settings", label: t.nav.settings, icon: SettingsIcon, roles: ["owner"] },
];

// Each page names itself in the router (`handle`); the top bar and the browser tab show it.
export type PageHandle = { title: keyof typeof t.nav };
