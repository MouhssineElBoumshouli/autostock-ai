import { Direction } from "radix-ui";
import { useEffect, useState } from "react";

import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { direction as appDirection } from "@/i18n";

import { BadgesSection } from "./BadgesSection";
import { ButtonsSection } from "./ButtonsSection";
import { CardsSection } from "./CardsSection";
import { InputsSection } from "./InputsSection";
import { OverlaysSection } from "./OverlaysSection";
import { StatesSection } from "./StatesSection";
import { TableSection } from "./TableSection";
import { TokensSection } from "./TokensSection";

// Shows every building block in one place. Build new screens only from these pieces.
export function DesignPage() {
  const [direction, setDirection] = useState(appDirection);

  // Flips the whole page (and dialogs, menus, toasts) to check that Arabic will look right.
  useEffect(() => {
    document.documentElement.dir = direction;
    return () => {
      document.documentElement.dir = appDirection;
    };
  }, [direction]);

  return (
    <Direction.Provider dir={direction}>
      <main className="mx-auto grid max-w-6xl gap-12 px-4 py-8 sm:px-6 lg:px-8 lg:py-12">
        <PageHeader
          title="Design system"
          subtitle="Every building block of AutoStock AI. New screens use these pieces, nothing else."
          action={
            <Button
              variant="primary"
              onClick={() => setDirection(direction === "ltr" ? "rtl" : "ltr")}
            >
              {direction === "ltr" ? "Preview right-to-left" : "Back to left-to-right"}
            </Button>
          }
        />
        <TokensSection />
        <ButtonsSection />
        <InputsSection />
        <CardsSection />
        <BadgesSection />
        <TableSection />
        <OverlaysSection />
        <StatesSection />
      </main>
    </Direction.Provider>
  );
}
