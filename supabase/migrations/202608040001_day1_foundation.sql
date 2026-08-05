create extension if not exists pgcrypto;

create type public.incident_severity as enum ('low', 'medium', 'high', 'critical');
create type public.incident_status as enum ('open', 'investigating', 'resolved');
create type public.investigation_status as enum ('pending', 'in_progress', 'completed', 'failed');

create table public.incidents (
    id uuid primary key default gen_random_uuid(),
    title text not null check (char_length(title) between 3 and 200),
    description text not null check (char_length(description) between 1 and 10000),
    severity public.incident_severity not null,
    status public.incident_status not null default 'open',
    started_at timestamptz not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table public.evidence (
    id uuid primary key default gen_random_uuid(),
    incident_id uuid not null references public.incidents(id) on delete cascade,
    source_type text not null check (char_length(source_type) between 1 and 100),
    source_reference text,
    content text not null check (char_length(content) > 0),
    metadata jsonb not null default '{}'::jsonb,
    collected_at timestamptz not null default now()
);

create table public.investigations (
    id uuid primary key default gen_random_uuid(),
    incident_id uuid not null references public.incidents(id) on delete cascade,
    status public.investigation_status not null default 'pending',
    summary text,
    confidence numeric(4, 3) check (confidence between 0 and 1),
    started_at timestamptz,
    completed_at timestamptz,
    created_at timestamptz not null default now(),
    check (completed_at is null or started_at is null or completed_at >= started_at)
);

create index incidents_created_at_idx on public.incidents (created_at desc);
create index incidents_status_idx on public.incidents (status);
create index incidents_severity_idx on public.incidents (severity);
create index evidence_incident_id_idx on public.evidence (incident_id);
create index evidence_source_type_idx on public.evidence (source_type);
create index investigations_incident_id_idx on public.investigations (incident_id);
create index investigations_status_idx on public.investigations (status);

create function public.set_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

create trigger incidents_set_updated_at
before update on public.incidents
for each row execute function public.set_updated_at();

alter table public.incidents enable row level security;
alter table public.evidence enable row level security;
alter table public.investigations enable row level security;

revoke all on public.incidents from anon, authenticated;
revoke all on public.evidence from anon, authenticated;
revoke all on public.investigations from anon, authenticated;

-- FastAPI uses a server-only Supabase service-role key, which bypasses RLS.
-- Browser, anonymous, and ordinary authenticated roles receive no table access.
