import { t } from "@/i18n";

import { SidebarNav } from "./SidebarNav";
import { UserMenu } from "./UserMenu";

// Logo, menu, and the logged-in person. Used by the fixed sidebar and the phone slide-in menu.
export function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <div className="flex h-full flex-col gap-6 p-3">
      <div className="flex h-12 items-center gap-3 px-2 md:max-xl:justify-center md:max-xl:px-0">
        <img src="/favicon.svg" alt="" className="size-8 shrink-0" />
        <span className="text-lg font-semibold tracking-tight md:max-xl:sr-only">{t.appName}</span>
      </div>
      <SidebarNav onNavigate={onNavigate} />
      <div className="mt-auto border-t pt-3">
        <UserMenu onNavigate={onNavigate} />
      </div>
    </div>
  );
}
