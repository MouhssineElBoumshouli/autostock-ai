import { cn } from "cn";
import type * as React from "react";

// First and last cells get 24px padding so the table lines up with card content.
const cellEdges = "px-3 first:ps-6 last:pe-6";

function Table({ className, ...props }: React.ComponentProps<"table">) {
  return (
    <div data-slot="table-container" className="relative w-full overflow-x-auto">
      <table data-slot="table" className={cn("w-full text-body-medium", className)} {...props} />
    </div>
  );
}

function TableHeader({ className, ...props }: React.ComponentProps<"thead">) {
  return <thead data-slot="table-header" className={className} {...props} />;
}

function TableBody({ className, ...props }: React.ComponentProps<"tbody">) {
  return <tbody data-slot="table-body" className={cn("[&_tr:last-child]:border-0", className)} {...props} />;
}

// Rows get the Material hover tint (on-surface at 8%).
function TableRow({ className, ...props }: React.ComponentProps<"tr">) {
  return (
    <tr
      data-slot="table-row"
      className={cn("border-b border-outline-variant transition-colors hover:bg-on-surface/8", className)}
      {...props}
    />
  );
}

function TableHead({ className, ...props }: React.ComponentProps<"th">) {
  return (
    <th
      data-slot="table-head"
      className={cn("h-12 text-start align-middle text-title-small whitespace-nowrap text-on-surface-variant", cellEdges, className)}
      {...props}
    />
  );
}

function TableCell({ className, ...props }: React.ComponentProps<"td">) {
  return <td data-slot="table-cell" className={cn("h-14 align-middle whitespace-nowrap", cellEdges, className)} {...props} />;
}

export { Table, TableBody, TableCell, TableHead, TableHeader, TableRow };
