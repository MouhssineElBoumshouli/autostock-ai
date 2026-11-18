import { type ReactNode, useEffect } from "react";

import { t } from "@/i18n";

// A single card in the middle of the screen, with the logo. Used for setup, login and home.
export function CenteredCard({ title, subtitle, children }: { title: string; subtitle?: string; children: ReactNode }) {
  useEffect(() => {
    document.title = title === t.appName ? title : `${title} · ${t.appName}`;
  }, [title]);

  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-12">
      <section className="w-full max-w-md rounded-xl bg-surface-container-low p-6 shadow-elevation-1 [--field-bg:var(--color-surface-container-low)] sm:p-10">
        <img src="/logo-mark.svg" alt="" className="h-12 w-15" />
        <h1 className="mt-6 text-headline-small sm:text-headline-medium">{title}</h1>
        {subtitle && <p className="mt-2 text-body-large text-on-surface-variant">{subtitle}</p>}
        <div className="mt-8">{children}</div>
      </section>
    </main>
  );
}
