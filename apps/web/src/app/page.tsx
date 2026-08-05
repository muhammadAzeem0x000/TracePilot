"use client";

import { FormEvent, useEffect, useState } from "react";

import {
  createIncident,
  getIncident,
  Incident,
  listIncidents,
  Severity,
  severities,
} from "@/lib/api";

function formatDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function severityClass(severity: Severity): string {
  return `badge severity-${severity}`;
}

function currentLocalDatetime(): string {
  const now = new Date();
  const localTime = new Date(now.getTime() - now.getTimezoneOffset() * 60_000);
  return localTime.toISOString().slice(0, 16);
}

export default function Home() {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [selected, setSelected] = useState<Incident | null>(null);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [severity, setSeverity] = useState<Severity>("medium");
  const [startedAt, setStartedAt] = useState(currentLocalDatetime);
  const [repositoryFullName, setRepositoryFullName] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    listIncidents()
      .then((items) => {
        if (active) setIncidents(items);
      })
      .catch((reason: unknown) => {
        if (active) setError(reason instanceof Error ? reason.message : "Unable to load incidents");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

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
      setTitle("");
      setDescription("");
      setSeverity("medium");
      setStartedAt(currentLocalDatetime());
      setRepositoryFullName("");
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "Unable to create incident");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleSelect(incidentId: string) {
    setError(null);
    try {
      setSelected(await getIncident(incidentId));
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "Unable to load incident details");
    }
  }

  return (
    <main>
      <header className="hero">
        <div className="eyebrow">Day 1 · Software foundation</div>
        <h1>TracePilot</h1>
        <p>Evidence-Grounded Incident Investigation</p>
      </header>

      {error && <div className="error" role="alert">{error}</div>}

      <div className="workspace">
        <section className="panel">
          <div className="section-heading">
            <span className="step">01</span>
            <div>
              <h2>Create Incident</h2>
              <p>Record the facts known at the start of an incident.</p>
            </div>
          </div>

          <form onSubmit={handleSubmit}>
            <label>
              Title
              <input
                required
                minLength={3}
                maxLength={200}
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                placeholder="Checkout error spike"
              />
            </label>
            <label>
              Description
              <textarea
                required
                maxLength={10000}
                rows={5}
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                placeholder="What is failing, and who is affected?"
              />
            </label>
            <label>
              GitHub repository <span className="optional">optional</span>
              <input
                pattern="[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9._-]{1,100}"
                value={repositoryFullName}
                onChange={(event) => setRepositoryFullName(event.target.value)}
                placeholder="owner/repository"
              />
            </label>
            <div className="form-row">
              <label>
                Severity
                <select value={severity} onChange={(event) => setSeverity(event.target.value as Severity)}>
                  {severities.map((value) => (
                    <option key={value} value={value}>{value}</option>
                  ))}
                </select>
              </label>
              <label>
                Started time
                <input
                  required
                  type="datetime-local"
                  value={startedAt}
                  onChange={(event) => setStartedAt(event.target.value)}
                />
              </label>
            </div>
            <button type="submit" disabled={submitting}>
              {submitting ? "Creating…" : "Create incident"}
            </button>
          </form>
        </section>

        <section className="panel incidents-panel">
          <div className="section-heading">
            <span className="step">02</span>
            <div>
              <h2>Incidents</h2>
              <p>{incidents.length} recorded</p>
            </div>
          </div>

          {loading ? (
            <p className="empty">Loading incidents…</p>
          ) : incidents.length === 0 ? (
            <p className="empty">No incidents yet. Create the first record.</p>
          ) : (
            <div className="incident-list">
              {incidents.map((incident) => (
                <button
                  className={`incident-card ${selected?.id === incident.id ? "selected" : ""}`}
                  key={incident.id}
                  onClick={() => handleSelect(incident.id)}
                  type="button"
                >
                  <div>
                    <h3>{incident.title}</h3>
                    <time>{formatDate(incident.created_at)}</time>
                  </div>
                  <div className="badges">
                    <span className={severityClass(incident.severity)}>{incident.severity}</span>
                    <span className="badge status">{incident.status}</span>
                  </div>
                </button>
              ))}
            </div>
          )}

          {selected && (
            <article className="details">
              <div className="details-heading">
                <span className={severityClass(selected.severity)}>{selected.severity}</span>
                <span className="badge status">{selected.status}</span>
              </div>
              <h3>{selected.title}</h3>
              <p>{selected.description}</p>
              <dl>
                {selected.repository_full_name && (
                  <div><dt>Repository</dt><dd className="mono">{selected.repository_full_name}</dd></div>
                )}
                <div><dt>Started</dt><dd>{formatDate(selected.started_at)}</dd></div>
                <div><dt>Created</dt><dd>{formatDate(selected.created_at)}</dd></div>
                <div><dt>Incident ID</dt><dd className="mono">{selected.id}</dd></div>
              </dl>
            </article>
          )}
        </section>
      </div>
    </main>
  );
}
