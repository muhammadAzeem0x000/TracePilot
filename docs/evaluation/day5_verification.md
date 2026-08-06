# Day 5 verification record

Executed 2026-08-06 against the real TracePilot Supabase project and configured providers.

## Live investigation

- Incident: `26aeff02-d571-4562-8133-0995933db33e`
- Investigation: `ecc6f4e5-8273-4169-a5c4-a394d16abc00`
- Result: completed; 5 tool calls; 18 Evidence rows
- Knowledge: `search_knowledge` executed; 5 Evidence rows persisted; 3 cited; ownership valid
- Telemetry: 12 rows; all 7 operation types; 18,759 input + 2,117 output tokens
- Cost/fallback: cost unknown (pricing unconfigured); fallback not used
- Latency: 41,748 ms investigation; 20,935 LLM; 7,414 GitHub; 6,263 retrieval; 711 embedding;
  2,381 rerank

The initial telemetry attempt exposed host/Supabase clock skew in queue timing. The repaired live run
clamped queue start to the database-created timestamp and persisted every operation type.

## Evaluation

- Frozen holdout: exactly one official live run, 7/7 completed and correct, citation precision and
  recall 1.0, invalid citation rate 0, 10,335.0 ms average, 6,733.7 tokens average, no fallback.
- Adversarial suite: 13/13 expected blocks; 0 forbidden tools, cross-repository access, invalid
  citations, or unsafe mutations.
- Retrieval and Day-4 development reports were not relabeled as holdout results.

## Database and API

- Both Day-5 migrations applied; `ai_operations` has RLS enabled.
- Public/anonymous/authenticated roles have no table privileges. `service_role` has SELECT/INSERT only.
- Supabase advisors reported informational fail-closed no-policy notices and unused indexes; no
  security error/warning required a schema change.
- FastAPI `/health` returned HTTP 200. A real service-role container listed persisted incidents.
- Public-demo mutation tests returned HTTP 403 while read endpoints remained available.

## Container, frontend, and browser

- Backend image built on Python 3.12.11, ran as `tracepilot`, became healthy, and served Supabase data.
- A Linux Next.js production build exposed missing native optional packages; the lockfile now includes
  Linux SWC, Tailwind oxide, and lightningcss packages. The rebuilt production image succeeded.
- Browser verification used the production frontend and real API data. The read-only banner appeared;
  create controls were disabled; run/review actions were absent; GitHub, RUNBOOK, ARCHITECTURE, and
  PAST INCIDENT Evidence remained separate from the preliminary hypothesis; metrics matched the live
  trace; the console had zero warnings/errors.

## Deployment attempt

Vercel CLI authentication succeeded. No Koyeb CLI profile, token, or environment credential was
available. The frontend was intentionally not deployed alone because it would have no public backend.
No deployment URL exists, and nothing was pushed as part of Day 5.
