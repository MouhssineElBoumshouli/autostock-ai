import { Card, CardContent } from "@/components/ui/card";

import { ExampleLabel, Section } from "./Section";

const colors = [
  { name: "background", use: "Page background" },
  { name: "card", use: "Cards, inputs" },
  { name: "border", use: "Thin lines" },
  { name: "foreground", use: "Main text" },
  { name: "muted-foreground", use: "Secondary text" },
  { name: "primary", use: "Main action, active" },
  { name: "success", use: "Healthy" },
  { name: "warning", use: "Low" },
  { name: "destructive", use: "Out, danger" },
];

const textSizes = [
  { className: "text-3xl font-semibold", label: "3xl · 30px · big numbers, page titles" },
  { className: "text-xl font-semibold", label: "xl · 20px · section titles" },
  { className: "text-base font-semibold", label: "base · 16px · card titles" },
  { className: "text-sm", label: "sm · 14px · body text (default)" },
  { className: "text-xs", label: "xs · 12px · captions, table headers" },
];

const radii = [
  { className: "rounded-sm", label: "sm · 6px" },
  { className: "rounded-md", label: "md · 8px" },
  { className: "rounded-lg", label: "lg · 10px · buttons, inputs" },
  { className: "rounded-xl", label: "xl · 16px · cards" },
];

const spacings = [
  { className: "w-2", label: "2 · 8px" },
  { className: "w-4", label: "4 · 16px" },
  { className: "w-6", label: "6 · 24px" },
  { className: "w-8", label: "8 · 32px" },
];

export function TokensSection() {
  return (
    <Section
      id="tokens"
      title="Tokens"
      description="Colors, sizes and corners all come from src/index.css. Change them there, never in a component."
    >
      <Card>
        <CardContent className="grid gap-8">
          <div className="grid gap-3">
            <ExampleLabel>Colors</ExampleLabel>
            <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
              {colors.map((color) => (
                <li key={color.name} className="flex items-center gap-3">
                  <span
                    className="size-10 shrink-0 rounded-lg border"
                    style={{ background: `var(--${color.name})` }}
                  />
                  <span className="grid min-w-0">
                    <span className="truncate text-xs font-medium">{color.name}</span>
                    <span className="truncate text-xs text-muted-foreground">{color.use}</span>
                  </span>
                </li>
              ))}
            </ul>
          </div>

          <div className="grid gap-3">
            <ExampleLabel>Text sizes · numbers use same-width digits: 1,111 / 8,888</ExampleLabel>
            {textSizes.map((size) => (
              <div key={size.label} className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
                <span className={`${size.className} tabular-nums`}>3,892 parts</span>
                <span className="text-xs text-muted-foreground">{size.label}</span>
              </div>
            ))}
          </div>

          <div className="grid gap-8 sm:grid-cols-2">
            <div className="grid gap-3">
              <ExampleLabel>Corners</ExampleLabel>
              <div className="flex flex-wrap gap-4">
                {radii.map((radius) => (
                  <div key={radius.label} className="grid justify-items-center gap-2">
                    <span className={`size-12 border-2 border-primary bg-accent ${radius.className}`} />
                    <span className="text-xs text-muted-foreground">{radius.label}</span>
                  </div>
                ))}
              </div>
            </div>
            <div className="grid gap-3">
              <ExampleLabel>Spacing (4px steps)</ExampleLabel>
              {spacings.map((space) => (
                <div key={space.label} className="flex items-center gap-3">
                  <span className={`h-3 rounded-sm bg-primary ${space.className}`} />
                  <span className="text-xs text-muted-foreground">{space.label}</span>
                </div>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>
    </Section>
  );
}
