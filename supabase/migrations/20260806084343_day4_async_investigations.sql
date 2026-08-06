create type public.investigation_stage as enum (
    'queued',
    'collecting_evidence',
    'retrieving_knowledge',
    'reasoning',
    'finalizing',
    'retry_scheduled',
    'completed',
    'failed'
);

create type public.investigation_job_status as enum (
    'queued',
    'running',
    'retry_scheduled',
    'completed',
    'failed'
);

create type public.investigation_review_decision as enum ('accepted', 'rejected');

alter table public.investigations
add column stage public.investigation_stage,
add column suspected_culprit_id text
    check (suspected_culprit_id is null or char_length(suspected_culprit_id) between 1 and 500),
add column tool_call_count integer not null default 0 check (tool_call_count >= 0),
add column duration_ms integer check (duration_ms is null or duration_ms >= 0);

update public.investigations
set stage = case status
    when 'completed' then 'completed'::public.investigation_stage
    when 'failed' then 'failed'::public.investigation_stage
    when 'in_progress' then 'reasoning'::public.investigation_stage
    else 'queued'::public.investigation_stage
end;

alter table public.investigations
alter column stage set default 'queued',
alter column stage set not null;

create unique index investigations_one_active_per_incident_idx
on public.investigations (incident_id)
where status in ('pending', 'in_progress');

create table public.investigation_jobs (
    id uuid primary key default gen_random_uuid(),
    investigation_id uuid not null unique
        references public.investigations(id) on delete cascade,
    status public.investigation_job_status not null default 'queued',
    attempt_count integer not null default 0 check (attempt_count >= 0),
    max_attempts integer not null default 3 check (max_attempts between 1 and 10),
    next_attempt_at timestamptz not null default now(),
    locked_at timestamptz,
    lease_expires_at timestamptz,
    last_error text check (last_error is null or char_length(last_error) <= 1000),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    completed_at timestamptz,
    constraint investigation_jobs_attempt_bound_check
        check (attempt_count <= max_attempts),
    constraint investigation_jobs_running_lease_check
        check (
            status <> 'running'
            or (locked_at is not null and lease_expires_at is not null)
        ),
    constraint investigation_jobs_completion_check
        check (
            status not in ('completed', 'failed')
            or completed_at is not null
        )
);

create index investigation_jobs_claim_idx
on public.investigation_jobs (next_attempt_at, created_at)
where status in ('queued', 'retry_scheduled');

create index investigation_jobs_stale_lease_idx
on public.investigation_jobs (lease_expires_at)
where status = 'running';

