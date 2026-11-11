import { useState } from "react";

import { CheckboxField } from "@/components/CheckboxField";
import { type Column, DataTable } from "@/components/DataTable";
import { type StockStatus, StockBadge } from "@/components/StockBadge";
import { Card, CardAction, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { formatNumber } from "@/lib/format";

import { Section } from "./Section";

type ExamplePart = { sku: string; name: string; inStock: number; soldLast30Days: number; status: StockStatus };

const exampleParts: ExamplePart[] = [
  { sku: "BP-001", name: "Brake pads (front)", inStock: 80, soldLast30Days: 420, status: "low" },
  { sku: "OF-203", name: "Oil filter", inStock: 1240, soldLast30Days: 380, status: "healthy" },
  { sku: "SP-104", name: "Spark plug", inStock: 0, soldLast30Days: 300, status: "out" },
  { sku: "AF-331", name: "Air filter (engine)", inStock: 645, soldLast30Days: 260, status: "healthy" },
];

const columns: Column<ExamplePart>[] = [
  { header: "Part", cell: (part) => part.name, primary: true },
  { header: "SKU", cell: (part) => <span className="text-on-surface-variant">{part.sku}</span> },
  { header: "In stock", cell: (part) => formatNumber(part.inStock), align: "end" },
  { header: "Sold (30 days)", cell: (part) => formatNumber(part.soldLast30Days), align: "end" },
  { header: "Status", cell: (part) => <StockBadge status={part.status} /> },
];

export function TableSection() {
  const [loading, setLoading] = useState(false);

  return (
    <Section
      id="table"
      title="Table"
      description="Numbers are right-aligned so digits line up. On phones each row becomes a small card. Make the window narrow to see it."
    >
      <Card className="gap-4 pb-0">
        <CardHeader>
          <CardTitle>Parts</CardTitle>
          <CardDescription>Example data</CardDescription>
          <CardAction>
            <CheckboxField label="Show loading" checked={loading} onCheckedChange={setLoading} />
          </CardAction>
        </CardHeader>
        <DataTable columns={columns} rows={exampleParts} rowKey={(part) => part.sku} loading={loading} />
      </Card>
    </Section>
  );
}
