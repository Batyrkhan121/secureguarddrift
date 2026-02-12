/** API entity types matching backend models. */

export interface Node {
  name: string;
  namespace: string;
  node_type: string;
  metadata?: Record<string, unknown>;
}

export interface Edge {
  source: string;
  destination: string;
  request_count: number;
  error_count: number;
  error_rate: number;
  avg_latency_ms: number;
  p99_latency_ms: number;
  metadata?: Record<string, unknown>;
}

export interface Snapshot {
  id: string;
  tenant_id: string;
  timestamp_start: string;
  timestamp_end: string;
  created_at: string;
  nodes: Node[];
  edges: Edge[];
  metadata?: Record<string, unknown>;
}

export interface SnapshotSummary {
  id: string;
  tenant_id: string;
  timestamp_start: string;
  timestamp_end: string;
  created_at: string;
  metadata?: Record<string, unknown>;
}

export interface DriftEvent {
  id: string;
  tenant_id: string;
  baseline_id: string | null;
  current_id: string | null;
  event_type: string;
  source: string;
  destination: string;
  severity: string;
  risk_score: number;
  title: string;
  what_changed: string;
  recommendation: string;
  why_risk: string[];
  affected: string[];
  rules_triggered: Record<string, unknown>;
  ml_modifiers: Record<string, unknown>;
  status: string;
  created_at: string;
}

export interface DriftSummary {
  total: number;
  critical: number;
  high: number;
  medium: number;
  low: number;
}

export interface PolicySuggestion {
  id: string;
  tenant_id: string;
  drift_event_id: string | null;
  yaml_text: string;
  reason: string;
  risk_score: number;
  status: string;
  approved_by: string | null;
  applied_at: string | null;
  created_at: string;
}

export interface Feedback {
  id: number;
  tenant_id: string;
  drift_event_id: string | null;
  user_id: string | null;
  verdict: string;
  comment: string | null;
  created_at: string;
}

export interface FeedbackStats {
  total: number;
  true_positive: number;
  false_positive: number;
  needs_review: number;
}

export interface WhitelistEntry {
  id: number;
  tenant_id: string;
  source: string;
  destination: string;
  reason: string | null;
  created_by: string | null;
  expires_at: string | null;
  created_at: string;
}

export interface Baseline {
  source: string;
  destination: string;
  mean_request_count: number;
  std_request_count: number;
  mean_error_rate: number;
  std_error_rate: number;
  mean_p99_latency: number;
  std_p99_latency: number;
  sample_count: number;
  updated_at: string;
}

export interface User {
  id: string;
  email: string;
  role: "admin" | "operator" | "viewer";
  tenant_id: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
}

export interface HealthResponse {
  status: string;
  database: string;
  version: string;
  redis?: string;
}

export interface RootCauseCandidate {
  service: string;
  confidence: number;
  reason: string;
  affected_downstream: string[];
  evidence: string[];
}

export interface RootCauseResponse {
  snapshot_id: string;
  root_causes: RootCauseCandidate[];
}

export interface BlastRadiusAffected {
  service: string;
  probability: number;
  time_to_impact_minutes: number;
  impact: string;
}

export interface BlastRadiusResponse {
  failing_service: string;
  failure_mode: string;
  affected: BlastRadiusAffected[];
  total_blast_radius: number;
  estimated_recovery_minutes: number;
}

export interface DriftPrediction {
  predicted_event: string;
  source: string;
  destination: string;
  predicted_severity: string;
  recommendation: string;
}

export interface PredictDriftResponse {
  predictions: DriftPrediction[];
}
