export const severities = ["low", "medium", "high", "critical"] as const;
export const incidentStatuses = ["open", "investigating", "resolved"] as const;

export type Severity = (typeof severities)[number];
export type IncidentStatus = (typeof incidentStatuses)[number];

export interface Incident {
  id: string;
  title: string;
  description: string;
  severity: Severity;
  status: IncidentStatus;
  started_at: string;
  created_at: string;
  updated_at: string;
  repository_full_name: string | null;
}

export interface IncidentCreate {
  title: string;
  description: string;
  severity: Severity;
  started_at: string;
  repository_full_name?: string;
}

interface IncidentListResponse {
  items: Incident[];
  count: number;
}

export type InvestigationStatus = "pending" | "in_progress" | "completed" | "failed";

export interface Evidence {
  id: string;
  incident_id: string;
  investigation_id: string | null;
  source_type:
    | "github_commit"
    | "github_commit_search"
    | "github_pull_request"
    | "github_pull_request_search"
    | "github_pull_request_file"
    | "knowledge_chunk";
  source_reference: string | null;
  content: string;
  metadata: Record<string, string | number | boolean | null>;
  collected_at: string;
}

export interface Investigation {
  id: string;
  incident_id: string;
  status: InvestigationStatus;
  summary: string | null;
  confidence: number | null;
  suspected_change: string | null;
  supporting_evidence_ids: string[];
  missing_information: string[];
  recommended_next_steps: string[];
  error_message: string | null;
  prompt_version: string | null;
  model_name: string | null;
  started_at: string;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

interface EvidenceListResponse {
  items: Evidence[];
  count: number;
}

interface InvestigationListResponse {
  items: Investigation[];
  count: number;
}

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null);
    let detail = `Request failed with status ${response.status}`;
    if (typeof body === "object" && body !== null && "detail" in body) {
      const responseDetail = body.detail;
      if (typeof responseDetail === "string") detail = responseDetail;
      if (
        typeof responseDetail === "object" &&
        responseDetail !== null &&
        "message" in responseDetail &&
        typeof responseDetail.message === "string"
      ) {
        detail = responseDetail.message;
      }
    }
    throw new Error(detail);
  }
  return (await response.json()) as T;
}

export async function listIncidents(): Promise<Incident[]> {
  const response = await fetch(`${apiUrl}/api/v1/incidents`, { cache: "no-store" });
  const result = await parseResponse<IncidentListResponse>(response);
  return result.items;
}

export async function createIncident(input: IncidentCreate): Promise<Incident> {
  const response = await fetch(`${apiUrl}/api/v1/incidents`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  return parseResponse<Incident>(response);
}

export async function getIncident(incidentId: string): Promise<Incident> {
  const response = await fetch(`${apiUrl}/api/v1/incidents/${incidentId}`, {
    cache: "no-store",
  });
  return parseResponse<Incident>(response);
}

export async function listEvidence(incidentId: string): Promise<Evidence[]> {
  const response = await fetch(`${apiUrl}/api/v1/incidents/${incidentId}/evidence`, {
    cache: "no-store",
  });
  const result = await parseResponse<EvidenceListResponse>(response);
  return result.items;
}

export async function listInvestigations(incidentId: string): Promise<Investigation[]> {
  const response = await fetch(`${apiUrl}/api/v1/incidents/${incidentId}/investigations`, {
    cache: "no-store",
  });
  const result = await parseResponse<InvestigationListResponse>(response);
  return result.items;
}

export async function runInvestigation(incidentId: string): Promise<Investigation> {
  const response = await fetch(`${apiUrl}/api/v1/incidents/${incidentId}/investigations`, {
    method: "POST",
    headers: { Accept: "application/json" },
  });
  return parseResponse<Investigation>(response);
}

export async function getInvestigation(investigationId: string): Promise<Investigation> {
  const response = await fetch(`${apiUrl}/api/v1/investigations/${investigationId}`, {
    cache: "no-store",
  });
  return parseResponse<Investigation>(response);
}
