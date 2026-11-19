import { QueryClient, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, api, apiDelete, apiPost } from "./api";
import { isActive, type AppConfig, type CreateJobBody, type Job, type JobSummary, type KeysOut, type Me } from "./types";

export const qk = {
  config: ["config"] as const,
  me: ["me"] as const,
  jobs: ["jobs"] as const,
  job: (id: string) => ["job", id] as const,
  keys: ["keys"] as const,
};

export function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 10_000,
        refetchOnWindowFocus: true,
        retry: (count, err) => !(err instanceof ApiError && [401, 404, 422].includes(err.status)) && count < 1,
      },
      mutations: { retry: false },
    },
  });
}

export const useConfig = () => useQuery({ queryKey: qk.config, queryFn: () => api<AppConfig>("/api/config"), staleTime: 5 * 60_000 });
export const useMe = (enabled = true) => useQuery({ queryKey: qk.me, queryFn: () => api<Me>("/api/me"), enabled, staleTime: 30_000 });

/** Polling 5 dtk HANYA bila ada job aktif. */
export function useJobs(enabled = true) {
  return useQuery({
    queryKey: qk.jobs,
    queryFn: () => api<JobSummary[]>("/api/jobs"),
    enabled,
    refetchInterval: (q) => ((q.state.data ?? []).some((j) => isActive(j.status)) ? 5000 : false),
  });
}

export const RETRY_STEPS = [3, 6, 12, 24, 30];
export const retryDelaySec = (failures: number) => RETRY_STEPS[Math.min(Math.max(failures - 1, 0), RETRY_STEPS.length - 1)] ?? 30;

/** Polling 1,5 dtk saat aktif; saat koneksi putus dicoba ulang 3, 6, 12 dtk … maks 30. */
export function useJob(id: string | undefined) {
  return useQuery({
    queryKey: qk.job(id ?? ""),
    queryFn: () => api<Job>(`/api/jobs/${encodeURIComponent(id ?? "")}`),
    enabled: !!id,
    retry: false,
    staleTime: 0,
    refetchInterval: (q) => {
      const err = q.state.error;
      if (err instanceof ApiError && err.status === 0) return retryDelaySec(q.state.fetchFailureCount) * 1000;
      if (err) return false;
      const st = q.state.data?.status;
      return st && isActive(st) ? 1500 : false;
    },
  });
}

export const useKeys = (enabled = true) => useQuery({ queryKey: qk.keys, queryFn: () => api<KeysOut>("/api/keys"), enabled });

export function useCreateJob() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: CreateJobBody) => apiPost<Job>("/api/jobs", body),
    onSuccess: (job) => {
      qc.setQueryData(qk.job(job.id), job);
      void qc.invalidateQueries({ queryKey: qk.jobs });
      void qc.invalidateQueries({ queryKey: qk.me });
      void qc.invalidateQueries({ queryKey: qk.config });
      void qc.invalidateQueries({ queryKey: qk.keys });
    },
  });
}

export function useDeleteJob() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiDelete<{ result: "deleted" | "cancelled" }>(`/api/jobs/${encodeURIComponent(id)}`),
    onSuccess: (_r, id) => {
      qc.removeQueries({ queryKey: qk.job(id) });
      void qc.invalidateQueries({ queryKey: qk.jobs });
      void qc.invalidateQueries({ queryKey: qk.me });
      void qc.invalidateQueries({ queryKey: qk.config });
    },
  });
}

export function useDeleteKey() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (provider: string) => apiDelete<{ result: string }>(`/api/keys/${encodeURIComponent(provider)}`),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: qk.keys }); },
  });
}
