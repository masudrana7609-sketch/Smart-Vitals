import type { Status } from "../api";

// Status is never shown by colour alone: each badge has an icon and a word.
const ICON: Record<Status, string> = { Normal: "●", Warning: "▲", Critical: "◆" };

export function StatusBadge({ status }: { status: Status | null | undefined }) {
  if (!status) return <span className="badge badge-none">No data</span>;
  return (
    <span className={`badge badge-${status.toLowerCase()}`}>
      <span aria-hidden="true">{ICON[status]}</span> {status}
    </span>
  );
}
