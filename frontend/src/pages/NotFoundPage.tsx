import { CompassIcon } from "lucide-react";
import { Link } from "react-router";

import { EmptyState } from "@/components/EmptyState";
import { Button } from "@/components/ui/button";
import { t } from "@/i18n";

export function NotFoundPage() {
  return (
    <main className="flex min-h-screen items-center justify-center px-4">
      <EmptyState
        icon={CompassIcon}
        title={t.notFound.title}
        description={t.notFound.description}
        action={
          <Button variant="primary" asChild>
            <Link to="/">{t.common.goHome}</Link>
          </Button>
        }
      />
    </main>
  );
}
