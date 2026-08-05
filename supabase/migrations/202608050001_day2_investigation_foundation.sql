alter table public.incidents
add column repository_full_name text;

alter table public.incidents
add constraint incidents_repository_full_name_format_check
check (
    repository_full_name is null
    or repository_full_name ~ '^[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9._-]{1,100}$'
);

alter table public.evidence
add column investigation_id uuid references public.investigations(id) on delete cascade;

alter table public.investigations
add column suspected_change text,
add column supporting_evidence_ids uuid[] not null default '{}'::uuid[],
add column missing_information jsonb not null default '[]'::jsonb,
add column recommended_next_steps jsonb not null default '[]'::jsonb,
add column error_message text,
add column prompt_version text;

alter table public.investigations
add constraint investigations_missing_information_array_check
check (jsonb_typeof(missing_information) = 'array'),
add constraint investigations_recommended_next_steps_array_check
check (jsonb_typeof(recommended_next_steps) = 'array');

create index evidence_investigation_id_idx
on public.evidence (investigation_id);

