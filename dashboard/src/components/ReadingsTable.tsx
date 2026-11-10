import type { Reading, Vital } from "../api";
import { flagText, time } from "../format";
import { StatusBadge } from "./StatusBadge";

// The same data as the charts, as a table: for screen readers and for checking exact values.
export function ReadingsTable({ readings, diabetic }: { readings: Reading[]; diabetic: boolean }) {
  const vitals: Vital[] = ["heart_rate", "spo2", "systolic_bp", "diastolic_bp", "temperature"];
  if (diabetic) vitals.push("glucose");
  const recent = [...readings].reverse().slice(0, 30);
  return (
    <section className="panel" aria-labelledby="readings-heading">
      <h2 id="readings-heading">Latest readings</h2>
      <div className="table-scroll">
        <table className="table">
          <thead>
            <tr>
              <th scope="col">Time (UTC)</th>
              <th scope="col">HR</th>
              <th scope="col">SpO₂</th>
              <th scope="col">BP</th>
              <th scope="col">Temp</th>
              {diabetic && <th scope="col">Glucose</th>}
              <th scope="col">Status</th>
              <th scope="col">Score</th>
              <th scope="col">Notes</th>
            </tr>
          </thead>
          <tbody>
            {recent.map((r) => (
              <tr key={r.msg_id}>
                <td>{time(r.measured_at)}</td>
                <td>{r.heart_rate ?? "–"}</td>
                <td>{r.spo2 ?? "–"}</td>
                <td>
                  {r.systolic_bp ?? "–"}/{r.diastolic_bp ?? "–"}
                </td>
                <td>{r.temperature ?? "–"}</td>
                {diabetic && <td>{r.glucose ?? "–"}</td>}
                <td>
                  <StatusBadge status={r.status} />
                </td>
                <td>{r.news_score}</td>
                <td className="small">
                  {[...r.flags.map(flagText), r.decided_by !== "model" ? `decided by ${r.decided_by}` : ""]
                    .filter(Boolean)
                    .join(" · ")}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
