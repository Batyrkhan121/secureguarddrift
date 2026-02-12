import axios from "axios";
import type {
  AuthResponse,
  Baseline,
  DriftEvent,
  DriftSummary,
  FeedbackStats,
  HealthResponse,
  PolicySuggestion,
  Snapshot,
  SnapshotSummary,
  WhitelistEntry,
} from "./types";

const api = axios.create({ baseURL: "/api" });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("sg_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem("sg_token");
      window.location.href = "/login";
    }
    return Promise.reject(err);
  },
);

export const getHealth = () =>
  api.get<HealthResponse>("/health").then((r) => r.data);

export const getSnapshots = () =>
  api.get<SnapshotSummary[]>("/graph/snapshots").then((r) => r.data);

export const getGraphLatest = () =>
  api.get<Snapshot>("/graph/latest").then((r) => r.data);

export const getGraph = (id: string) =>
  api.get<Snapshot>(`/graph/${id}`).then((r) => r.data);

export const getDrift = (baseId?: string, currId?: string) =>
  api
    .get<DriftEvent[]>("/drift/", { params: { base_id: baseId, curr_id: currId } })
    .then((r) => r.data);

export const getDriftSummary = () =>
  api.get<DriftSummary>("/drift/summary").then((r) => r.data);

export const getPolicies = () =>
  api.get<PolicySuggestion[]>("/policy/").then((r) => r.data);

export const approvePolicy = (id: string) =>
  api.post(`/policy/${id}/approve`).then((r) => r.data);

export const rejectPolicy = (id: string) =>
  api.post(`/policy/${id}/reject`).then((r) => r.data);

export const postFeedback = (eventId: string, verdict: string, comment?: string) =>
  api.post("/ml/feedback", { event_id: eventId, verdict, comment }).then((r) => r.data);

export const getFeedbackStats = () =>
  api.get<FeedbackStats>("/ml/feedback/stats").then((r) => r.data);

export const getWhitelist = () =>
  api.get<WhitelistEntry[]>("/ml/whitelist").then((r) => r.data);

export const addWhitelist = (source: string, destination: string, reason: string) =>
  api.post("/ml/whitelist", { source, destination, reason }).then((r) => r.data);

export const removeWhitelist = (source: string, destination: string) =>
  api.delete("/ml/whitelist", { data: { source, destination } }).then((r) => r.data);

export const getBaseline = (source: string, destination: string) =>
  api.get<Baseline>(`/ml/baseline/${source}/${destination}`).then((r) => r.data);

export const login = (email: string, password: string) =>
  api.post<AuthResponse>("/auth/login", { email, password }).then((r) => r.data);

export default api;
