"use client";

import { FormEvent, useEffect, useState } from "react";

import {
  createIncident,
  Evidence,
  getIncident,
  getInvestigation,
  Incident,
  Investigation,
  listEvidence,
  listIncidents,
  listInvestigations,
  reviewInvestigation,
  runInvestigation,
  Severity,
  severities,
} from "@/lib/api";

function formatDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function currentLocalDatetime(): string {
  const now = new Date();
  const localTime = new Date(now.getTime() - now.getTimezoneOffset() * 60_000);
  return localTime.toISOString().slice(0, 16);
}

function messageFrom(reason: unknown, fallback: string): string {
  return reason instanceof Error ? reason.message : fallback;
}

function evidenceLabel(evidence: Evidence): string {
  try {
    const content: unknown = JSON.parse(evidence.content);
    if (typeof content === "object" && content !== null) {
      if ("message" in content && typeof content.message === "string") return content.message;
      if ("title" in content && typeof content.title === "string") return content.title;
      if ("filename" in content && typeof content.filename === "string") return content.filename;
    }
  } catch {
    // The durable source reference below remains a safe display fallback.
  }
  return evidence.source_reference ?? evidence.source_type;
}

function evidenceOrigin(evidence: Evidence): string {
  if (evidence.source_type !== "knowledge_chunk") return evidence.source_type.replaceAll("_", " ");
  const sourceType = evidence.metadata.knowledge_source_type;
  return typeof sourceType === "string" ? sourceType.replaceAll("_", " ") : "knowledge";
}

