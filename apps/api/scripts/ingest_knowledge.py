"""Ingest repository-scoped Markdown/text knowledge into Supabase pgvector."""

import argparse
import asyncio
import json
from pathlib import Path

from app.ai.embeddings import GeminiEmbeddingProvider
from app.config.settings import Settings
from app.db.supabase import SupabaseRestClient
from app.knowledge.chunking import DeterministicChunker
from app.repositories.knowledge import SupabaseKnowledgeRepository
from app.schemas.knowledge import KnowledgeDocument, KnowledgeSourceType
from app.services.knowledge_ingestion import KnowledgeIngestionService

DIRECTORY_SOURCE_TYPES = {
    "runbooks": KnowledgeSourceType.RUNBOOK,
    "architecture": KnowledgeSourceType.ARCHITECTURE,
    "past_incidents": KnowledgeSourceType.PAST_INCIDENT,
}


def title_from_content(content: str, fallback: str) -> str:
    for line in content.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback.replace("-", " ").replace("_", " ").title()


def load_documents(root: Path, repository_full_name: str) -> list[KnowledgeDocument]:
    documents: list[KnowledgeDocument] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".md", ".txt"}:
            continue
        relative = path.relative_to(root).as_posix()
        source_type = DIRECTORY_SOURCE_TYPES.get(path.parent.name)
        if source_type is None:
            raise ValueError(
                f"Knowledge file must be under one of {sorted(DIRECTORY_SOURCE_TYPES)}: {relative}"
            )
        content = path.read_text(encoding="utf-8")
        documents.append(
            KnowledgeDocument(
                repository_full_name=repository_full_name,
                source_type=source_type,
                title=title_from_content(content, path.stem),
                source_reference=relative,
                content=content,
                metadata={"relative_path": relative},
            )
        )
    return documents


async def ingest(root: Path, repository_full_name: str) -> list[dict[str, object]]:
    settings = Settings()
    supabase_url, supabase_key = settings.require_supabase()
    embedding_url, embedding_key, embedding_model, dimensions = settings.require_embedding()
    provider = GeminiEmbeddingProvider(
        embedding_url,
        embedding_key,
        embedding_model,
        dimensions,
    )
    service = KnowledgeIngestionService(
        SupabaseKnowledgeRepository(SupabaseRestClient(supabase_url, supabase_key)),
        provider,
        DeterministicChunker(
            settings.knowledge_chunk_max_tokens,
            settings.knowledge_chunk_overlap_tokens,
        ),
    )
    results = await service.ingest_many(load_documents(root, repository_full_name))
    return [result.model_dump(mode="json") for result in results]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True, help="Repository scope in owner/name format")
    parser.add_argument(
        "--knowledge-dir",
        type=Path,
        default=Path("knowledge"),
        help="Directory containing runbooks/, architecture/, and past_incidents/",
    )
    arguments = parser.parse_args()
    results = asyncio.run(ingest(arguments.knowledge_dir, arguments.repository))
    summary = {
        action: sum(1 for result in results if result["action"] == action)
        for action in ("created", "updated", "skipped")
    }
    print(json.dumps({"summary": summary, "sources": results}, indent=2))


if __name__ == "__main__":
    main()
