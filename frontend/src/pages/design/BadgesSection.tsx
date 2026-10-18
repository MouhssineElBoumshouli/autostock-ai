import { StockBadge } from "@/components/StockBadge";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";

import { Section } from "./Section";

export function BadgesSection() {
  return (
    <Section
      id="badges"
      title="Status badges"
      description="A colored dot plus a word. Color is never the only signal."
    >
      <Card>
        <CardContent className="flex flex-wrap gap-3">
          <StockBadge status="healthy" />
          <StockBadge status="low" />
          <StockBadge status="out" />
          <Badge variant="neutral">No sales yet</Badge>
        </CardContent>
      </Card>
    </Section>
  );
}
