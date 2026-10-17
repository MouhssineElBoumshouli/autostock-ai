import { type ServerState, useServerState } from "../api/health";
import { t } from "../i18n";
import { Badge, type BadgeTone } from "./Badge";

const badges: Record<ServerState, { tone: BadgeTone; text: string }> = {
  connected: { tone: "good", text: t.serverStatus.connected },
  databaseDown: { tone: "bad", text: t.serverStatus.databaseDown },
  serverDown: { tone: "bad", text: t.serverStatus.serverDown },
};

export function ServerStatus() {
  const { data: state } = useServerState();
  const badge = state ? badges[state] : { tone: "neutral" as const, text: t.serverStatus.checking };

  return (
    <div role="status" aria-live="polite" className="flex items-center gap-3">
      <span className="text-sm text-muted">{t.serverStatus.label}</span>
      <Badge tone={badge.tone}>{badge.text}</Badge>
    </div>
  );
}
