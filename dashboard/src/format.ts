import type { Patient, Vital } from "./api";

export const VITAL_LABEL: Record<Vital, string> = {
  heart_rate: "Heart rate",
  spo2: "SpO₂",
  systolic_bp: "Systolic BP",
  diastolic_bp: "Diastolic BP",
  temperature: "Temperature",
  glucose: "Glucose",
};

export const VITAL_UNIT: Record<Vital, string> = {
  heart_rate: "bpm",
  spo2: "%",
  systolic_bp: "mmHg",
  diastolic_bp: "mmHg",
  temperature: "°C",
  glucose: "mmol/L",
};

// API times are UTC without a zone; show them as UTC so clinicians and the alert messages agree.
export function parseUtc(value: string): Date {
  return new Date(value.endsWith("Z") ? value : `${value}Z`);
}

export function time(value: string): string {
  return parseUtc(value).toISOString().slice(11, 16);
}

export function dateTime(value: string): string {
  const iso = parseUtc(value).toISOString();
  return `${iso.slice(0, 10)} ${iso.slice(11, 16)}`;
}

export function vitalValue(vital: Vital, value: number | null | undefined): string {
  if (value === null || value === undefined) return "–";
  const digits = vital === "temperature" || vital === "glucose" ? 1 : 0;
  return `${value.toFixed(digits)} ${VITAL_UNIT[vital]}`;
}

export function conditions(p: Patient): string {
  const list = [p.hypertension && "Hypertension", p.diabetes && "Diabetes", p.arrhythmia && "Arrhythmia", p.copd && "COPD"];
  const named = list.filter(Boolean).join(", ");
  return named || "None recorded";
}

export function flagText(flag: string): string {
  const [kind, vital] = flag.split(":");
  const name = vital ? VITAL_LABEL[vital as Vital] ?? vital : "";
  switch (kind) {
    case "missing":
      return `${name} missing`;
    case "sensor_error":
      return `${name} sensor error`;
    case "stuck":
      return `${name} sensor stuck`;
    case "late":
      return "Arrived late";
    case "ignored":
      return `${name} ignored`;
    default:
      return flag;
  }
}

// The band in which a vital scores 0 points by default, from the API's band list.
export function zeroBand(bands: [number | null, number][] | undefined): { low: number | null; high: number | null } | null {
  if (!bands) return null;
  let previous: number | null = null;
  for (const [upper, points] of bands) {
    if (points === 0) return { low: previous, high: upper };
    previous = upper;
  }
  return null;
}
