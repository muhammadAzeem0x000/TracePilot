"use client";

import { useState } from "react";

import { Icon } from "@/components/Icon";

interface GroundingComparisonModalProps {
  open: boolean;
  onClose: () => void;
  initialArchetype?: string;
}

interface ArchetypeComparison {
  id: string;
  title: string;
  incidentTitle: string;
  repository: string;
  naive: {
    model: string;
    confidence: number;
    summary: string;
    suspectedCulprit: string;
    failureReasons: string[];
    evidenceInspected: string;
    citationsCount: number;
    explanation: string;
  };
  grounded: {
    model: string;
    confidence: number;
    summary: string;
    suspectedCulprit: string;
    evidenceInspected: string;
    citationsCount: number;
    verifiedProof: string[];
    explanation: string;
  };
}

const COMPARISON_ARCHETYPES: ArchetypeComparison[] = [
  {
    id: "checkout_schema_gap",
    title: "Database Schema Gap (Missing Column)",
    incidentTitle: "Checkout service throwing UndefinedColumn on payment_status",
    repository: "retail-corp/checkout-api",
    naive: {
      model: "Standard Prompt (GPT-4 / DeepSeek Chat)",
      confidence: 0.98,
      summary:
        "The checkout failure is caused by an outdated database migration in commit 7a8f9c2d. The database is missing the payment_status enum and needs an immediate ALTER TABLE checkout_orders ADD COLUMN payment_status VARCHAR(50) DEFAULT 'pending'.",
      suspectedCulprit: "commit 7a8f9c2d (Hallucinated SHA)",
      failureReasons: [
        "Hallucinated non-existent commit SHA 7a8f9c2d",
        "Invented incorrect table name 'checkout_orders'",
        "Claimed 98% certainty without inspecting repository or migration logs",
        "Zero verifiable database citations",
      ],
      evidenceInspected: "None (Zero tool calls executed)",
      citationsCount: 0,
      explanation:
        "Standard LLMs generate fluent, plausible root causes using purely statistical word associations, inventing fake commit SHAs and tables.",
    },
    grounded: {
      model: "TracePilot Grounded Investigation Loop",
      confidence: 0.60,
      summary:
        "Commit 1111111111111111111111111111111111111111 merged application code referencing 'payment_status' before migration 20260804_002 was executed in production. Runbook database-migrations.md defines the required forward-migration gate.",
      suspectedCulprit: "retail-corp/checkout-api@1111111111111111111111111111111111111111",
      evidenceInspected: "4 server-executed tools (2 GitHub reads, 1 Hybrid RRF search, 1 commit diff)",
      citationsCount: 2,
      verifiedProof: [
        "Persisted Evidence: retail-corp/checkout-api@11111111 (commit patch inspected)",
        "Persisted Knowledge: runbooks/database-migrations.md#chunk-eval-1",
        "PostgreSQL Relational Citation Check: 2/2 UUIDs Verified in DB",
        "Honest 60% confidence with missing deployment logs declared",
      ],
      explanation:
        "TracePilot executed read-only GitHub and Hybrid Knowledge tools, persisted evidence before citation, and relationally proved all cited UUIDs exist.",
    },
  },
  {
    id: "refund_duplicate_execution",
    title: "Duplicate Job Execution (Lease Expiry)",
    incidentTitle: "Customers charged twice during high-concurrency refund spikes",
    repository: "retail-corp/billing-worker",
    naive: {
      model: "Standard Prompt (GPT-4 / DeepSeek Chat)",
      confidence: 0.95,
      summary:
        "The issue is caused by a race condition in Redis distributed locking inside refund_processor.py. Recommend increasing REDIS_LOCK_TIMEOUT to 60s and setting retry count to 0 in Celery.",
      suspectedCulprit: "config/celery.py:REDIS_LOCK_TIMEOUT (Invented Config)",
      failureReasons: [
        "Assumed Celery/Redis architecture when the system uses PostgreSQL leased jobs",
        "Invented non-existent configuration variable REDIS_LOCK_TIMEOUT",
        "Asserted 95% certainty based on generic internet training patterns",
        "Zero grounding in actual repository architecture",
      ],
      evidenceInspected: "None (Zero tool calls executed)",
      citationsCount: 0,
      explanation:
        "The naive model guessed an arbitrary technology stack (Redis/Celery) instead of discovering the actual PostgreSQL leased queue architecture.",
    },
    grounded: {
      model: "TracePilot Grounded Investigation Loop",
      confidence: 0.60,
      summary:
        "Commit 2222222222222222222222222222222222222222 reduced investigation_job_lease_seconds from 240s to 30s. Long-running Stripe refund calls exceeded 30s, causing stale worker leases to be reclaimed by concurrent workers.",
      suspectedCulprit: "retail-corp/billing-worker@2222222222222222222222222222222222222222",
      evidenceInspected: "4 server-executed tools (list_recent_commits, get_commit, search_knowledge)",
      citationsCount: 2,
      verifiedProof: [
        "Persisted Evidence: retail-corp/billing-worker@22222222",
        "Persisted Knowledge: past_incidents/duplicate-refund-jobs.md#chunk-eval-2",
        "PostgreSQL Relational Citation Check: 2/2 UUIDs Verified in DB",
        "Identified lease expiry interval mismatch accurately from git patch",
      ],
      explanation:
        "TracePilot retrieved the past incident and inspected the exact commit diff where lease duration was modified, accurately diagnosing lease reclamation.",
    },
  },
  {
    id: "tenant_scope_regression",
    title: "Multi-Tenant Authorization Leak",
    incidentTitle: "Organization A reports viewing order records belonging to Organization B",
    repository: "retail-corp/order-service",
    naive: {
      model: "Standard Prompt (GPT-4 / DeepSeek Chat)",
      confidence: 0.99,
      summary:
        "JWT token validation is compromised. The RS256 public key rotated without flushing the cache in auth_middleware.go. Upgrade auth0-jwt library to v4.2 immediately.",
      suspectedCulprit: "middleware/auth.go (Hallucinated File)",
      failureReasons: [
        "Invented non-existent Go file 'middleware/auth.go' in a Python service",
        "Guessed Auth0 key rotation without any evidence",
        "99% confidence despite complete lack of factual inspection",
        "Zero inspectable proof",
      ],
      evidenceInspected: "None (Zero tool calls executed)",
      citationsCount: 0,
      explanation:
        "Naive LLMs hallucinate whole programming languages and libraries to sound authoritative.",
    },
    grounded: {
      model: "TracePilot Grounded Investigation Loop",
      confidence: 0.70,
      summary:
        "Commit 6666666666666666666666666666666666666666 removed the 'organization_id' WHERE filter in the bulk orders query to optimize index usage, introducing a multi-tenant cross-organization leak.",
      suspectedCulprit: "retail-corp/order-service@6666666666666666666666666666666666666666",
      evidenceInspected: "4 server-executed tools (list_recent_commits, get_commit, search_knowledge)",
      citationsCount: 2,
      verifiedProof: [
        "Persisted Evidence: retail-corp/order-service@66666666",
        "Persisted Knowledge: architecture/tenant-authorization.md#chunk-eval-6",
        "PostgreSQL Relational Citation Check: 2/2 UUIDs Verified in DB",
        "Directly identified omitted tenant SQL predicate from commit patch",
      ],
      explanation:
        "TracePilot inspected the actual SQL query modifications in git commit diffs and compared against tenant authorization architecture docs.",
    },
  },
];

