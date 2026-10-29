import { RotateCwIcon, TriangleAlertIcon } from "lucide-react";
import { Component, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { t } from "@/i18n";

function referenceCode(): string {
  return Math.random().toString(16).slice(2, 8).toUpperCase();
}

// Catches a crash in one page, instead of the whole app going white. The sidebar and top bar
// (outside this) stay up; "Reload" is the one way back we can offer, since React can't recover
// a broken tree by itself. The router remounts this (a new `key`) when the person goes elsewhere.
export class PageErrorBoundary extends Component<{ children: ReactNode }, { code: string | null }> {
  state: { code: string | null } = { code: null };

  static getDerivedStateFromError() {
    return { code: referenceCode() };
  }

  componentDidCatch(error: unknown) {
    // eslint-disable-next-line no-console
    console.error(`Page crashed (reference ${this.state.code}):`, error);
  }

  render() {
    if (this.state.code === null) return this.props.children;
    return (
      <div role="alert" className="flex flex-col items-center gap-4 px-6 py-16 text-center">
        <span className="flex size-14 items-center justify-center rounded-full bg-error-container text-on-error-container">
          <TriangleAlertIcon aria-hidden="true" className="size-6" />
        </span>
        <div className="grid max-w-sm gap-1">
          <p className="text-title-medium">{t.states.crashTitle}</p>
          <p className="text-body-medium text-on-surface-variant">{t.states.crashBody}</p>
        </div>
        <Button onClick={() => window.location.reload()}>
          <RotateCwIcon aria-hidden="true" />
          {t.states.reload}
        </Button>
        <p className="text-body-small text-on-surface-variant">{t.states.referenceCode(this.state.code)}</p>
      </div>
    );
  }
}
