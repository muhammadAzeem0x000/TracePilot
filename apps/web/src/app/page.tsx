"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { EvaluationDashboardModal } from "@/components/EvaluationDashboardModal";
import { Icon } from "@/components/Icon";
import { IncidentSidebar } from "@/components/IncidentSidebar";
import { IncidentWorkspace } from "@/components/IncidentWorkspace";
import { NewIncidentDialog } from "@/components/NewIncidentDialog";
import { SandboxPlaygroundModal } from "@/components/SandboxPlaygroundModal";
import {
  API_DOCUMENTATION_URL,
  createIncident,
  Evidence,
  getIncident,
  getInvestigation,
  getInvestigationMetrics,
  getPublicConfig,
  Incident,
  IncidentCreate,
  Investigation,
  InvestigationMetrics,
  listEvidence,
  listIncidents,
  listInvestigations,
  reviewInvestigation,
  runInvestigation,
} from "@/lib/api";
import { messageFrom } from "@/lib/presentation";

type ApiState = "connecting" | "online" | "offline";

function incidentFromUrl(): string | null {
  if (typeof window === "undefined") return null;
  return new URL(window.location.href).searchParams.get("incident");
}

function updateIncidentUrl(incidentId: string | null, mode: "push" | "replace" = "push") {
  const url = new URL(window.location.href);
  if (incidentId) url.searchParams.set("incident", incidentId);
  else url.searchParams.delete("incident");
  window.history[mode === "push" ? "pushState" : "replaceState"]({}, "", url);
}

