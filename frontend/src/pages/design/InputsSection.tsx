import { useState } from "react";

import { CheckboxField } from "@/components/CheckboxField";
import { FilterChip } from "@/components/FilterChip";
import { FormField } from "@/components/FormField";
import { PasswordInput } from "@/components/PasswordInput";
import { SearchInput } from "@/components/SearchInput";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

import { ExampleLabel, Section } from "./Section";

export function InputsSection() {
  const [notify, setNotify] = useState(true);
  const [status, setStatus] = useState<string | undefined>("low");

  return (
    <Section
      id="inputs"
      title="Inputs"
      description="Outlined text fields: the label sits on the border. Supporting text explains, error text says exactly what to fix. Filters are chips."
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

          <FormField label="Password" help="The eye button shows or hides what was typed. It sits at the end side.">
            {(field) => <PasswordInput {...field} autoComplete="off" defaultValue="Atlas-parts-2026" />}
          </FormField>

          <div className="grid gap-3">
            <ExampleLabel>Filter chips (filled once a filter is chosen)</ExampleLabel>
            <div className="flex flex-wrap gap-2">
              <FilterChip
                label="Status"
                allLabel="All statuses"
                value={status}
                options={[
                  { value: "low", label: "Low stock" },
                  { value: "out", label: "Out of stock" },
                ]}
                onChange={setStatus}
              />
              <FilterChip label="Branch" allLabel="All branches" options={[{ value: "rabat", label: "Rabat" }]} onChange={() => {}} />
            </div>
          </div>

          <div className="grid gap-2">
            <ExampleLabel>Search bar</ExampleLabel>
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
