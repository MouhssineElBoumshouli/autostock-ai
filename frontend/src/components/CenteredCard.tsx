import type { ReactNode } from "react";

// A single card in the middle of the screen, with the logo. Used for setup, login and home.
export function CenteredCard({ title, subtitle, children }: { title: string; subtitle?: string; children: ReactNode }) {
  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-12">
      <section className="w-full max-w-md rounded-xl border bg-card p-6 sm:p-10">
        <img src="/favicon.svg" alt="" className="size-12" />
        <h1 className="mt-6 text-2xl font-semibold tracking-tight sm:text-3xl">{title}</h1>
        {subtitle && <p className="mt-2 text-base text-muted-foreground">{subtitle}</p>}
        <div className="mt-8">{children}</div>
      </section>
    </main>
  );
}
