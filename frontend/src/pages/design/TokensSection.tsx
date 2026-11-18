import { Card, CardContent } from "@/components/ui/card";

import { ExampleLabel, Section } from "./Section";

const colors = [
  { name: "primary", use: "Main action, active" },
  { name: "primary-container", use: "Brand deep blue #1f4fa3" },
  { name: "secondary-container", use: "Active menu item" },
  { name: "surface", use: "Page background" },
  { name: "surface-container-low", use: "Cards, menu" },
  { name: "surface-container-high", use: "Dialogs, search" },
  { name: "on-surface", use: "Main text" },
  { name: "on-surface-variant", use: "Secondary text" },
  { name: "outline", use: "Field borders" },
  { name: "outline-variant", use: "Dividers" },
  { name: "success-container", use: "Healthy" },
  { name: "warning-container", use: "Low stock" },
  { name: "error-container", use: "Out of stock" },
  { name: "error", use: "Danger, errors" },
  { name: "inverse-surface", use: "Snackbar" },
];

const typeScale = [
  { className: "text-display-small", label: "Display small · 36px · big numbers" },
  { className: "text-headline-medium", label: "Headline medium · 28px · page titles" },
  { className: "text-headline-small", label: "Headline small · 24px · dialog titles" },
  { className: "text-title-large", label: "Title large · 22px · top app bar" },
  { className: "text-title-medium", label: "Title medium · 16px · card titles" },
  { className: "text-body-large", label: "Body large · 16px · lists, fields" },
  { className: "text-body-medium", label: "Body medium · 14px · body text (default)" },
  { className: "text-label-large", label: "Label large · 14px · buttons, tabs" },
  { className: "text-body-small", label: "Body small · 12px · supporting text" },
];

const shapes = [
  { className: "rounded-xs", label: "Extra small · 4px · fields, menus" },
  { className: "rounded-sm", label: "Small · 8px · chips" },
  { className: "rounded-md", label: "Medium · 12px · cards" },
  { className: "rounded-lg", label: "Large · 16px · sheets" },
  { className: "rounded-xl", label: "Extra large · 28px · dialogs" },
  { className: "rounded-full", label: "Full · buttons" },
];

const elevations = [
  { className: "shadow-elevation-1", label: "Level 1 · cards" },
  { className: "shadow-elevation-2", label: "Level 2 · menus" },
  { className: "shadow-elevation-3", label: "Level 3 · dialogs, snackbar" },
];

export function TokensSection() {
  return (
    <Section
      id="tokens"
      title="Tokens"
      description="Material 3 colors (generated from #1f4fa3), type scale, shapes and elevation. They all come from src/index.css. Change them there, never in a component."
    >
      <Card>
        <CardContent className="grid gap-8">
          <div className="grid gap-3">
            <ExampleLabel>Color roles</ExampleLabel>
            <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
              {colors.map((color) => (
                <li key={color.name} className="flex items-center gap-3">
                  <span
                    className="size-10 shrink-0 rounded-md border border-outline-variant"
                    style={{ background: `var(--${color.name})` }}
                  />
                  <span className="grid min-w-0">
                    <span className="truncate text-label-medium">{color.name}</span>
                    <span className="truncate text-body-small text-on-surface-variant">{color.use}</span>
                  </span>
                </li>
              ))}
            </ul>
          </div>

          <div className="grid gap-3">
            <ExampleLabel>Type scale (Roboto Flex) · numbers use same-width digits: 1,111 / 8,888</ExampleLabel>
            {typeScale.map((type) => (
              <div key={type.label} className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
                <span className={`${type.className} tabular-nums`}>3,892 parts</span>
                <span className="text-body-small text-on-surface-variant">{type.label}</span>
              </div>
            ))}
          </div>

          <div className="grid gap-8 lg:grid-cols-2">
            <div className="grid gap-3">
              <ExampleLabel>Shapes</ExampleLabel>
              <div className="flex flex-wrap gap-4">
                {shapes.map((shape) => (
                  <div key={shape.label} className="grid w-24 justify-items-center gap-2 text-center">
                    <span className={`size-12 bg-primary-container ${shape.className}`} />
                    <span className="text-body-small text-on-surface-variant">{shape.label}</span>
                  </div>
                ))}
              </div>
            </div>
            <div className="grid gap-3">
              <ExampleLabel>Elevation</ExampleLabel>
              <div className="flex flex-wrap gap-6">
                {elevations.map((level) => (
                  <div key={level.label} className="grid w-24 justify-items-center gap-3 text-center">
                    <span className={`size-14 rounded-md bg-surface-container-low ${level.className}`} />
                    <span className="text-body-small text-on-surface-variant">{level.label}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </Section>
  );
}
