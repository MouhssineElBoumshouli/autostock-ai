import { DownloadIcon } from "lucide-react";

import { useDownloadAllData } from "@/api/exports";
import { FormError } from "@/components/FormError";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { t } from "@/i18n";

// Owners only: everything in the shop, as one Excel file they can open, share or keep safe.
export function ExportCard() {
  const download = useDownloadAllData();
  const words = t.settings.export;

  return (
    <Card className="max-w-2xl">
      <CardHeader>
        <CardTitle>{words.title}</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-3">
        <p className="text-body-medium text-on-surface-variant">{words.description}</p>
        <FormError message={download.isError ? words.failed : undefined} />
      </CardContent>
      <CardFooter className="border-t pt-6">
        <Button variant="filled" onClick={() => download.mutate()} loading={download.isPending}>
          <DownloadIcon aria-hidden="true" />
          {words.button}
        </Button>
      </CardFooter>
    </Card>
  );
}
