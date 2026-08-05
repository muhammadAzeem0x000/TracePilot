create extension if not exists vector with schema extensions;

create type public.knowledge_source_type as enum (
    'runbook',
    'architecture',
    'past_incident'
);

create table public.knowledge_sources (
    id uuid primary key default gen_random_uuid(),
    repository_full_name text not null,
    source_type public.knowledge_source_type not null,
    title text not null check (char_length(title) between 1 and 300),
    source_reference text not null check (char_length(source_reference) between 1 and 500),
    content_hash text not null check (content_hash ~ '^[0-9a-f]{64}$'),
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint knowledge_sources_repository_format_check check (
        char_length(repository_full_name) <= 140
        and repository_full_name ~ '^[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9._-]{1,100}$'
    ),
    unique (repository_full_name, source_reference)
);

create table public.knowledge_chunks (
    id uuid primary key default gen_random_uuid(),
    source_id uuid not null references public.knowledge_sources(id) on delete cascade,
    chunk_index integer not null check (chunk_index >= 0),
    content text not null check (char_length(content) > 0),
    token_count integer not null check (token_count > 0),
    embedding extensions.vector(768) not null,
    metadata jsonb not null default '{}'::jsonb,
    fts tsvector generated always as (to_tsvector('english', content)) stored,
    created_at timestamptz not null default now(),
    unique (source_id, chunk_index)
);

create index knowledge_sources_repository_idx
on public.knowledge_sources (repository_full_name);

create index knowledge_chunks_source_idx
on public.knowledge_chunks (source_id, chunk_index);

create index knowledge_chunks_fts_idx
on public.knowledge_chunks using gin (fts);

create index knowledge_chunks_embedding_hnsw_idx
on public.knowledge_chunks using hnsw (embedding vector_cosine_ops);

create trigger knowledge_sources_set_updated_at
before update on public.knowledge_sources
for each row execute function public.set_updated_at();

create or replace function public.replace_knowledge_source(
    p_repository_full_name text,
    p_source_type public.knowledge_source_type,
    p_title text,
    p_source_reference text,
    p_content_hash text,
    p_metadata jsonb,
    p_chunks jsonb
)
returns table (source_id uuid)
language plpgsql
set search_path = ''
as $$
declare
    stored_source_id uuid;
begin
    insert into public.knowledge_sources (
        repository_full_name,
        source_type,
        title,
        source_reference,
        content_hash,
        metadata
    ) values (
        p_repository_full_name,
        p_source_type,
        p_title,
        p_source_reference,
        p_content_hash,
        coalesce(p_metadata, '{}'::jsonb)
    )
    on conflict (repository_full_name, source_reference)
    do update set
        source_type = excluded.source_type,
        title = excluded.title,
        content_hash = excluded.content_hash,
        metadata = excluded.metadata
    returning id into stored_source_id;

    delete from public.knowledge_chunks where source_id = stored_source_id;

    insert into public.knowledge_chunks (
        source_id,
        chunk_index,
        content,
        token_count,
        embedding,
        metadata
    )
    select
        stored_source_id,
        (item->>'chunk_index')::integer,
        item->>'content',
        (item->>'token_count')::integer,
        (item->>'embedding')::extensions.vector(768),
        coalesce(item->'metadata', '{}'::jsonb)
    from jsonb_array_elements(p_chunks) as item;

    return query select stored_source_id;
end;
$$;

create or replace function public.search_knowledge_semantic(
    query_embedding extensions.vector(768),
    filter_repository text,
    match_count integer
)
returns table (
    chunk_id uuid,
    source_id uuid,
    source_type public.knowledge_source_type,
    source_reference text,
    title text,
    content text,
    token_count integer,
    metadata jsonb,
    score double precision
)
language sql
stable
set search_path = ''
as $$
    select
        kc.id,
        ks.id,
        ks.source_type,
        ks.source_reference,
        ks.title,
        kc.content,
        kc.token_count,
        kc.metadata || jsonb_build_object('source_metadata', ks.metadata),
        1 - (kc.embedding <=> query_embedding) as score
    from public.knowledge_chunks kc
    join public.knowledge_sources ks on ks.id = kc.source_id
    where ks.repository_full_name = filter_repository
    order by kc.embedding <=> query_embedding, kc.id
    limit least(greatest(match_count, 1), 50);
$$;

create or replace function public.search_knowledge_lexical(
    query_text text,
    filter_repository text,
    match_count integer
)
returns table (
    chunk_id uuid,
    source_id uuid,
    source_type public.knowledge_source_type,
    source_reference text,
    title text,
    content text,
    token_count integer,
    metadata jsonb,
    score real
)
language sql
stable
set search_path = ''
as $$
    with parsed_query as (
        select websearch_to_tsquery('english', query_text) as value
    )
    select
        kc.id,
        ks.id,
        ks.source_type,
        ks.source_reference,
        ks.title,
        kc.content,
        kc.token_count,
        kc.metadata || jsonb_build_object('source_metadata', ks.metadata),
        ts_rank_cd(kc.fts, parsed_query.value) as score
    from public.knowledge_chunks kc
    join public.knowledge_sources ks on ks.id = kc.source_id
    cross join parsed_query
    where ks.repository_full_name = filter_repository
      and kc.fts @@ parsed_query.value
    order by score desc, kc.id
    limit least(greatest(match_count, 1), 50);
$$;

alter table public.knowledge_sources enable row level security;
alter table public.knowledge_chunks enable row level security;

revoke all on public.knowledge_sources from anon, authenticated;
revoke all on public.knowledge_chunks from anon, authenticated;
revoke execute on function public.replace_knowledge_source(
    text,
    public.knowledge_source_type,
    text,
    text,
    text,
    jsonb,
    jsonb
) from public, anon, authenticated;
revoke execute on function public.search_knowledge_semantic(
    extensions.vector,
    text,
    integer
) from public, anon, authenticated;
revoke execute on function public.search_knowledge_lexical(
    text,
    text,
    integer
) from public, anon, authenticated;

grant execute on function public.replace_knowledge_source(
    text,
    public.knowledge_source_type,
    text,
    text,
    text,
    jsonb,
    jsonb
) to service_role;
grant execute on function public.search_knowledge_semantic(
    extensions.vector,
    text,
    integer
) to service_role;
grant execute on function public.search_knowledge_lexical(
    text,
    text,
    integer
) to service_role;
