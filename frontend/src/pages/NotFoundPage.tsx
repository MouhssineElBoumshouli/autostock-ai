import { CompassIcon } from "lucide-react";
import { Link } from "react-router";

import { EmptyState } from "@/components/EmptyState";
import { Button } from "@/components/ui/button";
import { t } from "@/i18n";

export function NotFoundPage() {
  return (
    <EmptyState
      icon={CompassIcon}
      title={t.notFound.title}
      description={t.notFound.description}
      action={
        <Button variant="filled" asChild>
          <Link to="/">{t.common.goHome}</Link>
        </Button>
      }
    />
  );
}
