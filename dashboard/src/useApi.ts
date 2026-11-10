import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, request, type Alert, type AuditEvent, type History, type Patient, type Thresholds, type Vital } from "./api";
import { useAuth } from "./auth";

const LIVE = 5000; // refresh every 5 s so new alerts appear without reloading

function useRequest() {
  const { session, signOut } = useAuth();
  return async <T,>(path: string, init?: RequestInit) => {
    try {
      return await request<T>(path, session, init);
    } catch (problem) {
      if (problem instanceof ApiError && problem.status === 401) signOut();
      throw problem;
    }
  };
}

export function usePatients() {
  const call = useRequest();
  return useQuery({ queryKey: ["patients"], queryFn: () => call<Patient[]>("/patients"), refetchInterval: LIVE });
}

export function useOpenAlerts() {
  const call = useRequest();
  return useQuery({ queryKey: ["alerts", "open"], queryFn: () => call<Alert[]>("/alerts?state=open"), refetchInterval: LIVE });
}

export function useHistory(patientId: string, limit: number) {
  const call = useRequest();
  return useQuery({
    queryKey: ["history", patientId, limit],
    queryFn: () => call<History>(`/patients/${encodeURIComponent(patientId)}/history?limit=${limit}`),
    refetchInterval: LIVE,
    retry: (count, problem) => !(problem instanceof ApiError && problem.status < 500) && count < 2,
  });
}

export function useThresholds(patientId: string) {
  const call = useRequest();
  return useQuery({
    queryKey: ["thresholds", patientId],
    queryFn: () => call<Thresholds>(`/patients/${encodeURIComponent(patientId)}/thresholds`),
    retry: false,
  });
}

export function useAudit() {
  const call = useRequest();
  return useQuery({ queryKey: ["audit"], queryFn: () => call<AuditEvent[]>("/audit?limit=300"), refetchInterval: 10000 });
}

export function useAcknowledge() {
  const call = useRequest();
  const client = useQueryClient();
  return useMutation({
    mutationFn: (alert: Alert) => call<Alert>(`/alerts/${alert.id}/acknowledge`, { method: "POST" }),
    onSuccess: () => client.invalidateQueries(),
  });
}

export function useThresholdChange(patientId: string) {
  const call = useRequest();
  const client = useQueryClient();
  const refresh = () => client.invalidateQueries({ queryKey: ["thresholds", patientId] });
  const path = (vital: Vital) => `/patients/${encodeURIComponent(patientId)}/thresholds/${vital}`;
  return {
    save: async (vital: Vital, low: number | null, high: number | null, reason: string) => {
      await call(path(vital), { method: "PUT", body: JSON.stringify({ low, high, reason }) });
      await refresh();
    },
    reset: async (vital: Vital) => {
      await call(path(vital), { method: "DELETE" });
      await refresh();
    },
  };
}
