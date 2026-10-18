import { SearchIcon } from "lucide-react";
import type * as React from "react";

import { Input } from "@/components/ui/input";

// A search box with a magnifier icon. `label` is read by screen readers since there is no visible label.
export function SearchInput({
  label,
  ...props
}: Omit<React.ComponentProps<"input">, "type"> & { label: string }) {
  return (
    <div className="relative">
      <SearchIcon
        aria-hidden="true"
        className="pointer-events-none absolute start-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
      />
      <Input type="search" aria-label={label} className="ps-9" {...props} />
    </div>
  );
}
