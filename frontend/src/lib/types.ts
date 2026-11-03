export type Vector = "batch" | "counterfeit" | "dark_store" | "review";
import type { components } from "./api-schema";
export interface ReferenceCase {
  id: string;
  brand: string;
  product: string;
  title: string;
  category: string;
  published_at: string;
  jurisdiction: string;
  status: string;
  aliases: string[];
  summary: string;
  findings: string[];
  company_response: string;
  limitations: string;
  sources: {
    title: string;
    publisher: string;
    url: string;
    published_at: string | null;
    kind: string;
    supports: string;
  }[];
  reviewed_at?: string;
}
export type Scores = components["schemas"]["SubScores"];
export type Attribution = {
  batch: number;
  counterfeit: number;
  dark_store: number;
};
export interface CaseSummary {
  id: string;
  title: string;
  subtitle: string;
  product_name: string;
  brand_name: string;
  risk_score: number;
  sub_scores: Scores;
  attribution: Attribution;
  dominant_vector: Vector;
  delta_velocity_48h: number;
  complaint_count_48h: number;
  cities: string[];
  synthetic: boolean;
  updated_at: string;
  status: string;
}
export interface Packet {
  id: string;
  kind: string;
  version: number;
  title: string;
  created_at: string;
}
export interface Grievance {
  id: string;
  status: string;
  days_elapsed: number;
  due_at: string;
  seconds_remaining: number;
  escalation_due: boolean;
  description?: string;
  internal_priority_due_at: string | null;
}
export interface CaseDetail extends CaseSummary {
  summary: string;
  provenance?: string;
  score_history: { label: string; risk: number }[];
  assessment: {
    score: number;
    base_score: number;
    amplification: number;
    pre_recall_factor: number;
    velocity: number;
    policy_version: string;
    baseline_available?: boolean;
    evidence_policy?: { note: string };
  };
  products: { name: string; brand: string; pack_size?: string }[];
  attribution_reasons: Record<string, string[]>;
  batches: { lot: string; manufactured: string; best_before: string }[];
  fbo?: { name: string; license_no: string };
  packets: Packet[];
  grievances: Grievance[];
  regulatory_records: {
    id: string;
    source: string;
    action_type: string;
    reason_for_recall: string;
    start_date: string;
    synthetic: boolean;
  }[];
  dark_store_nodes?: {
    id: string;
    name: string;
    city: string;
    radius_km: number;
    complaints: number;
  }[];
  audit_events: { event: string; timestamp: string }[];
  authority_queries?: {
    id: string;
    reference: string;
    received_at: string;
    due_at: string;
    status: string;
  }[];
  recall_workflow?: {
    decision_at: string;
    notification_due_at: string;
    next_weekly_status_due_at: string;
    reports: {
      submitted_at: string;
      distributed_units: number;
      recovered_units: number;
      effectiveness_notes: string;
    }[];
  };
}
export interface Entity {
  text: string;
  kind: "symptom" | "hazard" | "batch" | "counterfeit" | "location" | "product";
  normalized: string;
  severity: number;
}
export interface Signal {
  id: string;
  case_id: string;
  platform: string;
  source_url: string;
  timestamp: string;
  product_name: string;
  text: string;
  language: string;
  evidence_type: string;
  verified_purchase: boolean;
  lab_evidence: string;
  synthetic: boolean;
  entities: Entity[];
  clinical: {
    onset_latency_hours: number | null;
    symptom_duration_days: number | null;
    dechallenge_status: string;
    rechallenge_status: string;
    concomitant_products: string[];
  };
  geography: {
    city?: string | null;
    node_name?: string | null;
    pin_code_prefix?: string | null;
  };
  extraction_method: string;
  redacted_fields: string[];
  privacy_status: string;
  warnings: string[];
}
export interface EvidenceResponse {
  items: Signal[];
  total: number;
  platforms: string[];
}
export interface Telemetry {
  active_cases: number;
  high_risk_cases: number;
  velocity_alerts: number;
  pending_grievances: number;
  evidence_count: number;
  privacy_status: string;
  synthetic_cases: number;
  live_cases: number;
  last_updated: string;
  providers: Record<string, boolean>;
  task_mode: string;
}
export interface Scan {
  id: string;
  state: "queued" | "running" | "completed" | "partial" | "failed";
  results: {
    sources?: Record<
      string,
      { status: string; count: number; message: string }
    >;
    relevant_count?: number;
    collected_count?: number;
    case_ids?: string[];
    warnings?: string[];
    message?: string;
  };
}
export interface GraphData {
  nodes: { id: string; label: string; kind: string; license: string | null }[];
  edges: { id: string; source: string; target: string; label: string }[];
  facility_alerts: { license: string; brands: string[]; message: string }[];
}
