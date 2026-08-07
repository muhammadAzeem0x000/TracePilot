"use client";

import { KeyboardEvent, useMemo, useState } from "react";

import { Icon, IconName } from "@/components/Icon";
import { Evidence, Incident, Investigation, InvestigationMetrics } from "@/lib/api";
import {
  evidenceLabel,
  evidenceOrigin,
  formatDate,
  formatDuration,
  stageLabel,
} from "@/lib/presentation";

type WorkspaceTab = "overview" | "evidence" | "investigation" | "metrics";

interface IncidentWorkspaceProps {
  incident: Incident | null;
  evidence: Evidence[];
  investigations: Investigation[];
  metrics: InvestigationMetrics | null;
  detailsLoading: boolean;
  publicDemoMode: boolean;
  running: boolean;
  reviewing: boolean;
  reviewNote: string;
  onBack: () => void;
  onCreate: () => void;
  onRunInvestigation: () => void;
  onReview: (decision: "accepted" | "rejected") => void;
  onReviewNoteChange: (value: string) => void;
}

interface TabDefinition {
  id: WorkspaceTab;
  label: string;
  icon: IconName;
}

const tabs: TabDefinition[] = [
  { id: "overview", label: "Overview", icon: "overview" },
  { id: "evidence", label: "Evidence", icon: "evidence" },
  { id: "investigation", label: "Investigation", icon: "sparkles" },
  { id: "metrics", label: "Metrics", icon: "metrics" },
];

function TabCount({ value }: { value: number }) {
  return value > 0 ? <span className="tab-count">{value}</span> : null;
}

function EmptyWorkspace({ publicDemoMode, onCreate }: Pick<IncidentWorkspaceProps, "publicDemoMode" | "onCreate">) {
  return (
    <section className="detail-pane empty-workspace" aria-label="Incident details">
      <div className="empty-workspace-visual" aria-hidden="true">
        <div className="visual-orbit visual-orbit-one" />
        <div className="visual-orbit visual-orbit-two" />
        <div className="visual-center"><Icon name="activity" size={30} /></div>
      </div>
      <p className="section-kicker">Investigation workspace</p>
      <h2>Select an incident to begin</h2>
      <p>Choose an incident from the navigator to inspect its context, collected Evidence, preliminary hypothesis, and execution metrics.</p>
      {!publicDemoMode && (
        <button className="primary-button" type="button" onClick={onCreate}>
          <Icon name="plus" size={16} />
          Create an incident
        </button>
      )}
      <div className="workspace-capabilities" aria-label="Workspace capabilities">
        <span><Icon name="evidence" size={15} /> Evidence provenance</span>
        <span><Icon name="sparkles" size={15} /> Validated hypothesis</span>
        <span><Icon name="metrics" size={15} /> Execution metrics</span>
      </div>
    </section>
  );
}

function DetailSkeleton() {
  return (
    <div className="detail-skeleton" aria-label="Loading incident details">
      <span className="skeleton-line skeleton-line-wide" />
      <span className="skeleton-line" />
      <div className="skeleton-card-row"><span /><span /><span /></div>
      <span className="skeleton-block" />
    </div>
  );
}

function OverviewPanel({ incident, investigations }: { incident: Incident; investigations: Investigation[] }) {
  const latest = investigations[0] ?? null;
  return (
    <div className="tab-panel overview-panel" id="panel-overview" role="tabpanel" aria-labelledby="tab-overview">
      <div className="overview-grid">
        <article className="content-card overview-description">
          <div className="card-heading">
            <div className="card-icon"><Icon name="info" size={17} /></div>
            <div><p className="section-kicker">Incident context</p><h3>Description</h3></div>
          </div>
          <p className="incident-description">{incident.description}</p>
        </article>

        <aside className="content-card incident-metadata-card">
          <p className="section-kicker">Record details</p>
          <dl className="metadata-list">
            <div><dt>Started</dt><dd>{formatDate(incident.started_at)}</dd></div>
            <div><dt>Created</dt><dd>{formatDate(incident.created_at)}</dd></div>
            <div><dt>Updated</dt><dd>{formatDate(incident.updated_at)}</dd></div>
            <div><dt>Incident ID</dt><dd className="mono compact-id" title={incident.id}>{incident.id}</dd></div>
          </dl>
        </aside>
      </div>

      <section className="content-card investigation-history-card">
        <div className="card-heading card-heading-between">
          <div className="heading-cluster">
            <div className="card-icon"><Icon name="activity" size={17} /></div>
            <div><p className="section-kicker">Execution history</p><h3>Investigations</h3></div>
          </div>
          <span className="quiet-count">{investigations.length} total</span>
        </div>
        {investigations.length === 0 ? (
          <div className="inline-empty"><p>No investigation has been run for this incident.</p></div>
        ) : (
          <div className="investigation-history">
            {investigations.map((investigation, index) => (
              <div className="history-row" key={investigation.id}>
                <span className={`history-node history-node-${investigation.status}`} />
                <div>
                  <strong>{index === 0 ? "Latest investigation" : `Investigation ${investigations.length - index}`}</strong>
                  <span>{stageLabel(investigation.stage)} · {formatDate(investigation.created_at)}</span>
                </div>
                <span className={`status-pill status-pill-${investigation.status}`}>{investigation.status.replaceAll("_", " ")}</span>
              </div>
            ))}
          </div>
        )}
      </section>

      {latest?.review && (
        <section className={`review-summary review-summary-${latest.review.decision}`}>
          <Icon name={latest.review.decision === "accepted" ? "check" : "x"} size={18} />
          <div><strong>Human review: {latest.review.decision}</strong><p>{latest.review.note ?? "No review note was provided."}</p></div>
        </section>
      )}
    </div>
  );
}

