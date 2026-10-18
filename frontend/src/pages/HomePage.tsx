import { ServerStatus } from "@/components/ServerStatus";
import { t } from "@/i18n";

export function HomePage() {
  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-12">
      <section className="w-full max-w-md rounded-xl border bg-card p-8 sm:p-10">
        <img src="/favicon.svg" alt="" className="size-12" />
        <h1 className="mt-6 text-3xl font-semibold tracking-tight">{t.appName}</h1>
        <p className="mt-2 text-base text-muted-foreground">{t.tagline}</p>
        <div className="mt-8 border-t pt-6">
          <ServerStatus />
        </div>
      </section>
    </main>
  );
}
