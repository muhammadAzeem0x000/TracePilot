# TracePilot Architecture — Day 2

TracePilot remains a small monorepo: one Next.js application, one FastAPI service, and one
Supabase PostgreSQL database. Day 2 adds a bounded LLM/tool workflow inside the existing API;
it does not add a worker, queue, orchestration framework, or another service.

## Responsibilities

### Next.js (`apps/web`)

`src/lib/api.ts` is the browser contract boundary. The page creates incidents through FastAPI,
loads investigations/evidence for the selected incident, and starts a synchronous investigation.
It renders two deliberately different panels: persisted `EVIDENCE` and the
`AI PRELIMINARY HYPOTHESIS`. The browser has no Supabase, GitHub, or LLM credential.

### FastAPI (`apps/api`)

- `app/api/routes.py` owns HTTP status codes and response schemas.
- `app/services/investigations.py` owns the deterministic orchestration loop and failure state.
- `app/ai/provider.py` is the small OpenAI-compatible provider boundary.
- `app/ai/prompts/investigation_v1.py` versions the prompt and prompt-injection boundary.
- `app/tools/github.py` is the only tool dispatcher. It validates the name and Pydantic arguments,
  invokes Python, and persists the normalized result before returning it to the model.
- `app/integrations/github.py` performs only GitHub `GET` requests and converts remote payloads
  into application-owned schemas.
- repository modules isolate PostgREST paths and response validation.

The service logs investigation lifecycle, model calls, requested tool names, success/failure,
and evidence counts. It does not log tokens, provider payloads, raw repository content, or keys.

### Supabase PostgreSQL

`Incident` owns operational facts and optional `repository_full_name`. `Evidence` owns retrieved
GitHub facts and identifies both its incident and investigation. `Investigation` owns lifecycle
state and the validated model conclusion. Evidence and hypothesis remain separate records, so a
consumer never has to infer which text came from GitHub and which came from a model.

RLS is enabled and grants are revoked for `anon` and `authenticated`. FastAPI uses the
server-only key. No browser database policies exist yet because the browser is intentionally not
a database client.

## Investigation request flow

1. `POST /api/v1/incidents/{id}/investigations` loads the incident and requires repository context.
2. The investigation repository creates an `in_progress` row with prompt and model identifiers.
3. The provider receives the incident prompt and five read-only tool definitions.
4. If the model proposes a call, `GitHubToolExecutor` checks the exact allowlist and validates JSON
   arguments with models that forbid extra fields.
5. Python calls the configured incident repository through GitHub REST. Repository content is
   treated as untrusted data and cannot redefine tool permissions.
6. The normalized result is stored as one or more `Evidence` rows. Only bounded fields/content and
   the new evidence UUIDs return to the model.
7. The loop permits at most six total tool calls. A conclusion before any evidence call is invalid.
8. `PreliminaryInvestigationResult` parses the final JSON. One correction attempt is allowed.
9. The evidence repository queries every citation using incident ID, investigation ID, and UUID.
   Set equality must hold; invented or cross-context UUIDs fail validation.
10. Only then is the investigation marked `completed`. Any critical failure attempts to mark the row
    `failed` and the API returns `502` rather than a false conclusion.

## Why business writes do not go directly to Supabase

FastAPI is the enforcement point for incident validation, tool permissions, provider behavior,
evidence provenance, citation checks, stable HTTP errors, and future authorization. A direct
browser write would bypass those invariants, expose persistence shape, and risk exposing a
service-role key. The trade-off is two local processes and explicit TypeScript/Python contract
coordination, which is appropriate for the workflow under study.

## Async boundaries

GitHub, LLM, and Supabase methods are async because they wait on network I/O. Prompt construction,
Pydantic parsing, allowlist checks, evidence serialization, and route-independent transformations
remain synchronous. The Day-2 HTTP request waits for the whole workflow; background execution is
explicitly deferred.
