import { PlusIcon, Trash2Icon } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

import { ExampleLabel, Section } from "./Section";

const variants = [
  { variant: "filled", label: "Save order" },
  { variant: "tonal", label: "Reorder" },
  { variant: "outlined", label: "Export" },
  { variant: "text", label: "Cancel" },
  { variant: "danger", label: "Delete" },
] as const;

export function ButtonsSection() {
  const [saving, setSaving] = useState(false);

  function save() {
    setSaving(true);
    setTimeout(() => {
      setSaving(false);
      toast.success("Order saved");
    }, 1500);
  }

  return (
    <Section
      id="buttons"
      title="Buttons"
      description="Pill-shaped. Filled (blue) is the one main action of a screen, tonal for strong second actions, outlined for other actions, text for quiet ones, danger for deleting. Hover or press to see the state layer."
    >
      <Card>
        <CardContent className="grid gap-6">
          {(["md", "sm"] as const).map((size) => (
            <div key={size} className="grid gap-3">
              <ExampleLabel>{size === "md" ? "Normal size (40px)" : "Small size (32px)"}</ExampleLabel>
              <div className="flex flex-wrap gap-3">
                {variants.map(({ variant, label }) => (
                  <Button key={variant} variant={variant} size={size}>
                    {label}
                  </Button>
                ))}
              </div>
            </div>
          ))}

          <div className="grid gap-3">
            <ExampleLabel>With icon · loading (click Save) · disabled · icon button</ExampleLabel>
            <div className="flex flex-wrap gap-3">
              <Button variant="tonal">
                <PlusIcon aria-hidden="true" />
                Add part
              </Button>
              <Button variant="filled" loading={saving} onClick={save}>
                Save
              </Button>
              <Button variant="filled" disabled>
                Disabled
              </Button>
              <Button variant="text" size="icon" aria-label="Delete part">
                <Trash2Icon aria-hidden="true" />
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </Section>
  );
}
