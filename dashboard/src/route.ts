import { useEffect, useState } from "react";

// Three screens, addressed by the URL hash so the browser's back button works: #/, #/patients/P001, #/audit.
export type Route = { page: "home" } | { page: "patient"; id: string } | { page: "audit" };

export function parse(hash: string): Route {
  const patient = hash.match(/^#\/patients\/([A-Za-z0-9_-]+)$/);
  if (patient) return { page: "patient", id: patient[1] };
  if (hash === "#/audit") return { page: "audit" };
  return { page: "home" };
}

export function useRoute(): Route {
  const [route, setRoute] = useState(() => parse(window.location.hash));
  useEffect(() => {
    const onChange = () => setRoute(parse(window.location.hash));
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  return route;
}
