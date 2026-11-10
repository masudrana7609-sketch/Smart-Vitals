// Talking to the Smart Vitals API. Every call except login sends the clinician's token.
// The API enforces who may see what (R5): the dashboard only shows what the API returns.

export type Status = "Normal" | "Warning" | "Critical";
export const VITALS = ["heart_rate", "spo2", "systolic_bp", "diastolic_bp", "temperature", "glucose"] as const;
export type Vital = (typeof VITALS)[number];

export interface Session {
  token: string;
  clinicianId: string;
  name: string;
  role: "clinician" | "admin";
  expiresAt: number; // ms since epoch
}

export interface Patient {
  id: string;
  device_id: string;
  clinician_id: string;
  age_band: string;
  hypertension: boolean;
  diabetes: boolean;
  arrhythmia: boolean;
  copd: boolean;
  risk_group: "Low" | "Medium" | "High";
  risk_level: number;
  spo2_scale: number;
  latest_status?: Status | null;
  latest_at?: string | null;
  open_alert?: boolean;
}

export interface Reading {
  msg_id: string;
  measured_at: string;
  received_at: string;
  heart_rate: number | null;
  spo2: number | null;
  systolic_bp: number | null;
  diastolic_bp: number | null;
  temperature: number | null;
  glucose: number | null;
  flags: string[];
  status: Status;
  p_critical: number;
  decided_by: string;
  news_score: number;
  score_parts: Record<string, number>;
}

export interface Alert {
  id: number;
  patient_id: string;
  clinician_id: string;
  kind: "new" | "escalation";
  state: "open" | "acknowledged" | "superseded";
  raised_at: string;
  vitals: Partial<Record<Vital, number | null>>;
  news_score: number;
  red_vitals: string[];
  p_critical: number;
  decided_by: string;
  reminders: number;
  acknowledged_at: string | null;
  acknowledged_by: string | null;
}

export interface History {
  patient: Patient;
  readings: Reading[];
  alerts: Alert[];
}

export interface Limit {
  vital: Vital;
  low: number | null;
  high: number | null;
  reason: string;
  set_by: string;
  set_at: string;
}

export interface Thresholds {
  patient_id: string;
  spo2_scale: number;
  limits: Limit[];
  defaults: Record<string, [number | null, number][]>; // [highest value in band, points]
}

export interface AuditEvent {
  at: string;
  actor: string;
  action: string;
  patient_id: string | null;
  outcome: string;
  detail: string;
}

const BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? "/api";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function errorMessage(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body.detail === "string") return body.detail;
    if (Array.isArray(body.detail)) return body.detail.map((d: { msg: string }) => d.msg).join("; ");
  } catch {
    /* not JSON */
  }
  return `request failed (${response.status})`;
}

export async function request<T>(path: string, session: Session | null, init: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (session) headers.Authorization = `Bearer ${session.token}`;
  const response = await fetch(`${BASE}${path}`, { ...init, headers });
  if (!response.ok) throw new ApiError(response.status, await errorMessage(response));
  return (await response.json()) as T;
}

export async function login(username: string, password: string): Promise<Session> {
  const body = await request<{ access_token: string; clinician_id: string; name: string; role: Session["role"]; expires_in: number }>(
    "/auth/login",
    null,
    { method: "POST", body: JSON.stringify({ username, password }) },
  );
  return {
    token: body.access_token,
    clinicianId: body.clinician_id,
    name: body.name,
    role: body.role,
    expiresAt: Date.now() + body.expires_in * 1000,
  };
}
