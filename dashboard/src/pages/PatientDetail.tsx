import { useState } from "react";
import { ApiError, type Vital } from "../api";
import { useAuth } from "../auth";
import { AlertCard } from "../components/AlertCard";
import { ReadingsTable } from "../components/ReadingsTable";
import { StatusBadge } from "../components/StatusBadge";
import { ThresholdsForm } from "../components/ThresholdsForm";
import { VitalChart } from "../components/VitalChart";
import { VITAL_LABEL, conditions, zeroBand } from "../format";
import { useAcknowledge, useHistory, useThresholdChange, useThresholds } from "../useApi";

const RANGES = [
  { label: "1 h", limit: 60 },
  { label: "6 h", limit: 360 },
  { label: "24 h", limit: 1440 },
];

export function PatientDetail({ id }: { id: string }) {
  const { session } = useAuth();
  const [limit, setLimit] = useState(360);
  const history = useHistory(id, limit);
  const thresholds = useThresholds(id);
  const acknowledge = useAcknowledge();
  const change = useThresholdChange(id);

  if (history.error) {
    const denied = history.error instanceof ApiError && history.error.status === 403;
    return (
      <section className="panel">
        <h2>{denied ? "Not your patient" : "Could not load this patient"}</h2>
        <p className="muted">
          {denied ? "You can only see patients assigned to you. This attempt has been recorded." : history.error.message}
        </p>
        <a href="#/">Back to my patients</a>
      </section>
    );
  }
  if (!history.data) return <p className="muted">Loading…</p>;

  const { patient, readings, alerts } = history.data;
  const latest = readings[readings.length - 1];
  const defaults = thresholds.data?.defaults;
  const limitFor = (v: Vital) => thresholds.data?.limits.find((l) => l.vital === v) ?? null;
  const spo2Bands = defaults?.[patient.spo2_scale === 2 ? "spo2_scale2" : "spo2_scale1"];
  const visibleAlerts = alerts.filter((a) => readings.length && a.raised_at >= readings[0].measured_at);

  const charts: { title: string; vitals: Vital[]; bands?: [number | null, number][] }[] = [
    { title: "Heart rate", vitals: ["heart_rate"], bands: defaults?.heart_rate },
    { title: `SpO₂ (Scale ${patient.spo2_scale})`, vitals: ["spo2"], bands: spo2Bands },
    { title: "Blood pressure", vitals: ["systolic_bp", "diastolic_bp"], bands: defaults?.systolic_bp },
    { title: "Temperature", vitals: ["temperature"], bands: defaults?.temperature },
  ];
  if (patient.diabetes) charts.push({ title: "Glucose", vitals: ["glucose"], bands: defaults?.glucose });

  return (
    <div className="patient">
      <section className="panel patient-header">
        <div>
          <h2>Patient {patient.id}</h2>
          <p className="muted">
            {patient.risk_group} risk · age {patient.age_band} · {conditions(patient)} · clinician {patient.clinician_id}
          </p>
        </div>
        <div className="patient-status">
          <StatusBadge status={latest?.status} />
          {latest && (
            <p className="muted small">
              Why: score {latest.news_score}
              {Object.entries(latest.score_parts)
                .filter(([, p]) => p > 0)
                .map(([v, p]) => ` · ${VITAL_LABEL[v as Vital] ?? v} +${p}`)
                .join("")}
              {latest.decided_by !== "model" && ` · decided by ${latest.decided_by}`}
            </p>
          )}
        </div>
      </section>

      <div className="toolbar" role="group" aria-label="Time range">
        {RANGES.map((r) => (
          <button key={r.limit} type="button" className={`chip ${limit === r.limit ? "chip-on" : ""}`}
            aria-pressed={limit === r.limit} onClick={() => setLimit(r.limit)}>
            {r.label}
          </button>
        ))}
        <span className="muted small">
          Grey band: default normal range · dashed line: this patient's limits · red line: alert · red dot: this
          vital scored in a Critical reading
        </span>
      </div>

      <div className="charts">
        {charts.map((c) => (
          <VitalChart key={c.title} title={c.title} vitals={c.vitals} readings={readings} alerts={visibleAlerts}
            normal={zeroBand(c.bands)} limits={limitFor(c.vitals[0])} />
        ))}
      </div>

      {alerts.length > 0 && (
        <section className="panel" aria-labelledby="patient-alerts-heading">
          <h2 id="patient-alerts-heading">Alerts</h2>
          <div className="alert-list">
            {[...alerts].reverse().slice(0, 10).map((a) => (
              <AlertCard key={a.id} alert={a} showPatient={false} busy={acknowledge.isPending}
                onAcknowledge={session?.clinicianId === a.clinician_id ? (x) => acknowledge.mutate(x) : undefined} />
            ))}
          </div>
        </section>
      )}

      {thresholds.data && (
        <ThresholdsForm patient={patient} thresholds={thresholds.data} onSave={change.save} onReset={change.reset} />
      )}

      <ReadingsTable readings={readings} diabetic={patient.diabetes} />
    </div>
  );
}
