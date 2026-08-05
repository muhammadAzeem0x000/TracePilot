# Architecture Decision Records

## ADR-001: Separate FastAPI backend from Next.js

**Status:** Accepted for Day 1

TracePilot uses Next.js for presentation and a separate FastAPI service for business
operations. This keeps the browser focused on interaction while Python owns validation,
persistence, and future evidence/investigation workflows. It also gives the project an
explicit HTTP contract that can be tested without a browser.

The trade-off is two local processes, CORS configuration, and contract coordination
between TypeScript and Python. For this project, that cost is justified because the
planned investigation work will live naturally behind a Python API and should not be
embedded in Next.js route handlers.

## ADR-002: PostgreSQL/Supabase as the primary database

**Status:** Accepted for Day 1

Incidents, evidence, and investigations have clear relationships and constraints.
PostgreSQL provides enums, foreign keys, checks, indexes, timestamps, JSONB for source
metadata, and migrations without introducing another persistence model. Supabase hosts
PostgreSQL and exposes PostgREST, which lets the async API use normal HTTP I/O while the
schema remains explicit SQL.

The trade-off is reliance on Supabase availability and careful RLS/key configuration.
FastAPI uses a server-only service-role key while RLS and revoked grants deny browser and
anonymous database access. Tests inject an in-memory repository rather than depending on
the remote project. The service role must never reach the browser; production would also
add authenticated, tenant-scoped API authorization.

## ADR-003: Explicit Incident / Evidence / Investigation entities

**Status:** Accepted for Day 1

The schema separates the operational event (Incident), collected source material
(Evidence), and the lifecycle/output of an analysis attempt (Investigation). This keeps
evidence independently traceable and permits multiple investigations of one incident
without overloading the incident row.

The cost is additional joins and tables that are lightly used today. We accept that
small amount of foundation because the relationships already have clear meaning. We did
not add embeddings, prompts, model names, agent state, or speculative AI columns.
