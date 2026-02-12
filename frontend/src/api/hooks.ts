import { useQuery } from "@tanstack/react-query";
import {
  getHealth,
  getSnapshots,
  getGraphLatest,
  getGraph,
  getDrift,
  getDriftSummary,
  getPolicies,
  getWhitelist,
  getFeedbackStats,
} from "./client";

export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
    staleTime: 30_000,
  });
}

export function useSnapshots() {
  return useQuery({
    queryKey: ["snapshots"],
    queryFn: getSnapshots,
    staleTime: 30_000,
  });
}

export function useGraph(id?: string) {
  return useQuery({
    queryKey: ["graph", id ?? "latest"],
    queryFn: () => (id ? getGraph(id) : getGraphLatest()),
    staleTime: 30_000,
  });
}

export function useDrift(baseId?: string, currId?: string) {
  return useQuery({
    queryKey: ["drift", baseId, currId],
    queryFn: () => getDrift(baseId, currId),
    staleTime: 10_000,
  });
}

export function useDriftSummary() {
  return useQuery({
    queryKey: ["driftSummary"],
    queryFn: getDriftSummary,
    staleTime: 10_000,
  });
}

export function usePolicies() {
  return useQuery({
    queryKey: ["policies"],
    queryFn: getPolicies,
    staleTime: 60_000,
  });
}

export function useWhitelist() {
  return useQuery({
    queryKey: ["whitelist"],
    queryFn: getWhitelist,
    staleTime: 60_000,
  });
}

export function useFeedbackStats() {
  return useQuery({
    queryKey: ["feedbackStats"],
    queryFn: getFeedbackStats,
    staleTime: 60_000,
  });
}