export default function Home() {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [selected, setSelected] = useState<Incident | null>(null);
  const [evidence, setEvidence] = useState<Evidence[]>([]);
  const [investigations, setInvestigations] = useState<Investigation[]>([]);
  const [metrics, setMetrics] = useState<InvestigationMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailsLoading, setDetailsLoading] = useState(false);
  const [running, setRunning] = useState(false);
  const [reviewing, setReviewing] = useState(false);
  const [reviewNote, setReviewNote] = useState("");
  const [publicDemoMode, setPublicDemoMode] = useState(false);
  const [apiState, setApiState] = useState<ApiState>("connecting");
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [evalModalOpen, setEvalModalOpen] = useState(false);
  const [sandboxModalOpen, setSandboxModalOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const selectionVersion = useRef(0);
  const initialSelectionHandled = useRef(false);

  const latestInvestigation = investigations[0] ?? null;
  const investigationActive =
    latestInvestigation?.status === "pending" || latestInvestigation?.status === "in_progress";
  const activeInvestigationId = investigationActive ? latestInvestigation.id : null;

  const hydrateIncident = useCallback(async (incidentId: string, immediate?: Incident) => {
    const requestVersion = ++selectionVersion.current;
    const knownIncident = immediate ?? incidents.find((item) => item.id === incidentId);
    if (knownIncident) setSelected(knownIncident);
    setEvidence([]);
    setInvestigations([]);
    setMetrics(null);
    setReviewNote("");
    setDetailsLoading(true);
    setError(null);

    try {
      const [incident, collectedEvidence, existingInvestigations] = await Promise.all([
        getIncident(incidentId),
        listEvidence(incidentId),
        listInvestigations(incidentId),
      ]);
      const operationMetrics = existingInvestigations[0]
        ? await getInvestigationMetrics(existingInvestigations[0].id)
        : null;
      if (selectionVersion.current !== requestVersion) return;
      setSelected(incident);
      setEvidence(collectedEvidence);
      setInvestigations(existingInvestigations);
      setMetrics(operationMetrics);
      setApiState("online");
    } catch (reason: unknown) {
      if (selectionVersion.current === requestVersion) {
        setError(messageFrom(reason, "Unable to load incident details"));
      }
    } finally {
      if (selectionVersion.current === requestVersion) setDetailsLoading(false);
    }
  }, [incidents]);

  useEffect(() => {
    let active = true;
    Promise.all([listIncidents(), getPublicConfig()])
      .then(([items, config]) => {
        if (!active) return;
        setIncidents(items);
        setPublicDemoMode(config.public_demo_mode);
        setApiState("online");
      })
      .catch((reason: unknown) => {
        if (!active) return;
        setApiState("offline");
        setError(messageFrom(reason, "Unable to connect to TracePilot API"));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (loading || initialSelectionHandled.current) return;
    initialSelectionHandled.current = true;
    const requestedId = incidentFromUrl();
    const requestedIncident = incidents.find((item) => item.id === requestedId);
    if (requestedId && requestedIncident) {
      const timer = window.setTimeout(
        () => void hydrateIncident(requestedId, requestedIncident),
        0,
      );
      return () => window.clearTimeout(timer);
    }
    if (requestedId && !requestedIncident) updateIncidentUrl(null, "replace");
  }, [hydrateIncident, incidents, loading]);

  useEffect(() => {
    function handleHistoryChange() {
      const incidentId = incidentFromUrl();
      if (!incidentId) {
        selectionVersion.current += 1;
        setSelected(null);
        setEvidence([]);
        setInvestigations([]);
        setMetrics(null);
        setDetailsLoading(false);
        return;
      }
      const known = incidents.find((item) => item.id === incidentId);
      if (known) void hydrateIncident(incidentId, known);
    }
    window.addEventListener("popstate", handleHistoryChange);
    return () => window.removeEventListener("popstate", handleHistoryChange);
  }, [hydrateIncident, incidents]);

  useEffect(() => {
    const incidentId = selected?.id;
    if (!incidentId || !activeInvestigationId) return;
    const selectedIncidentId = incidentId;
    const investigationId = activeInvestigationId;
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
          const [collectedEvidence, operationMetrics] = await Promise.all([
            listEvidence(selectedIncidentId),
            getInvestigationMetrics(investigationId),
          ]);
          if (active) {
            setEvidence(collectedEvidence);
            setMetrics(operationMetrics);
          }
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

  function handleSelect(incidentId: string) {
    const known = incidents.find((incident) => incident.id === incidentId);
    if (!known) return;
    updateIncidentUrl(incidentId);
    void hydrateIncident(incidentId, known);
  }

  function handleBackToIncidents() {
    selectionVersion.current += 1;
    updateIncidentUrl(null);
    setSelected(null);
    setEvidence([]);
    setInvestigations([]);
    setMetrics(null);
    setDetailsLoading(false);
  }

  async function handleCreate(input: IncidentCreate) {
    const created = await createIncident(input);
    selectionVersion.current += 1;
    setIncidents((current) => [created, ...current]);
    setSelected(created);
    setEvidence([]);
    setInvestigations([]);
    setMetrics(null);
    setReviewNote("");
    setDetailsLoading(false);
    updateIncidentUrl(created.id);
    setApiState("online");
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
      setError(messageFrom(reason, "Unable to run investigation"));
      await hydrateIncident(selected.id, selected);
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
    <main className="app-shell">
      <header className="app-header">
        <div className="brand-lockup">
          <div className="brand-mark"><Icon name="activity" size={19} /></div>
          <div><strong>TracePilot</strong><span>Evidence-grounded incident investigation</span></div>
        </div>
        <div className="header-status">
          <button
            type="button"
            className="sandbox-modal-trigger-btn"
            onClick={() => setSandboxModalOpen(true)}
            title="Launch interactive zero-cost leased worker investigation sandbox"
          >
            <Icon name="play" size={13} />
            <span>Interactive Sandbox</span>
          </button>
          <button
            type="button"
            className="eval-modal-trigger-btn"
            onClick={() => setEvalModalOpen(true)}
            title="Inspect 13/13 Adversarial Tests, Hybrid Retrieval Matrix, and Holdout Benchmarks"
          >
            <Icon name="check" size={14} />
            <span>Security & Benchmarks</span>
          </button>
          {publicDemoMode && <span className="demo-chip"><Icon name="info" size={13} />Read-only demo</span>}
          {apiState === "online" ? (
            <a
              aria-label="Open API documentation in a new tab"
              className="api-status api-status-online api-status-link"
              href={API_DOCUMENTATION_URL}
              rel="noreferrer"
              target="_blank"
              title="Open API documentation"
            >
              <span />API online
            </a>
          ) : (
            <span className={`api-status api-status-${apiState}`}><span />API {apiState}</span>
          )}
        </div>
      </header>

      {publicDemoMode && (
        <div className="demo-banner" role="status">
          <Icon name="info" size={15} />
          <span><strong>Portfolio demo:</strong> explore persisted incidents, Evidence, hypotheses, and metrics. Cost-bearing actions are disabled.</span>
        </div>
      )}

      {error && (
        <div className="app-error" role="alert">
          <Icon name="info" size={17} />
          <span>{error}</span>
          {selected && <button type="button" onClick={() => void hydrateIncident(selected.id, selected)}>Retry</button>}
          <button aria-label="Dismiss error" className="error-dismiss" type="button" onClick={() => setError(null)}><Icon name="x" size={16} /></button>
        </div>
      )}

      <div className={`app-frame ${selected ? "has-selection" : ""}`}>
        <IncidentSidebar
          incidents={incidents}
          loading={loading}
          publicDemoMode={publicDemoMode}
          selectedId={selected?.id ?? null}
          onCreate={() => setCreateDialogOpen(true)}
          onSelect={handleSelect}
        />
        <IncidentWorkspace
          key={selected?.id ?? "empty"}
          incident={selected}
          evidence={evidence}
          investigations={investigations}
          metrics={metrics}
          detailsLoading={detailsLoading}
          publicDemoMode={publicDemoMode}
          running={running}
          reviewing={reviewing}
          reviewNote={reviewNote}
          onBack={handleBackToIncidents}
          onCreate={() => setCreateDialogOpen(true)}
          onRunInvestigation={() => void handleRunInvestigation()}
          onReview={(decision) => void handleReview(decision)}
          onReviewNoteChange={setReviewNote}
        />
      </div>

      <NewIncidentDialog
        open={createDialogOpen}
        onClose={() => setCreateDialogOpen(false)}
        onCreate={handleCreate}
      />

      <EvaluationDashboardModal
        open={evalModalOpen}
        onClose={() => setEvalModalOpen(false)}
      />

      <SandboxPlaygroundModal
        open={sandboxModalOpen}
        onClose={() => setSandboxModalOpen(false)}
      />
    </main>
  );
}
