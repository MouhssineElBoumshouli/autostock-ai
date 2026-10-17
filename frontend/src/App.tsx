import { ServerStatus } from "./components/ServerStatus";
import { t } from "./i18n";

export function App() {
  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-12">
      <section className="w-full max-w-md rounded-card border border-line bg-card p-8 sm:p-10">
        <img src="/favicon.svg" alt="" className="size-12" />
        <h1 className="mt-6 text-3xl font-semibold tracking-tight">{t.appName}</h1>
        <p className="mt-2 text-base leading-relaxed text-muted">{t.tagline}</p>
        <div className="mt-8 border-t border-line pt-6">
          <ServerStatus />
        </div>
      </section>
    </main>
  );
}
