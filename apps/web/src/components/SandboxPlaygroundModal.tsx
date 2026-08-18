"use client";

import { useEffect, useRef, useState } from "react";

import { Icon } from "@/components/Icon";

interface SandboxPlaygroundModalProps {
  open: boolean;
  onClose: () => void;
}

interface SandboxStep {
  stepNumber: number;
  stage: string;
  badge: "queue" | "tool" | "retrieval" | "db" | "llm" | "verified";
  title: string;
  description: string;
  logs: string[];
  tokensAdded: number;
  evidenceItems?: { title: string; ref: string; type: string; id: string }[];
}

interface SandboxScenario {
  id: string;
  title: string;
  repository: string;
  description: string;
  steps: SandboxStep[];
  conclusion: {
    summary: string;
    suspectedCulprit: string;
    confidence: number;
    supportingEvidenceIds: string[];
    missingInfo: string[];
    nextSteps: string[];
  };
}

const SANDBOX_SCENARIOS: SandboxScenario[] = [
  {
    id: "sandbox_schema_drift",
    title: "Database Schema Drift (Missing Column)",
    repository: "retail-corp/checkout-api",
    description: "Production checkout API returning UndefinedColumn: column 'payment_status' does not exist.",
    steps: [
      {
        stepNumber: 1,
        stage: "Queued & Claimed",
        badge: "queue",
        title: "PostgreSQL Leased Worker Claim",
        description: "Atomic enqueue RPC acquired row lock (FOR UPDATE SKIP LOCKED) and set lease_expires_at = now() + 240s.",
        logs: [
          "[00:00.012] POST /api/v1/incidents/26aeff02/investigations -> 202 Accepted",
          "[00:00.045] Worker polling: executed claim_investigation_job(240)",
          "[00:00.089] Claimed Job #7f8a12b; lease set to 240s; stage -> collecting_evidence",
        ],
        tokensAdded: 0,
      },
      {
        stepNumber: 2,
        stage: "Tool Calling",
        badge: "tool",
        title: "Allowlisted GitHub Inspection",
        description: "Model requested 'list_recent_commits' and 'get_commit'. Server injected repository context from Incident.",
        logs: [
          "[00:01.210] LLM turn 1: requested tool list_recent_commits(limit=5)",
          "[00:02.140] GitHub REST GET /repos/retail-corp/checkout-api/commits -> 5 commits",
          "[00:03.450] LLM turn 2: requested tool get_commit(sha='1111111111111111111111111111111111111111')",
          "[00:04.820] Commit diff inspected: found references to 'orders.payment_status'",
        ],
        tokensAdded: 2450,
        evidenceItems: [
          {
            title: "Commit: Add payment status tracking",
            ref: "retail-corp/checkout-api@11111111",
            type: "github_commit",
            id: "2ae7fc65-e334-42e7-9e57-04c8d627a7ef",
          },
        ],
      },
      {
        stepNumber: 3,
        stage: "Knowledge Retrieval",
        badge: "retrieval",
        title: "Hybrid pgvector Cosine + Lexical FTS (RRF k=60)",
        description: "Concurrently executed dense vector similarity and full-text tsquery search over runbooks.",
        logs: [
          "[00:05.100] Query embedding: gemini-embedding-001 (768-dim normalized)",
          "[00:05.811] Executed search_knowledge_semantic & search_knowledge_lexical",
          "[00:06.120] Reciprocal Rank Fusion: merged 8 candidates using 1/(60+rank)",
          "[00:07.450] Structured LLM Reranker: ordered candidate set by relevance",
        ],
        tokensAdded: 1820,
        evidenceItems: [
          {
            title: "Runbook: Database Migrations",
            ref: "runbooks/database-migrations.md#chunk-1",
            type: "knowledge_chunk",
            id: "34e9498d-6139-4b7c-a976-9ce74137af61",
          },
          {
            title: "Past Incident: Missing Checkout Column",
            ref: "past_incidents/missing-checkout-column.md#chunk-2",
            type: "knowledge_chunk",
            id: "42931db0-2f11-4fb5-99fc-12b3e4a74151",
          },
        ],
      },
      {
        stepNumber: 4,
        stage: "Evidence Grounding",
        badge: "db",
        title: "Persist Evidence to PostgreSQL",
        description: "Committed all 3 tool results as immutable Evidence rows in PostgreSQL before returning UUIDs to model.",
        logs: [
          "[00:07.890] SQL: INSERT INTO public.evidence (id, incident_id, source_type, ...) VALUES (...)",
          "[00:07.940] Persisted 3 Evidence rows; assigned verified server UUIDs",
          "[00:08.010] Formatted untrusted evidence payload with UUIDs for final model turn",
        ],
        tokensAdded: 0,
      },
      {
        stepNumber: 5,
        stage: "Synthesis & Validation",
        badge: "llm",
        title: "Pydantic Structured Output Validation",
        description: "Model returned preliminary hypothesis JSON. Pydantic validated schema, culprit, and confidence bounds.",
        logs: [
          "[00:09.650] Model turn 3: returned JSON hypothesis conclusion",
          "[00:09.710] PreliminaryInvestigationResult.model_validate_json() -> SUCCESS",
          "[00:09.730] Confidence: 0.60 (Calibrated with missing info declared)",
        ],
        tokensAdded: 840,
      },
      {
        stepNumber: 6,
        stage: "Citation Verification",
        badge: "verified",
        title: "Relational Citation Ownership Verification",
        description: "PostgreSQL verified all cited UUIDs exist in database for this exact investigation (0 hallucinations).",
        logs: [
          "[00:09.800] SQL: SELECT id FROM public.evidence WHERE incident_id = :id AND investigation_id = :inv_id",
          "[00:09.845] Verified: set(supporting_evidence_ids) == actual_persisted_ids (3/3 valid)",
          "[00:09.890] Suspected culprit matched verified source_reference: retail-corp/checkout-api@11111111",
          "[00:09.950] Investigation completed successfully with zero ungrounded citations!",
        ],
        tokensAdded: 0,
      },
    ],
    conclusion: {
      summary:
        "Commit 11111111 introduced application queries referencing 'payment_status' before migration 20260804_002 was executed in production. Runbook database-migrations.md outlines the required forward schema deployment gate.",
      suspectedCulprit: "retail-corp/checkout-api@1111111111111111111111111111111111111111",
      confidence: 0.60,
      supportingEvidenceIds: [
        "2ae7fc65-e334-42e7-9e57-04c8d627a7ef",
        "34e9498d-6139-4b7c-a976-9ce74137af61",
        "42931db0-2f11-4fb5-99fc-12b3e4a74151",
      ],
      missingInfo: [
        "Production database migration run history logs",
        "Deployment pipeline gate execution timestamps",
      ],
      nextSteps: [
        "Execute database migration 20260804_002 to add missing column",
        "Add pre-deployment migration verification gate to GitHub Actions workflow",
      ],
    },
  },
  {
    id: "sandbox_timeout_storm",
    title: "Payment Gateway Timeout Retry Storm",
    repository: "retail-corp/billing-service",
    description: "Payment provider read timeout retries causing duplicate debit requests.",
    steps: [
      {
        stepNumber: 1,
        stage: "Queued & Claimed",
        badge: "queue",
        title: "PostgreSQL Leased Worker Claim",
        description: "Claimed investigation job with 240s lease and started distributed telemetry span.",
        logs: [
          "[00:00.020] Job claimed via FOR UPDATE SKIP LOCKED",
          "[00:00.050] TraceContext initialized; stage -> collecting_evidence",
        ],
        tokensAdded: 0,
      },
      {
        stepNumber: 2,
        stage: "Tool Calling",
        badge: "tool",
        title: "GitHub Commit & PR Inspection",
        description: "Fetched recent PR #402 containing payment gateway client retry adjustments.",
        logs: [
          "[00:01.400] LLM requested list_recent_pull_requests(limit=5)",
          "[00:02.300] Fetched PR #402: 'Adjust payment gateway timeout'",
          "[00:03.500] Inspecting diff: timeout decreased from 10s to 2s with aggressive retries",
        ],
        tokensAdded: 2100,
        evidenceItems: [
          {
            title: "PR #402: Adjust payment gateway timeout",
            ref: "retail-corp/billing-service#402",
            type: "github_pull_request",
            id: "55f81a10-4411-4b1a-88f1-9c8e11a241b1",
          },
        ],
      },
      {
        stepNumber: 3,
        stage: "Knowledge Retrieval",
        badge: "retrieval",
        title: "Hybrid Search on Timeout Runbooks",
        description: "Retrieved external API timeout handling runbook and idempotency architecture doc.",
        logs: [
          "[00:04.900] Query: 'payment provider read timeout retries duplicate charges'",
          "[00:05.400] Retrieved runbooks/external-api-timeouts.md and architecture/checkout-service.md",
        ],
        tokensAdded: 1650,
        evidenceItems: [
          {
            title: "Runbook: External API Timeouts",
            ref: "runbooks/external-api-timeouts.md#chunk-1",
            type: "knowledge_chunk",
            id: "66e92b20-5522-4c2b-99a2-0d9f22b352c2",
          },
        ],
      },
      {
        stepNumber: 4,
        stage: "Evidence Grounding",
        badge: "db",
        title: "Persist Evidence to PostgreSQL",
        description: "Committed 2 Evidence rows with verified database UUIDs.",
        logs: [
          "[00:06.100] Persisted PR #402 and Runbook chunk to PostgreSQL evidence table",
        ],
        tokensAdded: 0,
      },
      {
        stepNumber: 5,
        stage: "Synthesis & Validation",
        badge: "llm",
        title: "Pydantic Structured Synthesis",
        description: "Generated structured preliminary conclusion citing valid persisted evidence.",
        logs: [
          "[00:07.800] Structured hypothesis parsed with 0.65 model confidence",
        ],
        tokensAdded: 790,
      },
      {
        stepNumber: 6,
        stage: "Citation Verification",
        badge: "verified",
        title: "Relational Citation Ownership Verification",
        description: "2/2 cited UUIDs verified in PostgreSQL evidence table.",
        logs: [
          "[00:08.100] Citation ownership query PASSED (2/2 UUIDs verified)",
          "[00:08.150] Investigation completed successfully!",
        ],
        tokensAdded: 0,
      },
    ],
    conclusion: {
      summary:
        "PR #402 decreased gateway HTTP timeout to 2s without passing idempotency keys on retries, causing transient upstream timeouts to spawn duplicate payment charges.",
      suspectedCulprit: "retail-corp/billing-service#402",
      confidence: 0.65,
      supportingEvidenceIds: [
        "55f81a10-4411-4b1a-88f1-9c8e11a241b1",
        "66e92b20-5522-4c2b-99a2-0d9f22b352c2",
      ],
      missingInfo: ["Payment gateway upstream transaction logs with response headers"],
      nextSteps: [
        "Revert PR #402 or restore 10s gateway timeout",
        "Enforce unique Idempotency-Key headers on all payment charge retries",
      ],
    },
  },
];

export function SandboxPlaygroundModal({ open, onClose }: SandboxPlaygroundModalProps) {
  const [selectedScenarioId, setSelectedScenarioId] = useState("sandbox_schema_drift");
  const [currentStepIndex, setCurrentStepIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const playTimerRef = useRef<number | null>(null);

  const activeScenario =
    SANDBOX_SCENARIOS.find((s) => s.id === selectedScenarioId) ?? SANDBOX_SCENARIOS[0];
  const maxSteps = activeScenario.steps.length;
  const currentStep = activeScenario.steps[currentStepIndex];

  // Calculate cumulative stats
  const cumulativeTokens = activeScenario.steps
    .slice(0, currentStepIndex + 1)
    .reduce((sum, s) => sum + s.tokensAdded, 0);
  const accumulatedEvidence = activeScenario.steps
    .slice(0, currentStepIndex + 1)
    .flatMap((s) => s.evidenceItems ?? []);

  useEffect(() => {
    if (isPlaying) {
      playTimerRef.current = window.setTimeout(() => {
        if (currentStepIndex < maxSteps - 1) {
          setCurrentStepIndex((prev) => prev + 1);
        } else {
          setIsPlaying(false);
        }
      }, 2000);
    }
    return () => {
      if (playTimerRef.current) window.clearTimeout(playTimerRef.current);
    };
  }, [isPlaying, currentStepIndex, maxSteps]);

  function handleReset() {
    setIsPlaying(false);
    setCurrentStepIndex(0);
  }

  function handleStepForward() {
    setIsPlaying(false);
    if (currentStepIndex < maxSteps - 1) {
      setCurrentStepIndex((prev) => prev + 1);
    }
  }

  function handleStepBack() {
    setIsPlaying(false);
    if (currentStepIndex > 0) {
      setCurrentStepIndex((prev) => prev - 1);
    }
  }

  if (!open) return null;

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="sandbox-title">
      <div className="modal-container sandbox-modal-container">
        <header className="modal-header">
          <div className="modal-header-copy">
            <div className="badge-row">
              <span className="source-pill source-github">
                <Icon name="play" size={13} /> Interactive Simulation
              </span>
              <span className="demo-chip">Zero-Cost Public Demo Sandbox</span>
            </div>
            <h2 id="sandbox-title">Investigation Sandbox</h2>
          </div>
          <button
            aria-label="Close modal"
            className="modal-close-button"
            type="button"
            onClick={onClose}
          >
            <Icon name="x" size={18} />
          </button>
        </header>

        {/* Sticky slim control strip */}
        <div className="sandbox-sticky-ctrl-bar">
          <div className="sticky-step-indicator">
            <span className="stat-label">Step</span>
            <strong>{currentStepIndex + 1}/{maxSteps}</strong>
            <span className="bullet-sep">•</span>
            <span className="stage-pill">{currentStep.stage}</span>
          </div>
          <div className="sandbox-controls-cluster">
            <button
              type="button"
              className="ctrl-btn"
              disabled={currentStepIndex === 0}
              onClick={handleStepBack}
              title="Previous step"
            >
              <Icon name="arrow-left" size={13} /> Prev
            </button>
            <button
              type="button"
              className={`ctrl-btn play-btn ${isPlaying ? "is-playing" : ""}`}
              onClick={() => setIsPlaying(!isPlaying)}
            >
              <Icon name={isPlaying ? "activity" : "play"} size={13} />
              {isPlaying ? "Pause" : "Auto Play"}
            </button>
            <button
              type="button"
              className="ctrl-btn"
              disabled={currentStepIndex === maxSteps - 1}
              onClick={handleStepForward}
              title="Next step"
            >
              Next <Icon name="chevron-right" size={13} />
            </button>
            <button type="button" className="ctrl-btn" onClick={handleReset} title="Reset simulation">
              Reset
            </button>
          </div>
        </div>

        <div className="sandbox-progress-track">
          <div
            className="sandbox-progress-bar"
            style={{ width: `${((currentStepIndex + 1) / maxSteps) * 100}%` }}
          />
        </div>

        <div className="modal-scrollable-body">
          {/* Scenario Archetype selector */}
          <div className="archetype-selector-bar">
            <span className="selector-label">Scenario Archetype:</span>
            <div className="archetype-pills">
              {SANDBOX_SCENARIOS.map((s) => (
                <button
                  key={s.id}
                  type="button"
                  className={`archetype-pill ${s.id === selectedScenarioId ? "is-active" : ""}`}
                  onClick={() => {
                    setSelectedScenarioId(s.id);
                    handleReset();
                  }}
                >
                  {s.title}
                </button>
              ))}
            </div>
          </div>

          {/* Stats Bar */}
          <div className="sandbox-live-stats-bar">
            <div className="stat-node">
              <span>Stage</span>
              <strong>{currentStep.stage}</strong>
            </div>
            <div className="stat-node">
              <span>Step</span>
              <strong>
                {currentStepIndex + 1} of {maxSteps}
              </strong>
            </div>
            <div className="stat-node">
              <span>Reported Tokens</span>
              <strong className="mono">{cumulativeTokens.toLocaleString()}</strong>
            </div>
            <div className="stat-node">
              <span>Persisted Evidence</span>
              <strong>{accumulatedEvidence.length} rows</strong>
            </div>
          </div>

          <div className="sandbox-workspace-grid">
            {/* LEFT: STEP RUNNER */}
            <div className="sandbox-step-pane">
              <div className="current-step-card">
                <div className="step-card-header">
                  <span className={`dag-badge ${currentStep.badge}`}>{currentStep.stage}</span>
                  <h3>{currentStep.title}</h3>
                </div>
                <p className="step-card-desc">{currentStep.description}</p>

                <div className="step-logs-box">
                  <span>Execution Logs & SQL Traces</span>
                  <div className="logs-scroller">
                    {currentStep.logs.map((log, idx) => (
                      <div key={idx} className="log-line mono">
                        {log}
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* PERSISTED EVIDENCE DRAWER */}
              {accumulatedEvidence.length > 0 && (
                <div className="sandbox-evidence-drawer">
                  <h4>
                    <Icon name="evidence" size={14} /> Persisted PostgreSQL Evidence (
                    {accumulatedEvidence.length})
                  </h4>
                  <div className="sandbox-evidence-list">
                    {accumulatedEvidence.map((ev) => (
                      <div key={ev.id} className="sandbox-evidence-item">
                        <span className="ev-pill mono">{ev.type}</span>
                        <strong>{ev.title}</strong>
                        <span className="mono ev-id">{ev.id.slice(0, 8)}…</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* RIGHT: CONCLUSION STATE */}
            <div className="sandbox-conclusion-pane">
              {currentStepIndex === maxSteps - 1 ? (
                <div className="sandbox-final-hypothesis">
                  <div className="final-badge-row">
                    <span className="grounded-badge">
                      <Icon name="check" size={13} /> Investigation Completed & Verified
                    </span>
                    <span className="confidence-pill">
                      {Math.round(activeScenario.conclusion.confidence * 100)}% Confidence
                    </span>
                  </div>
                  <h3>Preliminary Hypothesis</h3>
                  <p className="final-summary">{activeScenario.conclusion.summary}</p>

                  <div className="final-culprit-box">
                    <span>Verified Suspected Culprit</span>
                    <code className="mono">{activeScenario.conclusion.suspectedCulprit}</code>
                  </div>

                  <div className="final-citations-box">
                    <span>Database-Verified Citations</span>
                    <div className="citations-pills-row">
                      {activeScenario.conclusion.supportingEvidenceIds.map((id, idx) => (
                        <span key={id} className="verified-citation-pill mono">
                          ✓ [{idx + 1}] {id.slice(0, 8)}…
                        </span>
                      ))}
                    </div>
                  </div>

                  <div className="final-next-steps">
                    <span>Recommended Next Steps</span>
                    <ol>
                      {activeScenario.conclusion.nextSteps.map((step) => (
                        <li key={step}>{step}</li>
                      ))}
                    </ol>
                  </div>
                </div>
              ) : (
                <div className="sandbox-pending-pane">
                  <div className="pending-visual">
                    <Icon name="activity" size={32} />
                  </div>
                  <h3>Investigation in Progress…</h3>
                  <p>
                    TracePilot is currently executing Step {currentStepIndex + 1} of {maxSteps}.
                    Advance or click &quot;Auto Play&quot; to reach final synthesis and citation verification.
                  </p>
                  <div className="pending-step-list">
                    {activeScenario.steps.map((s, idx) => (
                      <div
                        key={s.stepNumber}
                        className={`pending-step-node ${
                          idx === currentStepIndex
                            ? "is-current"
                            : idx < currentStepIndex
                            ? "is-done"
                            : ""
                        }`}
                      >
                        <span className="step-num">{s.stepNumber}</span>
                        <span>{s.title}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>

          <div className="modal-body-note-card">
            <Icon name="activity" size={16} />
            <span>
              <strong>Sandbox Guarantee:</strong> Runs deterministic lifecycle simulations on real
              benchmark data with zero external API key costs or database mutation risks.
            </span>
          </div>
        </div>

        <footer className="modal-footer">
          <button className="primary-button" type="button" onClick={onClose}>
            Close Sandbox
          </button>
        </footer>
      </div>
    </div>
  );
}
