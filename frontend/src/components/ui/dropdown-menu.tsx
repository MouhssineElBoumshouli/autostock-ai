import { cn } from "cn";
import { DropdownMenu as MenuPrimitive } from "radix-ui";
import type * as React from "react";

const DropdownMenu = MenuPrimitive.Root;
const DropdownMenuTrigger = MenuPrimitive.Trigger;

// Material 3 menu: 4px corners, level 2 shadow, 48px rows.
function DropdownMenuContent({ className, sideOffset = 4, ...props }: React.ComponentProps<typeof MenuPrimitive.Content>) {
  return (
    <MenuPrimitive.Portal>
      <MenuPrimitive.Content
        data-slot="dropdown-menu-content"
        sideOffset={sideOffset}
        className={cn(
          "z-50 min-w-48 rounded-xs bg-surface-container py-2 text-on-surface shadow-elevation-2 data-open:animate-in data-open:fade-in-0 data-open:zoom-in-95",
          className,
        )}
        {...props}
      />
    </MenuPrimitive.Portal>
  );
}

function DropdownMenuItem({ className, ...props }: React.ComponentProps<typeof MenuPrimitive.Item>) {
  return (
    <MenuPrimitive.Item
      data-slot="dropdown-menu-item"
      className={cn(
        "flex h-12 cursor-default items-center gap-3 px-3 text-body-large outline-hidden select-none data-disabled:pointer-events-none data-disabled:opacity-38 data-highlighted:bg-on-surface/10 [&_svg]:size-5 [&_svg]:shrink-0 [&_svg]:text-on-surface-variant",
        className,
      )}
      {...props}
    />
  );
}

function DropdownMenuSeparator({ className, ...props }: React.ComponentProps<typeof MenuPrimitive.Separator>) {
  return <MenuPrimitive.Separator className={cn("my-2 h-px bg-outline-variant", className)} {...props} />;
}

export { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger };
