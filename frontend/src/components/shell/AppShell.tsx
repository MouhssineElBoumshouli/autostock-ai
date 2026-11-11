import { MenuIcon } from "lucide-react";
import { useEffect, useState } from "react";
import { Outlet, useLocation, useMatches } from "react-router";

import { DemoBanner } from "@/components/DemoBanner";
import { PageErrorBoundary } from "@/components/PageErrorBoundary";
import { useSignedIn } from "@/components/SignedIn";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { t } from "@/i18n";

import type { PageHandle } from "./navigation";
import { SidebarContent } from "./SidebarContent";

// The frame around every logged-in page (Material 3):
// navigation drawer on desktop, navigation rail on tablets, modal drawer on phones, and a top app bar.
export function AppShell() {
  const me = useSignedIn();
  const location = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);
  const handle = [...useMatches()].reverse().find((match) => match.handle)?.handle as PageHandle | undefined;
  const title = handle ? t.nav[handle.title] : t.appName;

  useEffect(() => {
    document.title = `${title} · ${t.appName}`;
  }, [title]);

  // Someone who must choose a password sees only that screen, without menus.
  if (me.user.must_change_password) return <Outlet />;

  return (
    <div className="flex min-h-screen flex-col">
      <div className="md:flex md:flex-1">
        <a
          href="#content"
          className="sr-only z-50 rounded-full bg-inverse-surface text-label-large text-inverse-on-surface shadow-elevation-3 focus:not-sr-only focus:fixed focus:start-4 focus:top-4 focus:px-6 focus:py-2.5"
        >
          {t.nav.skipToContent}
        </a>

        {/* Exactly the screen's height, so the person's button at its bottom is always in view. */}
        <aside className="sticky top-0 hidden h-dvh shrink-0 bg-surface-container-low md:block md:w-20 xl:w-80">
          <SidebarContent />
        </aside>

        <Sheet open={menuOpen} onOpenChange={setMenuOpen}>
          <SheetContent>
            <SheetTitle className="sr-only">{t.nav.mainMenu}</SheetTitle>
            <SidebarContent onNavigate={() => setMenuOpen(false)} />
          </SheetContent>
        </Sheet>

        <div className="min-w-0 flex-1">
          <DemoBanner />
          <header className="sticky top-0 z-10 flex h-16 items-center gap-1 bg-surface px-2 sm:px-4 lg:px-6">
            <Button
              variant="text"
              size="icon"
              className="md:hidden"
              aria-label={t.nav.openMenu}
              aria-expanded={menuOpen}
              onClick={() => setMenuOpen(true)}
            >
              <MenuIcon aria-hidden="true" />
            </Button>
            {/* The shop's name shrinks first (cut at its own end, in its own direction); the page name stays whole. */}
            <p className="flex min-w-0 items-center px-2 text-title-large">
              <span dir="auto" className="min-w-0 truncate text-on-surface-variant max-sm:hidden">
                {me.organization.name}
              </span>
              <span aria-hidden="true" className="shrink-0 px-2 text-on-surface-variant max-sm:hidden">
                /
              </span>
              <span className="min-w-0 truncate">{title}</span>
            </p>
          </header>
          <main id="content" tabIndex={-1} className="mx-auto max-w-6xl px-4 pt-2 pb-12 outline-none sm:px-6 lg:px-8">
            <PageErrorBoundary key={location.pathname}>
              <Outlet />
            </PageErrorBoundary>
          </main>
        </div>
      </div>
    </div>
  );
}
