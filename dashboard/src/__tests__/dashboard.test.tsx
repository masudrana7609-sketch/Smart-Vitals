import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Patient } from "../api";
import { AuthProvider } from "../auth";
import { StatusBadge } from "../components/StatusBadge";
import { flagText, zeroBand } from "../format";
import { Login } from "../pages/Login";
import { PatientTable, sortPatients } from "../pages/Home";
import { parse } from "../route";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  sessionStorage.clear();
});

const patient = (id: string, extra: Partial<Patient> = {}): Patient => ({
  id, device_id: `W${id}`, clinician_id: "C01", age_band: "50-64", hypertension: false, diabetes: false,
  arrhythmia: false, copd: false, risk_group: "Low", risk_level: 1, spo2_scale: 1, latest_status: "Normal",
  latest_at: "2026-01-06T00:10:00", open_alert: false, ...extra,
});

describe("status is never colour alone", () => {
  it("shows a word and an icon", () => {
    render(<StatusBadge status="Critical" />);
    expect(screen.getByText(/Critical/)).toBeTruthy();
    expect(screen.getByText("◆")).toBeTruthy();
  });
});

describe("patient list", () => {
  it("puts open alerts and Critical patients first", () => {
    const sorted = sortPatients([
      patient("P001"),
      patient("P002", { latest_status: "Critical" }),
      patient("P003", { latest_status: "Warning", open_alert: true }),
    ]);
    expect(sorted.map((p) => p.id)).toEqual(["P003", "P002", "P001"]);
  });

  it("links each patient to their page", () => {
    render(<PatientTable patients={[patient("P007")]} />);
    expect(screen.getByRole("link", { name: "P007" }).getAttribute("href")).toBe("#/patients/P007");
  });
});

describe("helpers", () => {
  it("finds the default 0-point band", () => {
    expect(zeroBand([[40, 3], [50, 1], [90, 0], [110, 1], [null, 3]])).toEqual({ low: 50, high: 90 });
    expect(zeroBand([[91, 3], [93, 2], [95, 1], [null, 0]])).toEqual({ low: 95, high: null });
  });

  it("explains quality flags in words", () => {
    expect(flagText("sensor_error:heart_rate")).toBe("Heart rate sensor error");
    expect(flagText("late")).toBe("Arrived late");
  });

  it("routes by hash", () => {
    expect(parse("#/patients/P005")).toEqual({ page: "patient", id: "P005" });
    expect(parse("#/audit")).toEqual({ page: "audit" });
    expect(parse("#/patients/<script>")).toEqual({ page: "home" });
  });
});

describe("login", () => {
  it("shows the API's message when the password is wrong", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "wrong name or password" }), { status: 401 }),
    );
    render(
      <QueryClientProvider client={new QueryClient()}>
        <AuthProvider>
          <Login />
        </AuthProvider>
      </QueryClientProvider>,
    );
    fireEvent.change(screen.getByLabelText("Clinician ID"), { target: { value: "C01" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "nope" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    await waitFor(() => expect(screen.getByRole("alert").textContent).toBe("wrong name or password"));
    expect(sessionStorage.length).toBe(0);
  });
});
