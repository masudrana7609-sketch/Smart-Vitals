import { useAuth } from "./auth";
import { Audit } from "./pages/Audit";
import { Home } from "./pages/Home";
import { Login } from "./pages/Login";
import { PatientDetail } from "./pages/PatientDetail";
import { useRoute } from "./route";

export function App() {
  const { session, signOut } = useAuth();
  const route = useRoute();
  if (!session) return <Login />;

  return (
    <>
      <header className="topbar">
        <a href="#/" className="brand">
          Smart Vitals
        </a>
        <nav aria-label="Main">
          <a href="#/" aria-current={route.page === "home" ? "page" : undefined}>
            {session.role === "admin" ? "Patients" : "My patients"}
          </a>
          {session.role === "admin" && (
            <a href="#/audit" aria-current={route.page === "audit" ? "page" : undefined}>
              Audit log
            </a>
          )}
        </nav>
        <span className="who">
          {session.name} ({session.clinicianId})
        </span>
        <button type="button" className="button button-quiet" onClick={signOut}>
          Sign out
        </button>
      </header>
      <p className="banner">Prototype · simulated data only · not a medical device</p>
      <main className="content">
        {route.page === "home" && <Home />}
        {route.page === "patient" && <PatientDetail id={route.id} />}
        {route.page === "audit" && <Audit />}
      </main>
    </>
  );
}
