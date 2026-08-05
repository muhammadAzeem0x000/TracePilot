"""Inspect semantic, lexical, hybrid, or reranked repository knowledge results."""

import argparse
import asyncio
import json

from app.config.settings import Settings
from app.retrieval.factory import build_retrieval_service
from app.schemas.knowledge import KnowledgeSearchMode


async def search(
    query: str,
    repository_full_name: str,
    mode: KnowledgeSearchMode,
    top_k: int,
) -> dict[str, object]:
    response = await build_retrieval_service(Settings()).search(
        query,
        repository_full_name,
        mode,
        top_k,
    )
    return response.model_dump(mode="json")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query")
    parser.add_argument("--repository", required=True)
    parser.add_argument(
        "--mode",
        choices=[item.value for item in KnowledgeSearchMode],
        default="hybrid",
    )
    parser.add_argument("--top-k", type=int, default=5)
    arguments = parser.parse_args()
    result = asyncio.run(
        search(
            arguments.query,
            arguments.repository,
            KnowledgeSearchMode(arguments.mode),
            arguments.top_k,
        )
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
