import { type ServerState, useServerState } from "@/api/health";
import { Badge } from "@/components/ui/badge";
import { t } from "@/i18n";

const badges = {
  connected: { variant: "success", text: t.serverStatus.connected },
  databaseDown: { variant: "destructive", text: t.serverStatus.databaseDown },
  serverDown: { variant: "destructive", text: t.serverStatus.serverDown },
} as const satisfies Record<ServerState, unknown>;

export function ServerStatus() {
  const { data: state } = useServerState();
  const badge = state ? badges[state] : { variant: "neutral" as const, text: t.serverStatus.checking };

  return (
    <div role="status" aria-live="polite" className="flex items-center gap-3">
      <span className="text-sm text-muted-foreground">{t.serverStatus.label}</span>
      <Badge variant={badge.variant}>{badge.text}</Badge>
    </div>
  );
}
