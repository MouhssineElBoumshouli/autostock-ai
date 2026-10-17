import type { ReactNode } from "react";

export type BadgeTone = "good" | "low" | "bad" | "neutral";

const toneClasses: Record<BadgeTone, string> = {
  good: "bg-good-soft text-good",
  low: "bg-low-soft text-low",
  bad: "bg-bad-soft text-bad",
  neutral: "bg-page text-muted",
};

// Always shows a word next to the color dot, so meaning never depends on color alone.
export function Badge({ tone, children }: { tone: BadgeTone; children: ReactNode }) {
  return (
    <span
      className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-sm font-medium ${toneClasses[tone]}`}
    >
      <span aria-hidden="true" className="size-2 rounded-full bg-current" />
      {children}
    </span>
  );
}
