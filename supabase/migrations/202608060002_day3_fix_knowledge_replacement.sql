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

    delete from public.knowledge_chunks as knowledge_chunk
    where knowledge_chunk.source_id = stored_source_id;

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

revoke execute on function public.replace_knowledge_source(
    text,
    public.knowledge_source_type,
    text,
    text,
    text,
    jsonb,
    jsonb
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