export default function Home() {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [selected, setSelected] = useState<Incident | null>(null);
  const [evidence, setEvidence] = useState<Evidence[]>([]);
  const [investigations, setInvestigations] = useState<Investigation[]>([]);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [severity, setSeverity] = useState<Severity>("medium");
  const [startedAt, setStartedAt] = useState(currentLocalDatetime);
  const [repositoryFullName, setRepositoryFullName] = useState("");
  const [loading, setLoading] = useState(true);
  const [detailsLoading, setDetailsLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [running, setRunning] = useState(false);
  const [reviewing, setReviewing] = useState(false);
  const [reviewNote, setReviewNote] = useState("");
  const [error, setError] = useState<string | null>(null);

  const latestInvestigation = investigations[0] ?? null;
  const investigationActive =
    latestInvestigation?.status === "pending" || latestInvestigation?.status === "in_progress";
  const activeInvestigationId =
    investigationActive && latestInvestigation ? latestInvestigation.id : null;

  useEffect(() => {
    let active = true;
    listIncidents()
      .then((items) => {
        if (active) setIncidents(items);
      })
      .catch((reason: unknown) => {
        if (active) setError(messageFrom(reason, "Unable to load incidents"));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    const incidentId = selected?.id;
    if (!incidentId || !activeInvestigationId) return;
    const investigationId: string = activeInvestigationId;
    const selectedIncidentId: string = incidentId;

    let active = true;
    async function poll() {
      try {
        const updated = await getInvestigation(investigationId);
        if (!active) return;
        setInvestigations((current) => [
          updated,
          ...current.filter((item) => item.id !== updated.id),
        ]);
        if (updated.status === "completed" || updated.status === "failed") {
          const collectedEvidence = await listEvidence(selectedIncidentId);
          if (active) setEvidence(collectedEvidence);
        }
      } catch (reason: unknown) {
        if (active) setError(messageFrom(reason, "Unable to refresh investigation progress"));
      }
    }

    void poll();
    const timer = window.setInterval(() => void poll(), 1_500);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [activeInvestigationId, selected?.id]);

  async function loadIncidentContext(incidentId: string) {
    const [incident, collectedEvidence, existingInvestigations] = await Promise.all([
      getIncident(incidentId),
      listEvidence(incidentId),
      listInvestigations(incidentId),
    ]);
    setSelected(incident);
    setEvidence(collectedEvidence);
    setInvestigations(existingInvestigations);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const parsedStartedAt = new Date(startedAt);
    if (!startedAt || Number.isNaN(parsedStartedAt.getTime())) {
      setError("Enter a valid started time");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const created = await createIncident({
        title,
        description,
        severity,
        started_at: parsedStartedAt.toISOString(),
        repository_full_name: repositoryFullName || undefined,
      });
      setIncidents((current) => [created, ...current]);
      setSelected(created);
      setEvidence([]);
      setInvestigations([]);
      setTitle("");
      setDescription("");
      setSeverity("medium");
      setStartedAt(currentLocalDatetime());
      setRepositoryFullName("");
    } catch (reason: unknown) {
      setError(messageFrom(reason, "Unable to create incident"));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleSelect(incidentId: string) {
    setError(null);
    setDetailsLoading(true);
    try {
      await loadIncidentContext(incidentId);
    } catch (reason: unknown) {
      setError(messageFrom(reason, "Unable to load incident details"));
    } finally {
      setDetailsLoading(false);
    }
  }

  async function handleRunInvestigation() {
    if (!selected) return;
    setRunning(true);
    setError(null);
    try {
      const accepted = await runInvestigation(selected.id);
      const queued = await getInvestigation(accepted.investigation_id);
      setInvestigations((current) => [
        queued,
        ...current.filter((item) => item.id !== queued.id),
      ]);
    } catch (reason: unknown) {
      setError(messageFrom(reason, "Investigation failed"));
      await loadIncidentContext(selected.id).catch(() => undefined);
    } finally {
      setRunning(false);
    }
  }

  async function handleReview(decision: "accepted" | "rejected") {
    if (!latestInvestigation || latestInvestigation.status !== "completed") return;
    setReviewing(true);
    setError(null);
    try {
      const review = await reviewInvestigation(
        latestInvestigation.id,
        decision,
        reviewNote || undefined,
      );
      setInvestigations((current) =>
        current.map((item) =>
          item.id === latestInvestigation.id ? { ...item, review } : item,
        ),
      );
      setReviewNote("");
    } catch (reason: unknown) {
      setError(messageFrom(reason, "Unable to save human review"));
    } finally {
      setReviewing(false);
    }
  }

  return (
    <main>
      <header className="hero">
        <div className="eyebrow">Day 4 · Durable investigation workflow</div>
        <h1>TracePilot</h1>
        <p>Evidence-Grounded Incident Investigation</p>
      </header>

      {error && <div className="error" role="alert">{error}</div>}

      <div className="workspace">
        <section className="panel">
          <div className="section-heading">
            <span className="step">01</span>
            <div><h2>Create Incident</h2><p>Record facts and repository context.</p></div>
          </div>
          <form onSubmit={handleSubmit}>
            <label>Title<input required minLength={3} maxLength={200} value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Checkout error spike" /></label>
            <label>Description<textarea required maxLength={10000} rows={5} value={description} onChange={(event) => setDescription(event.target.value)} placeholder="What is failing, and who is affected?" /></label>
            <label>GitHub repository <span className="optional">optional</span><input pattern="[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9._-]{1,100}" value={repositoryFullName} onChange={(event) => setRepositoryFullName(event.target.value)} placeholder="owner/repository" /></label>
            <div className="form-row">
              <label>Severity<select value={severity} onChange={(event) => setSeverity(event.target.value as Severity)}>{severities.map((value) => <option key={value} value={value}>{value}</option>)}</select></label>
              <label>Started time<input required type="datetime-local" value={startedAt} onChange={(event) => setStartedAt(event.target.value)} /></label>
            </div>
            <button type="submit" disabled={submitting}>{submitting ? "Creating…" : "Create incident"}</button>
          </form>
        </section>

        <section className="panel incidents-panel">
          <div className="section-heading">
            <span className="step">02</span>
            <div><h2>Incidents</h2><p>{incidents.length} recorded</p></div>
          </div>
          {loading ? <p className="empty">Loading incidents…</p> : incidents.length === 0 ? <p className="empty">No incidents yet.</p> : (
            <div className="incident-list">{incidents.map((incident) => (
              <button className={`incident-card ${selected?.id === incident.id ? "selected" : ""}`} key={incident.id} onClick={() => handleSelect(incident.id)} type="button">
                <div><h3>{incident.title}</h3><time>{formatDate(incident.created_at)}</time></div>
                <div className="badges"><span className={`badge severity-${incident.severity}`}>{incident.severity}</span><span className="badge status">{incident.status}</span></div>
              </button>
            ))}</div>
          )}

          {selected && (
            <article className="details">
              <div className="details-heading"><span className={`badge severity-${selected.severity}`}>{selected.severity}</span><span className="badge status">{selected.status}</span></div>
              <h3>{selected.title}</h3><p>{selected.description}</p>
              <dl>
                {selected.repository_full_name && <div><dt>Repository</dt><dd className="mono">{selected.repository_full_name}</dd></div>}
                <div><dt>Started</dt><dd>{formatDate(selected.started_at)}</dd></div>
                <div><dt>Incident ID</dt><dd className="mono">{selected.id}</dd></div>
              </dl>
              {selected.repository_full_name ? <button className="run-button" type="button" disabled={running || detailsLoading || investigationActive} onClick={handleRunInvestigation}>{running ? "Queuing…" : investigationActive ? "Investigation in progress" : "Run investigation"}</button> : <p className="notice">Add repository context to run an evidence-grounded investigation.</p>}
            </article>
          )}
        </section>
      </div>

      {selected && (
        <section className="results-grid" aria-busy={detailsLoading}>
          <article className="result-panel evidence-panel">
            <div className="result-label factual">Factual collected evidence</div>
            <h2>EVIDENCE</h2>
            <p className="boundary-copy">Read-only GitHub records and knowledge chunks retrieved and stored by TracePilot.</p>
            {evidence.length === 0 ? <p className="empty">No evidence collected yet.</p> : <div className="evidence-list">{evidence.map((item) => (
              <article className="evidence-card" id={`evidence-${item.id}`} key={item.id}>
                <div><span className={`badge source ${item.source_type === "knowledge_chunk" ? "knowledge-source" : ""}`}>{evidenceOrigin(item)}</span><time>{formatDate(item.collected_at)}</time></div>
                <h3>{evidenceLabel(item)}</h3>
                <p className="mono">{item.source_reference}</p>
                {item.source_type === "knowledge_chunk" && <details className="retrieval-details"><summary>Retrieval details</summary><pre>{JSON.stringify(item.metadata, null, 2)}</pre></details>}
                <small className="mono">Evidence ID: {item.id}</small>
              </article>
            ))}</div>}
          </article>

          <article className="result-panel hypothesis-panel">
            <div className="result-label inferred">Model-generated inference</div>
            <h2>AI PRELIMINARY HYPOTHESIS</h2>
            <p className="boundary-copy">A validated conclusion, not a confirmed root cause.</p>
            {!latestInvestigation ? <p className="empty">No investigation run yet.</p> : (
              <div className="hypothesis">
                <div className="hypothesis-meta"><span className={`badge investigation-${latestInvestigation.status}`}>{latestInvestigation.stage.replaceAll("_", " ")}</span>{latestInvestigation.confidence !== null && <strong>{Math.round(latestInvestigation.confidence * 100)}% confidence</strong>}</div>
                {latestInvestigation.status === "failed" ? <p className="failure-copy">{latestInvestigation.error_message}</p> : <>
                  {latestInvestigation.status !== "completed" ? <div className="progress-copy"><span className="progress-dot" aria-hidden="true" /><div><strong>Background worker active</strong><p>This page is polling durable progress. You can safely navigate away.</p></div></div> : <>
                  <h3>Summary</h3><p>{latestInvestigation.summary ?? "Awaiting a conclusion."}</p>
                  <h3>Suspected change</h3><p>{latestInvestigation.suspected_change ?? "No specific change identified."}</p>
                  <h3>Suspected culprit ID</h3><p className="mono">{latestInvestigation.suspected_culprit_id ?? "No evidence source selected."}</p>
                  <h3>Supporting evidence</h3>{latestInvestigation.supporting_evidence_ids.length === 0 ? <p>None cited.</p> : <ul>{latestInvestigation.supporting_evidence_ids.map((id) => <li key={id}><a href={`#evidence-${id}`} className="mono">{id}</a></li>)}</ul>}
                  <h3>Missing information</h3><ul>{latestInvestigation.missing_information.map((item) => <li key={item}>{item}</li>)}</ul>
                  <h3>Recommended next steps</h3><ol>{latestInvestigation.recommended_next_steps.map((item) => <li key={item}>{item}</li>)}</ol>
                  <section className="human-review">
                    <h3>HUMAN REVIEW</h3>
                    <p className="boundary-copy">A separate human decision; it never edits the AI conclusion.</p>
                    {latestInvestigation.review ? <div className={`review-decision review-${latestInvestigation.review.decision}`}><strong>{latestInvestigation.review.decision}</strong>{latestInvestigation.review.note && <p>{latestInvestigation.review.note}</p>}<small>{formatDate(latestInvestigation.review.reviewed_at)}</small></div> : <>
                      <label>Review note <span className="optional">optional</span><textarea maxLength={2000} rows={3} value={reviewNote} onChange={(event) => setReviewNote(event.target.value)} placeholder="Why do you accept or reject this preliminary conclusion?" /></label>
                      <div className="review-actions"><button type="button" disabled={reviewing} onClick={() => handleReview("accepted")}>Accept</button><button className="reject-button" type="button" disabled={reviewing} onClick={() => handleReview("rejected")}>Reject</button></div>
                    </>}
                  </section>
                  </>}
                </>}
                <small className="model-note">{latestInvestigation.prompt_version} · {latestInvestigation.model_name}{latestInvestigation.duration_ms !== null ? ` · ${(latestInvestigation.duration_ms / 1000).toFixed(1)}s · ${latestInvestigation.tool_call_count} tools` : ""}</small>
              </div>
            )}
          </article>
        </section>
      )}
    </main>
  );
}
