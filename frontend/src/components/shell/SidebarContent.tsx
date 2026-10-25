import { useSignedIn } from "@/components/SignedIn";
import { t } from "@/i18n";

import { SidebarNav } from "./SidebarNav";
import { UserMenu } from "./UserMenu";

// Logo, menu, and the logged-in person. Used by the drawer (desktop), the rail (tablet)
// and the modal drawer (phone).
export function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const shop = useSignedIn().organization.name;

  return (
    <div className="flex h-full flex-col gap-4 p-3 md:max-xl:items-center md:max-xl:px-0">
      <div className="flex min-h-14 items-center gap-3 px-4 md:max-xl:justify-center md:max-xl:px-0">
        <img src="/favicon.svg" alt="" className="size-9 shrink-0" />
        <span className="grid min-w-0 md:max-xl:sr-only">
          <span className="text-title-medium">{t.appName}</span>
          <span dir="auto" className="truncate text-body-small text-on-surface-variant">
            {shop}
          </span>
        </span>
      </div>
      <SidebarNav onNavigate={onNavigate} />
      <div className="mt-auto border-t border-outline-variant pt-3 md:max-xl:border-0">
        <UserMenu onNavigate={onNavigate} />
      </div>
    </div>
  );
}
