import { SearchIcon } from "lucide-react";
import type * as React from "react";

// Material 3 search bar: pill-shaped, with a magnifier at the start.
// `label` is read by screen readers since there is no visible label.
export function SearchInput({ label, ...props }: Omit<React.ComponentProps<"input">, "type"> & { label: string }) {
  return (
    <div className="relative">
      <SearchIcon
        aria-hidden="true"
        className="pointer-events-none absolute start-4 top-1/2 size-5 -translate-y-1/2 text-on-surface-variant"
      />
      <input
        type="search"
        aria-label={label}
        className="h-12 w-full min-w-0 rounded-full bg-surface-container-high ps-12 pe-4 text-body-large text-on-surface transition-[background-color,box-shadow] placeholder:text-on-surface-variant hover:bg-surface-container-highest focus-visible:bg-surface-container-highest focus-visible:shadow-[inset_0_0_0_2px_var(--color-primary)] focus-visible:outline-none"
        {...props}
      />
    </div>
  );
}
