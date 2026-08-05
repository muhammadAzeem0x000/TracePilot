# TracePilot Day-1 Architecture

TracePilot is currently a three-tier monorepo. It is intentionally a single web
application, one API service, and one PostgreSQL database rather than a collection
of microservices.

## Responsibilities

### Next.js (`apps/web`)

The browser renders the incident form, sends typed JSON to FastAPI, lists incidents,
and retrieves details when a user selects a record. `src/lib/api.ts` is the browser's
contract boundary. It knows the FastAPI base URL but contains no Supabase URL, key,
or client.

### FastAPI (`apps/api`)

FastAPI owns input validation, HTTP semantics, the incident use cases, and persistence
coordination:

- `app/schemas/incident.py` defines controlled enums and request/response contracts.
- `app/api/routes.py` maps HTTP operations to the incident service.
- `app/services/incidents.py` owns use-case behavior, including not-found handling.
- `app/repositories/incidents.py` translates the domain contract into persistence calls.
- `app/db/supabase.py` performs asynchronous PostgREST I/O against Supabase PostgreSQL.

Database failures are converted into a stable `503` response. Validation failures are
FastAPI's structured `422` response, and unknown incident IDs return a useful `404`.

### Supabase PostgreSQL (`supabase/migrations`)

PostgreSQL is the durable source of truth. The Day-1 migration creates relational
Incident, Evidence, and Investigation tables, enum types, foreign keys, checks,
indexes, an `updated_at` trigger, and locked-down row-level security. Evidence
and Investigation are schema foundations only; no pretend ingestion or AI behavior
exists yet.

## Request flow

1. A user submits the form in `apps/web/src/app/page.tsx`.
2. `createIncident` sends `POST /api/v1/incidents` to FastAPI.
3. Pydantic validates strings, enum membership, and timezone-aware `started_at`.
4. `IncidentService` calls the injected repository.
5. `SupabaseIncidentRepository` writes to PostgreSQL through Supabase PostgREST.
6. The database applies defaults and constraints, then returns the stored row.
7. FastAPI serializes the `IncidentResponse` and returns `201 Created`.
8. The UI inserts that response into the visible list and opens its details.

## Why the frontend does not write directly to Supabase

Incident creation is business behavior, not a UI implementation detail. Routing writes
through FastAPI creates one enforcement point for validation, error contracts, future
authorization, audit behavior, and later investigation workflows. Direct browser writes
would duplicate rules and couple the UI to database shape. It would also make a future
security model harder because every client would become a database client.

Day 1 has no user authentication, but database access is not anonymous: FastAPI uses a
server-only Supabase service-role key. RLS remains enabled and all table privileges are
revoked from the `anon` and `authenticated` roles. The key stays in the backend
environment and the browser has no Supabase dependency. API authentication and
user-scoped authorization are still required before production.
