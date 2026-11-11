import { cn } from "cn";
import { Tabs as TabsPrimitive } from "radix-ui";
import type * as React from "react";

function Tabs({ className, ...props }: React.ComponentProps<typeof TabsPrimitive.Root>) {
  return <TabsPrimitive.Root data-slot="tabs" className={cn("min-w-0 flex flex-col gap-6", className)} {...props} />;
}

// min-w-0 lets the row's own overflow-x-auto scroll internally when the tabs don't all fit,
// instead of its minimum content width pushing whatever contains it wider than the screen.
function TabsList({ className, ...props }: React.ComponentProps<typeof TabsPrimitive.List>) {
  return (
    <TabsPrimitive.List
      data-slot="tabs-list"
      className={cn("flex min-w-0 overflow-x-auto border-b border-outline-variant", className)}
      {...props}
    />
  );
}

// Material 3 primary tabs: the active tab is violet with a 3px rounded indicator under its label.
function TabsTrigger({ className, ...props }: React.ComponentProps<typeof TabsPrimitive.Trigger>) {
  return (
    <TabsPrimitive.Trigger
      data-slot="tabs-trigger"
      className={cn(
        "state-layer relative inline-flex h-12 shrink-0 items-center gap-2 px-4 text-title-small whitespace-nowrap text-on-surface-variant focus-visible:outline-offset-[-2px] disabled:pointer-events-none disabled:opacity-38 data-[state=active]:text-primary data-[state=active]:after:absolute data-[state=active]:after:inset-x-4 data-[state=active]:after:bottom-0 data-[state=active]:after:h-[3px] data-[state=active]:after:rounded-t-full data-[state=active]:after:bg-primary [&_svg]:size-5",
        className,
      )}
      {...props}
    />
  );
}

function TabsContent({ className, ...props }: React.ComponentProps<typeof TabsPrimitive.Content>) {
  return <TabsPrimitive.Content data-slot="tabs-content" className={className} {...props} />;
}

export { Tabs, TabsContent, TabsList, TabsTrigger };
