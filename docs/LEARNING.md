# Day-1 Engineering Notes

These notes describe choices in this repository rather than general framework advice.

## Pydantic validation is the first API boundary

`app/schemas/incident.py` uses `StrEnum` values for severity/status, bounded strings,
and `AwareDatetime` for `started_at`. A value such as `"catastrophic"`, a blank title,
or a timestamp without a timezone is rejected before the route calls the service. The
same response model validates data returned by Supabase, so an unexpected database
shape becomes a controlled storage failure rather than leaking malformed JSON.

## Python typing and TypeScript typing protect different boundaries

Python type hints make repository/service dependencies reviewable and allow `mypy` to
check their composition, but Pydantic is still required because HTTP and database data
exist at runtime. TypeScript in `apps/web/src/lib/api.ts` makes component usage safe at
compile time, but the remote response is still an external trust boundary. Day 1 keeps
the browser parser small; a future generated/shared contract could add runtime response
validation if API surface growth justifies it.

## FastAPI dependency injection made persistence replaceable in tests

`app/api/dependencies.py` constructs the Supabase repository and incident service. Tests
override `get_incident_repository` with a small typed fake. This is enough to test routing,
validation, error codes, serialization, listing, and retrieval without a network or a
shared production database. It avoids a container framework or service locator.

## Async is useful specifically at the network boundary

Incident routes and repository calls are async because Supabase requests wait on network
I/O; `httpx.AsyncClient` lets the server serve other requests during that wait. The health
handler, settings parsing, Pydantic validation, and in-memory transformations remain
synchronous because making them async would add ceremony without releasing blocked I/O.

## Repository/service separation needs a reason

`SupabaseIncidentRepository` contains PostgREST paths and converts storage failures into
`RepositoryError`. `IncidentService` owns use-case semantics such as translating a missing
record into `IncidentNotFoundError`. The split currently earns its keep by making tests
independent of Supabase and keeping HTTP/database details out of each other; further
abstraction would not yet be justified.

## HTTP errors should stay stable when internals fail

Invalid requests receive FastAPI's `422`, unknown UUID records receive `404`, and storage
failures receive a non-sensitive `503`. `app/main.py` logs the internal exception but does
not return Supabase response details or keys to clients. A missing backend configuration
also returns `503` with the names of missing variables, while `/health` remains usable for
diagnosis.