function EvidencePanel({ evidence, citedIds }: { evidence: Evidence[]; citedIds: Set<string> }) {
  const sourceCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const item of evidence) {
      const origin = evidenceOrigin(item);
      counts.set(origin, (counts.get(origin) ?? 0) + 1);
    }
    return [...counts.entries()];
  }, [evidence]);

  return (
    <div className="tab-panel" id="panel-evidence" role="tabpanel" aria-labelledby="tab-evidence">
      <header className="panel-intro evidence-intro">
        <div><p className="section-kicker">Collected factual material</p><h2>Evidence</h2><p>Read-only GitHub records and knowledge chunks persisted before the model can cite them.</p></div>
        <div className="source-summary">{sourceCounts.map(([source, count]) => <span key={source}>{source}<strong>{count}</strong></span>)}</div>
      </header>

      {evidence.length === 0 ? (
        <div className="panel-empty"><div className="panel-empty-icon"><Icon name="evidence" size={24} /></div><h3>No Evidence collected</h3><p>Run an investigation to collect repository and knowledge Evidence.</p></div>
      ) : (
        <div className="evidence-grid">
          {evidence.map((item) => {
            const cited = citedIds.has(item.id);
            const origin = evidenceOrigin(item);
            return (
              <article className={`evidence-card ${cited ? "is-cited" : ""}`} id={`evidence-${item.id}`} key={item.id}>
                <header>
                  <span className={`source-pill source-${item.source_type === "knowledge_chunk" ? "knowledge" : "github"}`}>
                    {item.source_type === "knowledge_chunk" ? <Icon name="layers" size={13} /> : <Icon name="github" size={13} />}
                    {origin}
                  </span>
                  {cited && <span className="cited-pill"><Icon name="check" size={12} /> Cited</span>}
                </header>
                <h3>{evidenceLabel(item)}</h3>
                <p className="evidence-reference mono">{item.source_reference}</p>
                <footer><time>{formatDate(item.collected_at)}</time><span className="evidence-id mono" title={item.id}>{item.id.slice(0, 8)}…</span></footer>
                <details className="evidence-details">
                  <summary>Inspect provenance</summary>
                  <dl>
                    <div><dt>Evidence ID</dt><dd className="mono">{item.id}</dd></div>
                    <div><dt>Source type</dt><dd>{item.source_type.replaceAll("_", " ")}</dd></div>
                  </dl>
                  {Object.keys(item.metadata).length > 0 && <pre>{JSON.stringify(item.metadata, null, 2)}</pre>}
                </details>
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
}

interface InvestigationPanelProps {
  investigation: Investigation | null;
  publicDemoMode: boolean;
  reviewing: boolean;
  reviewNote: string;
  onEvidenceSelect: (evidenceId: string) => void;
  onReview: (decision: "accepted" | "rejected") => void;
  onReviewNoteChange: (value: string) => void;
}

function InvestigationPanel({
  investigation,
  publicDemoMode,
  reviewing,
  reviewNote,
  onEvidenceSelect,
  onReview,
  onReviewNoteChange,
}: InvestigationPanelProps) {
  return (
    <div className="tab-panel" id="panel-investigation" role="tabpanel" aria-labelledby="tab-investigation">
      <header className="panel-intro hypothesis-intro">
        <div><p className="section-kicker">Model-generated inference</p><h2>Preliminary hypothesis</h2><p>A structured, validated conclusion over stored Evidence—not a confirmed root cause.</p></div>
        <span className="inference-boundary"><Icon name="sparkles" size={15} /> Inference</span>
      </header>

      {!investigation ? (
        <div className="panel-empty"><div className="panel-empty-icon hypothesis-empty-icon"><Icon name="sparkles" size={24} /></div><h3>No investigation yet</h3><p>Run an investigation from the incident header to generate a preliminary hypothesis.</p></div>
      ) : investigation.status === "failed" ? (
        <div className="failure-state"><Icon name="x" size={22} /><div><h3>Investigation failed</h3><p>{investigation.error_message ?? "The investigation could not be completed."}</p></div></div>
      ) : investigation.status !== "completed" ? (
        <div className="active-investigation">
          <div className="active-investigation-visual"><span /><span /><span /></div>
          <p className="section-kicker">Background worker active</p>
          <h3>{stageLabel(investigation.stage)}</h3>
          <p>TracePilot is collecting and validating Evidence. Durable progress will continue if you leave this view.</p>
          <div className="stage-track"><span style={{ width: `${stageProgress(investigation.stage)}%` }} /></div>
        </div>
      ) : (
        <div className="hypothesis-layout">
          <article className="hypothesis-main">
            <div className="hypothesis-confidence">
              <div>
                <span className="confidence-number">{investigation.confidence === null ? "—" : `${Math.round(investigation.confidence * 100)}%`}</span>
                <span>model confidence</span>
              </div>
              <p>Confidence is model-reported and is not a calibrated probability.</p>
            </div>

            <section className="hypothesis-section hypothesis-summary">
              <p className="section-kicker">Summary</p>
              <h3>{investigation.summary ?? "No summary was returned."}</h3>
            </section>
            <section className="hypothesis-section">
              <p className="section-kicker">Suspected change</p>
              <p>{investigation.suspected_change ?? "No specific change was identified."}</p>
              {investigation.suspected_culprit_id && <div className="culprit-reference"><Icon name="repository" size={15} /><span className="mono">{investigation.suspected_culprit_id}</span></div>}
            </section>

            <section className="hypothesis-section">
              <p className="section-kicker">Supporting Evidence</p>
              {investigation.supporting_evidence_ids.length === 0 ? <p>No Evidence was cited.</p> : (
                <div className="citation-list">{investigation.supporting_evidence_ids.map((id, index) => (
                  <button type="button" key={id} onClick={() => onEvidenceSelect(id)}><span>{index + 1}</span><span className="mono">{id}</span><Icon name="chevron-right" size={15} /></button>
                ))}</div>
              )}
            </section>
          </article>

          <aside className="hypothesis-aside">
            <section className="action-list-card missing-card">
              <div className="card-heading"><div className="card-icon"><Icon name="info" size={17} /></div><h3>Missing information</h3></div>
              {investigation.missing_information.length === 0 ? <p>Nothing explicitly identified.</p> : <ul>{investigation.missing_information.map((item) => <li key={item}>{item}</li>)}</ul>}
            </section>
            <section className="action-list-card next-steps-card">
              <div className="card-heading"><div className="card-icon"><Icon name="check" size={17} /></div><h3>Recommended next steps</h3></div>
              {investigation.recommended_next_steps.length === 0 ? <p>No next steps returned.</p> : <ol>{investigation.recommended_next_steps.map((item) => <li key={item}>{item}</li>)}</ol>}
            </section>
          </aside>

          {!publicDemoMode && (
            <section className="human-review-card">
              <div><p className="section-kicker">Human judgment</p><h3>Review this conclusion</h3><p>The review is stored separately and never rewrites the AI result.</p></div>
              {investigation.review ? (
                <div className={`review-result review-result-${investigation.review.decision}`}><Icon name={investigation.review.decision === "accepted" ? "check" : "x"} size={18} /><div><strong>{investigation.review.decision}</strong><p>{investigation.review.note ?? "No review note provided."}</p><small>{formatDate(investigation.review.reviewed_at)}</small></div></div>
              ) : (
                <div className="review-form">
                  <label><span className="sr-only">Review note</span><textarea maxLength={2_000} rows={3} value={reviewNote} onChange={(event) => onReviewNoteChange(event.target.value)} placeholder="Optional review note…" /></label>
                  <div><button className="secondary-button reject-button" disabled={reviewing} type="button" onClick={() => onReview("rejected")}><Icon name="x" size={15} />Reject</button><button className="primary-button" disabled={reviewing} type="button" onClick={() => onReview("accepted")}><Icon name="check" size={15} />Accept conclusion</button></div>
                </div>
              )}
            </section>
          )}

          <footer className="model-provenance"><span>{investigation.prompt_version ?? "prompt unknown"}</span><span>{investigation.model_name ?? "model unknown"}</span>{investigation.duration_ms !== null && <span>{formatDuration(investigation.duration_ms)}</span>}<span>{investigation.tool_call_count} tools</span></footer>
        </div>
      )}
    </div>
  );
}

function stageProgress(stage: Investigation["stage"]): number {
  const values: Record<Investigation["stage"], number> = {
    queued: 10,
    collecting_evidence: 30,
    retrieving_knowledge: 50,
    reasoning: 70,
    finalizing: 90,
    retry_scheduled: 20,
    completed: 100,
    failed: 100,
  };
  return values[stage];
}

function MetricsPanel({ metrics, investigation }: { metrics: InvestigationMetrics | null; investigation: Investigation | null }) {
  const maximumLatency = Math.max(...(metrics?.latency.map((item) => item.total_duration_ms) ?? [1]), 1);
  return (
    <div className="tab-panel" id="panel-metrics" role="tabpanel" aria-labelledby="tab-metrics">
      <header className="panel-intro metrics-intro"><div><p className="section-kicker">Developer view</p><h2>Execution metrics</h2><p>Provider-reported usage and application-owned stage timing. Nested stages are not summed as a second total.</p></div><span className="developer-pill"><Icon name="activity" size={14} /> Telemetry</span></header>
      {!metrics ? (
        <div className="panel-empty"><div className="panel-empty-icon"><Icon name="metrics" size={24} /></div><h3>No metrics available</h3><p>Metrics appear after an investigation records operation spans.</p></div>
      ) : (
        <>
          <div className="metric-summary-grid">
            <article><span>Total duration</span><strong>{investigation?.duration_ms == null ? "—" : formatDuration(investigation.duration_ms)}</strong><small>End-to-end investigation</small></article>
            <article><span>Total tokens</span><strong>{metrics.total_tokens?.toLocaleString() ?? "—"}</strong><small>Provider reported</small></article>
            <article><span>Estimated cost</span><strong>{metrics.estimated_cost_usd === null ? "Unknown" : `$${metrics.estimated_cost_usd.toFixed(6)}`}</strong><small>{metrics.cost_status.replaceAll("_", " ")}</small></article>
            <article><span>Fallback</span><strong>{metrics.fallback_used ? "Used" : "Not used"}</strong><small>Provider resilience</small></article>
          </div>
          <div className="metrics-layout">
            <section className="content-card latency-card">
              <div className="card-heading"><div className="card-icon"><Icon name="clock" size={17} /></div><div><p className="section-kicker">Latency profile</p><h3>Operation stages</h3></div></div>
              <div className="latency-list">{metrics.latency.map((item) => (
                <div className="latency-row" key={item.operation_type}>
                  <div><strong>{item.operation_type.replaceAll("_", " ")}</strong><span>{item.call_count} {item.call_count === 1 ? "call" : "calls"}</span></div>
                  <div className="latency-bar"><span style={{ width: `${Math.max((item.total_duration_ms / maximumLatency) * 100, 2)}%` }} /></div>
                  <strong>{formatDuration(item.total_duration_ms)}</strong>
                </div>
              ))}</div>
            </section>
            <aside className="content-card provider-card">
              <p className="section-kicker">Serving configuration</p>
              <h3>Providers and models</h3>
              <dl className="metadata-list"><div><dt>Providers</dt><dd>{metrics.serving_providers.join(", ") || "Unknown"}</dd></div><div><dt>Models</dt><dd>{metrics.serving_models.join(", ") || "Unknown"}</dd></div><div><dt>Input tokens</dt><dd>{metrics.input_tokens?.toLocaleString() ?? "Not reported"}</dd></div><div><dt>Output tokens</dt><dd>{metrics.output_tokens?.toLocaleString() ?? "Not reported"}</dd></div><div><dt>Trace IDs</dt><dd>{metrics.trace_ids.length}</dd></div></dl>
            </aside>
          </div>
        </>
      )}
    </div>
  );
}

export function IncidentWorkspace({
  incident,
  evidence,
  investigations,
  metrics,
  detailsLoading,
  publicDemoMode,
  running,
  reviewing,
  reviewNote,
  onBack,
  onCreate,
  onRunInvestigation,
  onReview,
  onReviewNoteChange,
}: IncidentWorkspaceProps) {
  const [activeTab, setActiveTab] = useState<WorkspaceTab>("overview");
  const latestInvestigation = investigations[0] ?? null;
  const investigationActive = latestInvestigation?.status === "pending" || latestInvestigation?.status === "in_progress";
  const citedIds = useMemo(() => new Set(latestInvestigation?.supporting_evidence_ids ?? []), [latestInvestigation?.supporting_evidence_ids]);

  if (!incident) return <EmptyWorkspace publicDemoMode={publicDemoMode} onCreate={onCreate} />;

  function handleTabKeyDown(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
    event.preventDefault();
    const direction = event.key === "ArrowRight" ? 1 : -1;
    const nextIndex = (index + direction + tabs.length) % tabs.length;
    setActiveTab(tabs[nextIndex].id);
    const buttons = event.currentTarget.parentElement?.querySelectorAll<HTMLButtonElement>("[role=tab]");
    buttons?.[nextIndex]?.focus();
  }

  function showEvidence(evidenceId: string) {
    setActiveTab("evidence");
    window.setTimeout(() => document.getElementById(`evidence-${evidenceId}`)?.scrollIntoView({ block: "center", behavior: "smooth" }), 0);
  }

  return (
    <section className="detail-pane" aria-label={`Incident details for ${incident.title}`} aria-busy={detailsLoading}>
      <header className="incident-detail-header">
        <button className="mobile-back-button" type="button" onClick={onBack}><Icon name="arrow-left" size={18} />Incidents</button>
        <div className="incident-title-row">
          <div className={`incident-severity-icon severity-icon-${incident.severity}`}><Icon name="activity" size={20} /></div>
          <div className="incident-title-copy">
            <div className="title-badges"><span className={`severity-badge severity-${incident.severity}`}>{incident.severity}</span><span className={`status-badge status-${incident.status}`}><span />{incident.status}</span></div>
            <h2 tabIndex={-1}>{incident.title}</h2>
            <div className="incident-title-meta"><span><Icon name="clock" size={14} />Started {formatDate(incident.started_at)}</span>{incident.repository_full_name && <span><Icon name="github" size={14} />{incident.repository_full_name}</span>}</div>
          </div>
          <div className="incident-header-actions">
            {incident.repository_full_name ? !publicDemoMode && (
              <button className="primary-button run-investigation-button" disabled={running || detailsLoading || investigationActive} type="button" onClick={onRunInvestigation}>
                {running || investigationActive ? <span className="button-spinner" /> : <Icon name="play" size={15} />}
                {running ? "Queuing…" : investigationActive ? "Investigation running" : "Run investigation"}
              </button>
            ) : <span className="repository-required"><Icon name="info" size={14} />Repository required to investigate</span>}
          </div>
        </div>
        {detailsLoading && <div className="detail-loading-track"><span /></div>}
        <nav className="detail-tabs" aria-label="Incident sections" role="tablist">
          {tabs.map((tab, index) => (
            <button aria-controls={`panel-${tab.id}`} aria-selected={activeTab === tab.id} id={`tab-${tab.id}`} key={tab.id} role="tab" tabIndex={activeTab === tab.id ? 0 : -1} type="button" onClick={() => setActiveTab(tab.id)} onKeyDown={(event) => handleTabKeyDown(event, index)}>
              <Icon name={tab.icon} size={16} />{tab.label}{tab.id === "evidence" && <TabCount value={evidence.length} />}{tab.id === "investigation" && <TabCount value={investigations.length} />}
            </button>
          ))}
        </nav>
      </header>

      <div className="detail-content">
        {detailsLoading && investigations.length === 0 && evidence.length === 0 ? <DetailSkeleton /> : (
          <>
            {activeTab === "overview" && <OverviewPanel incident={incident} investigations={investigations} />}
            {activeTab === "evidence" && <EvidencePanel evidence={evidence} citedIds={citedIds} />}
            {activeTab === "investigation" && <InvestigationPanel investigation={latestInvestigation} publicDemoMode={publicDemoMode} reviewing={reviewing} reviewNote={reviewNote} onEvidenceSelect={showEvidence} onReview={onReview} onReviewNoteChange={onReviewNoteChange} />}
            {activeTab === "metrics" && <MetricsPanel metrics={metrics} investigation={latestInvestigation} />}
          </>
        )}
      </div>
    </section>
  );
}
