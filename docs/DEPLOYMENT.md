# Deployment runbook

TracePilot is a portfolio system, not commercial production software. The intended public shape is a Vercel-hosted Next.js frontend and a Koyeb-hosted FastAPI container. Supabase remains the managed PostgreSQL store.

## Required production posture

- Set `APP_ENVIRONMENT=production`.
- Set `PUBLIC_DEMO_MODE=true` for an anonymous public portfolio deployment.
- Set an exact HTTPS frontend origin in `CORS_ORIGINS`; wildcards are rejected.
- Keep `SUPABASE_KEY`, `GITHUB_TOKEN`, LLM keys, and embedding keys only on the backend.
- Run one Uvicorn process per container. The in-process durable queue worker must not be duplicated by multiple Uvicorn workers.
- Apply every forward migration before starting the new image.

## Backend image

From the repository root:

```powershell
docker build --file apps/api/Dockerfile --tag tracepilot-api:day5 .
docker run --rm --name tracepilot-api -p 8000:8000 --env-file .env tracepilot-api:day5
```

The image runs as the unprivileged `tracepilot` user and exposes `/health`. `.dockerignore` prevents `.env` from entering the build context.

## Vercel

Use `apps/web` as the project root and set `NEXT_PUBLIC_API_URL` to the deployed Koyeb HTTPS URL. No backend credential belongs in Vercel.

## Koyeb

Deploy the repository with `apps/api/Dockerfile`, repository-root build context, port `8000`, and `/health` as the health check. Configure all backend environment values in Koyeb's encrypted settings. Public demo mode must stay enabled unless a real authentication/authorization layer is added.

## Rollback

Roll back the application image independently. Database migrations are forward-only; do not drop telemetry or investigation data as part of an application rollback. If an incompatible database fix is needed, add a corrective migration.

## Verification and current deployment status

On 2026-08-06 the image built with Python 3.12.11, ran as the unprivileged `tracepilot` user, became
healthy, returned `/health`, and read real Supabase incidents. The production frontend also built in
a Linux container after native optional dependencies were locked.

Vercel CLI authentication was available, but no Koyeb CLI profile/token or backend credential was
present. TracePilot was therefore not partially deployed: a frontend with no reachable API would be
a broken and misleading demo. There is currently no public URL and no Day-5 push was performed.
