import { useSignedIn } from "@/components/SignedIn";
import { t } from "@/i18n";

import { SidebarNav } from "./SidebarNav";
import { UserMenu } from "./UserMenu";

// Logo, menu, and the logged-in person. Used by the drawer (desktop), the rail (tablet)
// and the modal drawer (phone). It fits the screen's height: when the menu is longer than the space
// left, the menu scrolls inside, and the person's button stays visible at the bottom.
export function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const shop = useSignedIn().organization.name;

  return (
    <div className="flex h-full min-h-0 flex-col gap-4 p-3 md:max-xl:items-center md:max-xl:px-0">
      <div className="flex min-h-14 shrink-0 items-center gap-3 px-4 md:max-xl:justify-center md:max-xl:px-0">
        <img src="/logo-mark.svg" alt="" className="h-8 w-10 shrink-0" />
        <span className="grid min-w-0 md:max-xl:sr-only">
          <span className="text-title-medium">{t.appName}</span>
          <span dir="auto" className="truncate text-body-small text-on-surface-variant">
            {shop}
          </span>
        </span>
      </div>
      <div className="-mx-1 min-h-0 flex-1 overflow-y-auto px-1 md:max-xl:w-full">
        <SidebarNav onNavigate={onNavigate} />
      </div>
      <div className="shrink-0 border-t border-outline-variant pt-3 md:max-xl:border-0">
        <UserMenu onNavigate={onNavigate} />
      </div>
    </div>
  );
}
