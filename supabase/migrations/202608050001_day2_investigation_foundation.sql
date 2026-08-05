alter table public.incidents
add column repository_full_name text,
add constraint incidents_repository_full_name_format_check
check (
    repository_full_name is null
    or (
        char_length(repository_full_name) <= 140
        and repository_full_name ~ '^[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9._-]{1,100}$'
    )
);

alter table public.evidence
add column investigation_id uuid references public.investigations(id) on delete cascade;

alter table public.investigations
add column suspected_change text,
add column supporting_evidence_ids uuid[] not null default '{}',
add column missing_information text[] not null default '{}',
add column recommended_next_steps text[] not null default '{}',
add column error_message text,
add column prompt_version text,
add column model_name text,
add column updated_at timestamptz not null default now();

create index evidence_investigation_id_idx on public.evidence (investigation_id);
create index investigations_created_at_idx on public.investigations (created_at desc);

create trigger investigations_set_updated_at
before update on public.investigations
for each row execute function public.set_updated_at();

revoke all on public.incidents from anon, authenticated;
revoke all on public.evidence from anon, authenticated;
revoke all on public.investigations from anon, authenticated;

