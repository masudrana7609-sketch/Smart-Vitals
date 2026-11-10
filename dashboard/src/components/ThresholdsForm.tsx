import { useState, type FormEvent } from "react";
import type { Patient, Thresholds, Vital } from "../api";
import { VITAL_LABEL, VITAL_UNIT, dateTime } from "../format";

interface Props {
  patient: Patient;
  thresholds: Thresholds;
  onSave: (vital: Vital, low: number | null, high: number | null, reason: string) => Promise<void>;
  onReset: (vital: Vital) => Promise<void>;
}

export function ThresholdsForm({ patient, thresholds, onSave, onReset }: Props) {
  const vitals: Vital[] = ["heart_rate", "spo2", "systolic_bp", "diastolic_bp", "temperature"];
  if (patient.diabetes) vitals.push("glucose");
  const [vital, setVital] = useState<Vital>("heart_rate");
  const [low, setLow] = useState("");
  const [high, setHigh] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const number = (text: string) => (text.trim() === "" ? null : Number(text));

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSaving(true);
    try {
      await onSave(vital, number(low), number(high), reason.trim());
      setLow("");
      setHigh("");
      setReason("");
    } catch (problem) {
      setError(problem instanceof Error ? problem.message : String(problem));
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="panel" aria-labelledby="thresholds-heading">
      <h2 id="thresholds-heading">Alert limits for {patient.id}</h2>
      <p className="muted small">
        Personal limits replace the default bands for that vital, for this patient only: a value outside them is a
        red score (Critical); inside them it scores 0. They apply to new readings, and every change is audited.
        SpO₂ is scored on Scale {thresholds.spo2_scale}.
      </p>
      {thresholds.limits.length > 0 ? (
        <div className="table-scroll">
        <table className="table">
          <thead>
            <tr>
              <th scope="col">Vital</th>
              <th scope="col">Low</th>
              <th scope="col">High</th>
              <th scope="col">Reason</th>
              <th scope="col">Set by</th>
              <th scope="col"><span className="visually-hidden">Actions</span></th>
            </tr>
          </thead>
          <tbody>
            {thresholds.limits.map((l) => (
              <tr key={l.vital}>
                <td>{VITAL_LABEL[l.vital]}</td>
                <td>{l.low ?? "–"}</td>
                <td>{l.high ?? "–"}</td>
                <td>{l.reason}</td>
                <td>
                  {l.set_by}, {dateTime(l.set_at)}
                </td>
                <td>
                  <button type="button" className="button button-quiet" onClick={() => onReset(l.vital)}>
                    Reset to default
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      ) : (
        <p className="muted">No personal limits: default bands apply.</p>
      )}
      <form className="threshold-form" onSubmit={submit}>
        <label>
          Vital
          <select value={vital} onChange={(e) => setVital(e.target.value as Vital)}>
            {vitals.map((v) => (
              <option key={v} value={v}>
                {VITAL_LABEL[v]} ({VITAL_UNIT[v]})
              </option>
            ))}
          </select>
        </label>
        <label>
          Low limit
          <input inputMode="decimal" value={low} onChange={(e) => setLow(e.target.value)} placeholder="none" />
        </label>
        <label>
          High limit
          <input inputMode="decimal" value={high} onChange={(e) => setHigh(e.target.value)} placeholder="none" />
        </label>
        <label className="grow">
          Reason (required)
          <input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. usual SBP 90-100" />
        </label>
        <button type="submit" className="button" disabled={saving}>
          Save limits
        </button>
      </form>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
    </section>
  );
}
