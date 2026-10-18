import { useState } from "react";

import { CheckboxField } from "@/components/CheckboxField";
import { FormField } from "@/components/FormField";
import { SearchInput } from "@/components/SearchInput";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

import { ExampleLabel, Section } from "./Section";

export function InputsSection() {
  const [notify, setNotify] = useState(true);

  return (
    <Section
      id="inputs"
      title="Inputs"
      description="Every field has a label above it. Help text explains, error text says exactly what to fix."
    >
      <Card>
        <CardContent className="grid gap-6 md:grid-cols-2">
          <FormField label="Part name" help="As written on the box, e.g. Brake pads (front).">
            {(field) => <Input {...field} placeholder="Brake pads (front)" />}
          </FormField>

          <FormField label="Quantity" error="Enter a whole number, for example 12.">
            {(field) => <Input {...field} inputMode="numeric" defaultValue="12.5" />}
          </FormField>

          <FormField label="Branch" help="Where this stock is kept.">
            {(field) => (
              <Select defaultValue="casablanca">
                <SelectTrigger {...field}>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="casablanca">Casablanca</SelectItem>
                  <SelectItem value="rabat">Rabat</SelectItem>
                  <SelectItem value="marrakech">Marrakech</SelectItem>
                </SelectContent>
              </Select>
            )}
          </FormField>

          <div className="grid gap-2">
            <ExampleLabel>Search with icon</ExampleLabel>
            <SearchInput label="Search parts" placeholder="Search parts, SKUs or OEM numbers" />
          </div>

          <CheckboxField
            label="Tell me when stock is low"
            help="You get one message per day, not one per part."
            checked={notify}
            onCheckedChange={setNotify}
          />
        </CardContent>
      </Card>
    </Section>
  );
}
