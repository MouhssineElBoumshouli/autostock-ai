import { PackageIcon, UploadIcon } from "lucide-react";
import { useState } from "react";

import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

import { ExampleLabel, Section } from "./Section";

export function StatesSection() {
  const [retrying, setRetrying] = useState(false);

  function retry() {
    setRetrying(true);
    setTimeout(() => setRetrying(false), 1500);
  }

  return (
    <Section
      id="states"
      title="Loading, empty and error"
      description="Every screen has all three. Loading shows grey shapes, empty offers a next step, error offers Try again."
    >
      <div className="grid gap-4 lg:grid-cols-3">
        <div className="grid grid-rows-[auto_1fr] gap-3">
          <ExampleLabel>Loading</ExampleLabel>
          <Card>
            <CardContent className="grid gap-4">
              <Skeleton className="h-5 w-1/2" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-5/6" />
              <Skeleton className="h-4 w-2/3" />
            </CardContent>
          </Card>
        </div>
        <div className="grid grid-rows-[auto_1fr] gap-3">
          <ExampleLabel>Empty</ExampleLabel>
          <Card className="justify-center py-0">
            <EmptyState
              icon={PackageIcon}
              title="No parts yet"
              description="Import your stock from an Excel or CSV file to get started."
              action={
                <Button variant="primary">
                  <UploadIcon aria-hidden="true" />
                  Import parts
                </Button>
              }
            />
          </Card>
        </div>
        <div className="grid grid-rows-[auto_1fr] gap-3">
          <ExampleLabel>Error</ExampleLabel>
          <Card className="justify-center py-0">
            <ErrorState onRetry={retry} retrying={retrying} />
          </Card>
        </div>
      </div>
    </Section>
  );
}