export function GroundingComparisonModal({
  open,
  onClose,
  initialArchetype = "checkout_schema_gap",
}: GroundingComparisonModalProps) {
  const [selectedId, setSelectedId] = useState(initialArchetype);
  const activeArchetype =
    COMPARISON_ARCHETYPES.find((item) => item.id === selectedId) ?? COMPARISON_ARCHETYPES[0];

  if (!open) return null;

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="comparison-title">
      <div className="modal-container comparison-modal-container">
        <header className="modal-header">
          <div className="modal-header-copy">
            <div className="badge-row">
              <span className="source-pill source-github">
                <Icon name="sparkles" size={13} /> Empirical Comparison
              </span>
              <span className="demo-chip">Why AI Engineering Matters</span>
            </div>
            <h2 id="comparison-title">Naive LLM vs. TracePilot Grounded Architecture</h2>
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

        <div className="modal-scrollable-body">
          <div className="archetype-selector-bar">
            <span className="selector-label">Incident Scenario:</span>
            <div className="archetype-pills">
              {COMPARISON_ARCHETYPES.map((arch) => (
                <button
                  key={arch.id}
                  type="button"
                  className={`archetype-pill ${arch.id === selectedId ? "is-active" : ""}`}
                  onClick={() => setSelectedId(arch.id)}
                >
                  {arch.title}
                </button>
              ))}
            </div>
          </div>

          <div className="scenario-context-strip">
            <span className="context-repo">
              <Icon name="repository" size={14} /> {activeArchetype.repository}
            </span>
            <span className="context-incident">
              <strong>Incident:</strong> {activeArchetype.incidentTitle}
            </span>
          </div>

          <div className="comparison-columns-grid">
            {/* NAIVE COLUMN */}
            <article className="comparison-card naive-card">
              <div className="comparison-card-header">
                <div className="card-badge naive-badge">
                  <Icon name="x" size={15} /> Naive Chatbot / Direct LLM
                </div>
                <span className="model-tag">{activeArchetype.naive.model}</span>
              </div>

              <div className="comparison-confidence-row">
                <div className="confidence-stat false-confidence">
                  <strong>{Math.round(activeArchetype.naive.confidence * 100)}%</strong>
                  <span>Model Confidence</span>
                </div>
                <div className="confidence-warning">
                  <Icon name="info" size={14} />
                  <span>Ungrounded overconfidence (hallucinated certainty)</span>
                </div>
              </div>

              <div className="comparison-body-section">
                <h4>Generated Diagnosis</h4>
                <p className="diagnosis-text">{activeArchetype.naive.summary}</p>
              </div>

              <div className="comparison-culprit-section">
                <h4>Suspected Culprit</h4>
                <div className="culprit-box culprit-hallucinated">
                  <span className="mono">{activeArchetype.naive.suspectedCulprit}</span>
                </div>
              </div>

              <div className="comparison-failures-section">
                <h4>Critical Engineering Failure Modes</h4>
                <ul className="failure-list">
                  {activeArchetype.naive.failureReasons.map((reason) => (
                    <li key={reason}>
                      <Icon name="x" size={14} />
                      <span>{reason}</span>
                    </li>
                  ))}
                </ul>
              </div>

              <footer className="comparison-footer naive-footer">
                <div>
                  <span>Evidence Inspected</span>
                  <strong>{activeArchetype.naive.evidenceInspected}</strong>
                </div>
                <div>
                  <span>Verified Citations</span>
                  <strong className="zero-citations">0 (None)</strong>
                </div>
              </footer>
            </article>

            {/* GROUNDED COLUMN */}
            <article className="comparison-card grounded-card">
              <div className="comparison-card-header">
                <div className="card-badge grounded-badge">
                  <Icon name="check" size={15} /> TracePilot Grounded System
                </div>
                <span className="model-tag">{activeArchetype.grounded.model}</span>
              </div>

              <div className="comparison-confidence-row">
                <div className="confidence-stat grounded-confidence">
                  <strong>{Math.round(activeArchetype.grounded.confidence * 100)}%</strong>
                  <span>Calibrated Confidence</span>
                </div>
                <div className="confidence-valid">
                  <Icon name="check" size={14} />
                  <span>Honest uncertainty with missing info explicitly stated</span>
                </div>
              </div>

              <div className="comparison-body-section">
                <h4>Validated Diagnosis</h4>
                <p className="diagnosis-text">{activeArchetype.grounded.summary}</p>
              </div>

              <div className="comparison-culprit-section">
                <h4>Verified Culprit</h4>
                <div className="culprit-box culprit-verified">
                  <span className="mono">{activeArchetype.grounded.suspectedCulprit}</span>
                </div>
              </div>

              <div className="comparison-failures-section">
                <h4>Database & Verification Proof</h4>
                <ul className="proof-list">
                  {activeArchetype.grounded.verifiedProof.map((proof) => (
                    <li key={proof}>
                      <Icon name="check" size={14} />
                      <span>{proof}</span>
                    </li>
                  ))}
                </ul>
              </div>

              <footer className="comparison-footer grounded-footer">
                <div>
                  <span>Evidence Inspected</span>
                  <strong>{activeArchetype.grounded.evidenceInspected}</strong>
                </div>
                <div>
                  <span>Verified Citations</span>
                  <strong className="valid-citations">
                    {activeArchetype.grounded.citationsCount} Relational DB UUIDs
                  </strong>
                </div>
              </footer>
            </article>
          </div>

          <div className="modal-body-note-card">
            <Icon name="activity" size={16} />
            <span>
              <strong>Key Takeaway:</strong> TracePilot eliminates hallucinations by turning LLM tool calls
              into persisted PostgreSQL Evidence rows before citation validation occurs.
            </span>
          </div>
        </div>

        <footer className="modal-footer">
          <button className="primary-button" type="button" onClick={onClose}>
            Close Comparison
          </button>
        </footer>
      </div>
    </div>
  );
}
