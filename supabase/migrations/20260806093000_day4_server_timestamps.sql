-- Keep durable queue timestamps on the database clock. Worker hosts may have small
-- clock offsets, and queue correctness must not depend on synchronized wall clocks.

create or replace function public.set_terminal_completion_timestamp()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
begin
  if new.status::text in ('completed', 'failed')
     and old.status::text not in ('completed', 'failed') then
    new.completed_at := clock_timestamp();
  end if;
  return new;
end;
$$;

create trigger investigations_terminal_timestamp
before update on public.investigations
for each row execute function public.set_terminal_completion_timestamp();

create trigger investigation_jobs_terminal_timestamp
before update on public.investigation_jobs
for each row execute function public.set_terminal_completion_timestamp();

create or replace function public.schedule_investigation_job_retry(
  p_job_id uuid,
  p_error_message text,
  p_delay_seconds integer
)
returns setof public.investigation_jobs
language plpgsql
security invoker
set search_path = ''
as $$
begin
  if p_delay_seconds < 1 or p_delay_seconds > 86400 then
    raise exception 'Retry delay must be between 1 and 86400 seconds'
      using errcode = '22023';
  end if;

  return query
  update public.investigation_jobs as job
  set
    status = 'retry_scheduled',
    next_attempt_at = clock_timestamp() + make_interval(secs => p_delay_seconds),
    last_error = left(p_error_message, 1000),
    locked_at = null,
    lease_expires_at = null,
    completed_at = null,
    updated_at = clock_timestamp()
  where job.id = p_job_id
    and job.status = 'running'
  returning job.*;
end;
$$;

revoke all on function public.set_terminal_completion_timestamp() from public;
revoke all on function public.set_terminal_completion_timestamp() from anon, authenticated;

revoke all on function public.schedule_investigation_job_retry(uuid, text, integer) from public;
revoke all on function public.schedule_investigation_job_retry(uuid, text, integer)
  from anon, authenticated;
grant execute on function public.schedule_investigation_job_retry(uuid, text, integer)
  to service_role;
