import { dateTime } from "../format";
import { useAudit } from "../useApi";

export function Audit() {
  const audit = useAudit();
  return (
    <section className="panel" aria-labelledby="audit-heading">
      <h2 id="audit-heading">Audit log</h2>
      <p className="muted small">Every login, view, change and refused access (newest first, real time, UTC).</p>
      {audit.error && <p className="error">{audit.error.message}</p>}
      <div className="table-scroll">
        <table className="table">
          <thead>
            <tr>
              <th scope="col">When</th>
              <th scope="col">Who</th>
              <th scope="col">Action</th>
              <th scope="col">Patient</th>
              <th scope="col">Outcome</th>
              <th scope="col">Detail</th>
            </tr>
          </thead>
          <tbody>
            {audit.data?.map((e, i) => (
              <tr key={i} className={e.outcome !== "ok" ? "row-flag" : undefined}>
                <td>{dateTime(e.at)}</td>
                <td>{e.actor}</td>
                <td>{e.action}</td>
                <td>{e.patient_id ?? ""}</td>
                <td>{e.outcome}</td>
                <td className="small">{e.detail}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
