import { BoxIcon, CircleCheckIcon, PackageXIcon, TriangleAlertIcon } from "lucide-react";

import { StatCard } from "@/components/StatCard";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { formatNumber } from "@/lib/format";

import { ExampleLabel, Section } from "./Section";

export function CardsSection() {
  return (
    <Section
      id="cards"
      title="Cards"
      description="White box with a thin border and 16px corners. Stat cards show one big number with a label and a short note."
    >
      <div className="grid gap-3">
        <ExampleLabel>Stat cards (example numbers)</ExampleLabel>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard icon={BoxIcon} label="All parts" value={formatNumber(3892)} note="Across 12 categories" />
          <StatCard
            icon={CircleCheckIcon}
            tone="success"
            label="Healthy"
            value={formatNumber(2841)}
            note="73% of all parts"
          />
          <StatCard
            icon={TriangleAlertIcon}
            tone="warning"
            label="Low stock"
            value={formatNumber(682)}
            note="18% of all parts"
          />
          <StatCard icon={PackageXIcon} tone="destructive" label="Out of stock" value="" loading />
        </div>
      </div>

      <div className="grid gap-3">
        <ExampleLabel>Card with title, description, content and footer</ExampleLabel>
        <Card className="max-w-xl">
          <CardHeader>
            <CardTitle>Supplier</CardTitle>
            <CardDescription>Who you order brake parts from.</CardDescription>
            <CardAction>
              <Button variant="subtle" size="sm">
                Edit
              </Button>
            </CardAction>
          </CardHeader>
          <CardContent className="grid gap-1 text-sm">
            <p className="font-medium">Atlas Auto Parts</p>
            <p className="text-muted-foreground">Delivers in 3 days · Casablanca</p>
          </CardContent>
          <CardFooter className="border-t pt-6">
            <Button variant="secondary" size="sm">
              View orders
            </Button>
          </CardFooter>
        </Card>
      </div>
    </Section>
  );
}
