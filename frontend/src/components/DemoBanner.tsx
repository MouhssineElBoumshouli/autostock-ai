import { InfoIcon } from "lucide-react";

import { useSignedIn } from "@/components/SignedIn";
import { t } from "@/i18n";

// A thin reminder on every page of a demo shop, so nobody mistakes made-up data for a real shop.
export function DemoBanner() {
  const isDemo = useSignedIn().organization.is_demo;
  if (!isDemo) return null;

  return (
    <p className="flex items-center justify-center gap-2 bg-tertiary-container px-4 py-1.5 text-center text-body-small text-on-tertiary-container">
      <InfoIcon aria-hidden="true" className="size-4 shrink-0" />
      {t.demo.banner}
    </p>
  );
}
