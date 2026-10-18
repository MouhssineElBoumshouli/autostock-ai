import { CircleCheckIcon, InfoIcon, OctagonXIcon, TriangleAlertIcon } from "lucide-react";
import type * as React from "react";
import { Toaster as Sonner } from "sonner";

// Short messages that appear at the bottom and disappear by themselves.
// Show one with: toast.success("Order saved") — import { toast } from "sonner".
function Toaster() {
  return (
    <Sonner
      theme="light"
      position="bottom-center"
      icons={{
        success: <CircleCheckIcon className="size-4 text-success" />,
        info: <InfoIcon className="size-4 text-muted-foreground" />,
        warning: <TriangleAlertIcon className="size-4 text-warning" />,
        error: <OctagonXIcon className="size-4 text-destructive" />,
      }}
      style={
        {
          "--normal-bg": "var(--popover)",
          "--normal-text": "var(--popover-foreground)",
          "--normal-border": "var(--border)",
          "--border-radius": "var(--radius-lg)",
        } as React.CSSProperties
      }
      toastOptions={{ classNames: { toast: "font-sans shadow-lg", description: "text-muted-foreground!" } }}
    />
  );
}

export { Toaster };
