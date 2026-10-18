import { cn } from "cn";
import type * as React from "react";

// A grey placeholder shaped like the content that is loading.
function Skeleton({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="skeleton"
      aria-hidden="true"
      className={cn("animate-pulse rounded-sm bg-surface-container-highest motion-reduce:animate-none", className)}
      {...props}
    />
  );
}

export { Skeleton };