create table public.investigation_reviews (
    id uuid primary key default gen_random_uuid(),
    investigation_id uuid not null unique
        references public.investigations(id) on delete cascade,
    decision public.investigation_review_decision not null,
    note text check (note is null or char_length(note) between 1 and 2000),
    reviewed_at timestamptz not null default now(),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create trigger investigation_jobs_set_updated_at
before update on public.investigation_jobs
for each row execute function public.set_updated_at();

create trigger investigation_reviews_set_updated_at
before update on public.investigation_reviews
for each row execute function public.set_updated_at();

create or replace function public.enqueue_investigation_job(
    p_incident_id uuid,
    p_prompt_version text,
    p_model_name text,
    p_max_attempts integer
)
returns table (
    investigation_id uuid,
    investigation_status public.investigation_status,
    investigation_stage public.investigation_stage,
    investigation_created_at timestamptz,
    already_active boolean
)
language plpgsql
security invoker
set search_path = ''
as $$
declare
    active_investigation public.investigations%rowtype;
    created_investigation public.investigations%rowtype;
begin
    if p_max_attempts < 1 or p_max_attempts > 10 then
        raise exception 'max attempts must be between 1 and 10';
    end if;

    perform 1
    from public.incidents
    where id = p_incident_id
    for update;
    if not found then
        raise exception 'incident not found';
    end if;

    select investigation.*
    into active_investigation
    from public.investigations as investigation
    where investigation.incident_id = p_incident_id
      and investigation.status in ('pending', 'in_progress')
    order by investigation.created_at desc
    limit 1;

    if found then
        return query select
            active_investigation.id,
            active_investigation.status,
            active_investigation.stage,
            active_investigation.created_at,
            true;
        return;
    end if;

    insert into public.investigations (
        incident_id,
        status,
        stage,
        started_at,
        prompt_version,
        model_name
    ) values (
        p_incident_id,
        'pending',
        'queued',
        now(),
        p_prompt_version,
        p_model_name
    )
    returning * into created_investigation;

    insert into public.investigation_jobs (investigation_id, max_attempts)
    values (created_investigation.id, p_max_attempts);

    return query select
        created_investigation.id,
        created_investigation.status,
        created_investigation.stage,
        created_investigation.created_at,
        false;
end;
$$;

create or replace function public.claim_investigation_job(p_lease_seconds integer)
returns table (
    id uuid,
    investigation_id uuid,
    status public.investigation_job_status,
    attempt_count integer,
    max_attempts integer,
    next_attempt_at timestamptz,
    locked_at timestamptz,
    lease_expires_at timestamptz,
    last_error text,
    created_at timestamptz,
    updated_at timestamptz,
    completed_at timestamptz,
    reclaimed_stale_lease boolean
)
language plpgsql
security invoker
set search_path = ''
as $$
declare
    candidate_id uuid;
    candidate_was_stale boolean;
    exhausted record;
begin
    if p_lease_seconds < 30 or p_lease_seconds > 3600 then
        raise exception 'lease seconds must be between 30 and 3600';
    end if;

    for exhausted in
        update public.investigation_jobs as job
        set status = 'failed',
            last_error = 'Job lease expired after maximum attempts',
            completed_at = now(),
            locked_at = null,
            lease_expires_at = null
        where job.status = 'running'
          and job.lease_expires_at <= now()
          and job.attempt_count >= job.max_attempts
        returning job.investigation_id
    loop
        update public.investigations
        set status = 'failed',
            stage = 'failed',
            error_message = 'Investigation worker stopped after maximum attempts',
            completed_at = now()
        where public.investigations.id = exhausted.investigation_id;
    end loop;

    select job.id,
           job.status = 'running' and job.lease_expires_at <= now()
    into candidate_id, candidate_was_stale
    from public.investigation_jobs as job
    where job.attempt_count < job.max_attempts
      and (
          (job.status in ('queued', 'retry_scheduled') and job.next_attempt_at <= now())
          or (job.status = 'running' and job.lease_expires_at <= now())
      )
    order by job.next_attempt_at, job.created_at
    for update skip locked
    limit 1;

    if candidate_id is null then
        return;
    end if;

    return query
    update public.investigation_jobs as claimed
    set status = 'running',
        attempt_count = claimed.attempt_count + 1,
        locked_at = now(),
        lease_expires_at = now() + make_interval(secs => p_lease_seconds),
        completed_at = null
    where claimed.id = candidate_id
    returning
        claimed.id,
        claimed.investigation_id,
        claimed.status,
        claimed.attempt_count,
        claimed.max_attempts,
        claimed.next_attempt_at,
        claimed.locked_at,
        claimed.lease_expires_at,
        claimed.last_error,
        claimed.created_at,
        claimed.updated_at,
        claimed.completed_at,
        coalesce(candidate_was_stale, false);
end;
$$;

alter table public.investigation_jobs enable row level security;
alter table public.investigation_reviews enable row level security;

revoke all on public.investigation_jobs from anon, authenticated;
revoke all on public.investigation_reviews from anon, authenticated;
grant all on public.investigation_jobs to service_role;
grant all on public.investigation_reviews to service_role;

revoke execute on function public.enqueue_investigation_job(
    uuid, text, text, integer
) from public, anon, authenticated;
revoke execute on function public.claim_investigation_job(integer)
from public, anon, authenticated;

grant execute on function public.enqueue_investigation_job(
    uuid, text, text, integer
) to service_role;
grant execute on function public.claim_investigation_job(integer) to service_role;
