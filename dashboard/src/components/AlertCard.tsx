import type { Alert, Vital } from "../api";
import { VITAL_LABEL, dateTime, vitalValue } from "../format";

interface Props {
  alert: Alert;
  onAcknowledge?: (alert: Alert) => void;
  busy?: boolean;
  showPatient?: boolean;
}

export function AlertCard({ alert, onAcknowledge, busy, showPatient = true }: Props) {
  const vitals = Object.entries(alert.vitals).filter(([, v]) => v !== null && v !== undefined) as [Vital, number][];
  return (
    <article className={`alert-card alert-${alert.state}`} aria-label={`Alert for ${alert.patient_id}`}>
      <header>
        <span className="alert-title">
          <span aria-hidden="true">◆</span> {alert.kind === "escalation" ? "Critical, worse" : "Critical"}
          {showPatient && (
            <>
              {" · "}
              <a href={`#/patients/${alert.patient_id}`}>{alert.patient_id}</a>
            </>
          )}
        </span>
        <time dateTime={alert.raised_at}>{dateTime(alert.raised_at)} UTC</time>
      </header>
      <dl className="alert-vitals">
        {vitals.map(([vital, value]) => (
          <div key={vital} className={alert.red_vitals.includes(vital) ? "red" : undefined}>
            <dt>{VITAL_LABEL[vital]}</dt>
            <dd>{vitalValue(vital, value)}</dd>
          </div>
        ))}
      </dl>
      <p className="muted small">
        Score {alert.news_score}
        {alert.red_vitals.length > 0 && <> · red: {alert.red_vitals.map((v) => VITAL_LABEL[v as Vital] ?? v).join(", ")}</>}
        {" · "}decided by {alert.decided_by} · P(Critical) {alert.p_critical.toFixed(2)}
        {alert.reminders > 0 && <> · {alert.reminders} reminder{alert.reminders > 1 ? "s" : ""}</>}
      </p>
      {alert.state === "open" && onAcknowledge && (
        <button type="button" className="button" disabled={busy} onClick={() => onAcknowledge(alert)}>
          Acknowledge
        </button>
      )}
      {alert.state === "acknowledged" && (
        <p className="muted small">
          Acknowledged by {alert.acknowledged_by} at {alert.acknowledged_at && dateTime(alert.acknowledged_at)} UTC
        </p>
      )}
    </article>
  );
}
