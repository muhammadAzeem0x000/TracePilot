create table public.ai_operations (
    id uuid primary key default gen_random_uuid(),
    investigation_id uuid not null references public.investigations(id) on delete cascade,
    job_id uuid references public.investigation_jobs(id) on delete set null,
    trace_id uuid not null,
    span_id uuid not null unique,
    parent_span_id uuid,
    operation_type text not null check (operation_type in (
        'queue_wait', 'investigation', 'llm_call', 'github_tool',
        'embedding', 'knowledge_retrieval', 'rerank'
    )),
    provider text,
    model text,
    prompt_version text,
    tool_name text,
    started_at timestamptz not null,
    completed_at timestamptz not null,
    duration_ms integer not null check (duration_ms >= 0),
    input_tokens integer check (input_tokens is null or input_tokens >= 0),
    output_tokens integer check (output_tokens is null or output_tokens >= 0),
    total_tokens integer check (total_tokens is null or total_tokens >= 0),
    estimated_cost_usd numeric(14, 8) check (
        estimated_cost_usd is null or estimated_cost_usd >= 0
    ),
    fallback_used boolean not null default false,
    fallback_reason text,
    status text not null check (status in ('succeeded', 'failed')),
    error_type text,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    constraint ai_operations_time_order check (completed_at >= started_at),
    constraint ai_operations_parent_not_self check (parent_span_id is null or parent_span_id <> span_id)
);

create index ai_operations_investigation_started_idx
    on public.ai_operations (investigation_id, started_at);
create index ai_operations_trace_idx on public.ai_operations (trace_id, started_at);
create index ai_operations_job_idx on public.ai_operations (job_id) where job_id is not null;

alter table public.ai_operations enable row level security;

revoke all on table public.ai_operations from public, anon, authenticated;
grant select, insert on table public.ai_operations to service_role;

comment on table public.ai_operations is
    'Provider-neutral operational telemetry. Never stores prompts, evidence bodies, or credentials.';
