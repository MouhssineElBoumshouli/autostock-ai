import { CheckIcon } from "lucide-react";

import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

export const ALL = "all";

// A Material 3 filter chip that opens a menu of choices. It fills in with a check once something
// other than "All …" is chosen. `label` names the filter for screen readers ("Status", "Branch").
export function FilterChip({
  label,
  value,
  allLabel,
  options,
  onChange,
}: {
  label: string;
  value?: string;
  allLabel: string;
  options: { value: string; label: string }[];
  onChange: (value: string | undefined) => void;
}) {
  const chosen = value !== undefined && value !== ALL;

  return (
    <Select value={value ?? ALL} onValueChange={(next) => onChange(next === ALL ? undefined : next)}>
      <SelectTrigger variant="chip" aria-label={label} data-chosen={chosen || undefined}>
        <span className="flex items-center gap-2">
          {chosen && <CheckIcon aria-hidden="true" className="size-[18px]" />}
          <SelectValue />
        </span>
      </SelectTrigger>
      <SelectContent>
        <SelectItem value={ALL}>{allLabel}</SelectItem>
        {options.map((option) => (
          <SelectItem key={option.value} value={option.value}>
            {option.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
