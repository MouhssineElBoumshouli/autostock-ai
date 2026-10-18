import type { ReactNode } from "react";

// One block of the design page: a heading, one line about when to use it, then examples.
export function Section({
  id,
  title,
  description,
  children,
}: {
  id: string;
  title: string;
  description: string;
  children: ReactNode;
}) {
  return (
    <section aria-labelledby={id} className="grid gap-4 scroll-mt-8">
      <div className="grid gap-1">
        <h2 id={id} className="text-xl font-semibold">
          {title}
        </h2>
        <p className="text-sm text-muted-foreground">{description}</p>
      </div>
      {children}
    </section>
  );
}

// A small caption above an example inside a section.
export function ExampleLabel({ children }: { children: ReactNode }) {
  return <p className="text-xs font-medium text-muted-foreground">{children}</p>;
}
