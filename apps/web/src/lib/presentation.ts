import { Evidence, InvestigationStage } from "@/lib/api";

export function formatDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export function formatCompactDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

export function currentLocalDatetime(): string {
  const now = new Date();
  const localTime = new Date(now.getTime() - now.getTimezoneOffset() * 60_000);
  return localTime.toISOString().slice(0, 16);
}

export function messageFrom(reason: unknown, fallback: string): string {
  return reason instanceof Error ? reason.message : fallback;
}

export function evidenceLabel(evidence: Evidence): string {
  try {
    const content: unknown = JSON.parse(evidence.content);
    if (typeof content === "object" && content !== null) {
      if ("message" in content && typeof content.message === "string") return content.message;
      if ("title" in content && typeof content.title === "string") return content.title;
      if ("filename" in content && typeof content.filename === "string") return content.filename;
    }
  } catch {
    // Durable source references remain the safe fallback for non-JSON Evidence.
  }
  return evidence.source_reference ?? evidence.source_type.replaceAll("_", " ");
}

export function evidenceOrigin(evidence: Evidence): string {
  if (evidence.source_type !== "knowledge_chunk") {
    return evidence.source_type.replaceAll("_", " ");
  }
  const sourceType = evidence.metadata.knowledge_source_type;
  return typeof sourceType === "string" ? sourceType.replaceAll("_", " ") : "knowledge";
}

export function stageLabel(stage: InvestigationStage): string {
  return stage.replaceAll("_", " ");
}

export function formatDuration(milliseconds: number): string {
  if (milliseconds < 1_000) return `${Math.round(milliseconds)} ms`;
  return `${(milliseconds / 1_000).toFixed(milliseconds >= 10_000 ? 1 : 2)} s`;
}
