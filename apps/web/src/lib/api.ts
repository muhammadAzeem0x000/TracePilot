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
}

export interface IncidentCreate {
  title: string;
  description: string;
  severity: Severity;
  started_at: string;
}

interface IncidentListResponse {
  items: Incident[];
  count: number;
}

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null);
    const detail =
      typeof body === "object" && body !== null && "detail" in body
        ? String(body.detail)
        : `Request failed with status ${response.status}`;
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

