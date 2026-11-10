import type { Patient, Status } from "../api";
import { useAuth } from "../auth";
import { AlertCard } from "../components/AlertCard";
import { StatusBadge } from "../components/StatusBadge";
import { conditions, dateTime } from "../format";
import { useAcknowledge, useOpenAlerts, usePatients } from "../useApi";

const SEVERITY: Record<Status, number> = { Critical: 0, Warning: 1, Normal: 2 };

// Patients needing attention first: an open alert, then the latest status, then ID.
export function sortPatients(patients: Patient[]): Patient[] {
  return [...patients].sort(
    (a, b) =>
      Number(b.open_alert) - Number(a.open_alert) ||
      (a.latest_status ? SEVERITY[a.latest_status] : 3) - (b.latest_status ? SEVERITY[b.latest_status] : 3) ||
      a.id.localeCompare(b.id),
  );
}

export function PatientTable({ patients }: { patients: Patient[] }) {
  return (
    <table className="table patient-table">
      <thead>
        <tr>
          <th scope="col">Patient</th>
          <th scope="col">Risk group</th>
          <th scope="col">Conditions</th>
          <th scope="col">Latest</th>
          <th scope="col">Last reading (UTC)</th>
          <th scope="col">Alert</th>
        </tr>
      </thead>
      <tbody>
        {sortPatients(patients).map((p) => (
          <tr key={p.id}>
            <th scope="row">
              <a href={`#/patients/${p.id}`}>{p.id}</a>
            </th>
            <td>{p.risk_group}</td>
            <td>{conditions(p)}</td>
            <td>
              <StatusBadge status={p.latest_status} />
            </td>
            <td>{p.latest_at ? dateTime(p.latest_at) : "–"}</td>
            <td>{p.open_alert ? <span className="badge badge-critical">◆ Open</span> : ""}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function Home() {
  const { session } = useAuth();
  const patients = usePatients();
  const alerts = useOpenAlerts();
  const acknowledge = useAcknowledge();
  const mine = session?.role === "admin" ? "All patients" : "My patients";

  return (
    <div className="home">
      <section className="panel" aria-labelledby="alerts-heading">
        <h2 id="alerts-heading">
          Open alerts {alerts.data && <span className="count">{alerts.data.length}</span>}
        </h2>
        {alerts.isLoading && <p className="muted">Loading…</p>}
        {alerts.error && <p className="error">{alerts.error.message}</p>}
        {alerts.data?.length === 0 && <p className="muted">No open alerts.</p>}
        <div className="alert-list">
          {alerts.data?.map((a) => (
            <AlertCard key={a.id} alert={a} busy={acknowledge.isPending}
              onAcknowledge={session?.clinicianId === a.clinician_id ? (x) => acknowledge.mutate(x) : undefined} />
          ))}
        </div>
      </section>
      <section className="panel" aria-labelledby="patients-heading">
        <h2 id="patients-heading">
          {mine} {patients.data && <span className="count">{patients.data.length}</span>}
        </h2>
        {patients.isLoading && <p className="muted">Loading…</p>}
        {patients.error && <p className="error">{patients.error.message}</p>}
        {patients.data && (
          <div className="table-scroll">
            <PatientTable patients={patients.data} />
          </div>
        )}
      </section>
    </div>
  );
}
