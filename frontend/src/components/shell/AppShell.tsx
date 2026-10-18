import { MenuIcon } from "lucide-react";
import { useEffect, useState } from "react";
import { Outlet, useMatches } from "react-router";

import { useSignedIn } from "@/components/SignedIn";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { t } from "@/i18n";

import type { PageHandle } from "./navigation";
import { SidebarContent } from "./SidebarContent";

// The frame around every logged-in page: sidebar (icons only on tablets, slide-in on phones) and top bar.
export function AppShell() {
  const me = useSignedIn();
  const [menuOpen, setMenuOpen] = useState(false);
  const handle = [...useMatches()].reverse().find((match) => match.handle)?.handle as PageHandle | undefined;
  const title = handle ? t.nav[handle.title] : t.appName;

  useEffect(() => {
    document.title = `${title} · ${t.appName}`;
  }, [title]);

  // Someone who must choose a password sees only that screen, without menus.
  if (me.user.must_change_password) return <Outlet />;

  return (
    <div className="min-h-screen md:flex">
      <a
        href="#content"
        className="sr-only z-50 rounded-lg border bg-card font-medium shadow-lg focus:not-sr-only focus:fixed focus:start-4 focus:top-4 focus:px-4 focus:py-2"
      >
        {t.nav.skipToContent}
      </a>

      <aside className="sticky top-0 hidden h-screen shrink-0 py-4 ps-4 md:block md:w-22 xl:w-72">
        <div className="h-full rounded-xl border bg-card">
          <SidebarContent />
        </div>
      </aside>

      <Sheet open={menuOpen} onOpenChange={setMenuOpen}>
        <SheetContent>
          <SheetTitle className="sr-only">{t.nav.mainMenu}</SheetTitle>
          <SidebarContent onNavigate={() => setMenuOpen(false)} />
        </SheetContent>
      </Sheet>

      <div className="min-w-0 flex-1">
        <header className="flex h-16 items-center gap-2 px-4 sm:px-6 md:h-20 lg:px-8">
          <Button
            variant="subtle"
            size="icon"
            className="-ms-2 md:hidden"
            aria-label={t.nav.openMenu}
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen(true)}
          >
            <MenuIcon aria-hidden="true" />
          </Button>
          <p className="min-w-0 truncate text-sm">
            <span className="text-muted-foreground">{me.organization.name}</span>
            <span aria-hidden="true" className="px-2 text-muted-foreground">
              /
            </span>
            <span className="font-medium">{title}</span>
          </p>
        </header>
        <main id="content" tabIndex={-1} className="mx-auto max-w-6xl px-4 pb-12 outline-none sm:px-6 lg:px-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
