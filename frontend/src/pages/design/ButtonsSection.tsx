import { PlusIcon, Trash2Icon } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

import { ExampleLabel, Section } from "./Section";

const variants = [
  { variant: "primary", label: "Save order" },
  { variant: "secondary", label: "Export" },
  { variant: "subtle", label: "Cancel" },
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
      description="Primary (violet) is the one main action of a screen. Secondary for other actions, subtle for quiet ones, danger for deleting."
    >
      <Card>
        <CardContent className="grid gap-6">
          {(["md", "sm"] as const).map((size) => (
            <div key={size} className="grid gap-3">
              <ExampleLabel>{size === "md" ? "Normal size" : "Small size"}</ExampleLabel>
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
            <ExampleLabel>With icon · loading (click Save) · disabled</ExampleLabel>
            <div className="flex flex-wrap gap-3">
              <Button variant="secondary">
                <PlusIcon aria-hidden="true" />
                Add part
              </Button>
              <Button variant="primary" loading={saving} onClick={save}>
                Save
              </Button>
              <Button variant="secondary" disabled>
                Disabled
              </Button>
              <Button variant="subtle" size="icon" aria-label="Delete part">
                <Trash2Icon aria-hidden="true" />
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </Section>
  );
}
