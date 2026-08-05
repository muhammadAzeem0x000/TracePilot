from app.schemas.knowledge import KnowledgeSearchResult


class ContextAssembler:
    def __init__(self, token_budget: int) -> None:
        if token_budget < 1:
            raise ValueError("Context token budget must be positive")
        self._token_budget = token_budget

    def select(
        self,
        candidates: list[KnowledgeSearchResult],
        top_k: int,
    ) -> tuple[list[KnowledgeSearchResult], int]:
        selected: list[KnowledgeSearchResult] = []
        selected_ids = set()
        used_tokens = 0
        for candidate in candidates:
            if len(selected) >= top_k:
                break
            if candidate.chunk_id in selected_ids:
                continue
            if used_tokens + candidate.token_count > self._token_budget:
                continue
            selected.append(candidate)
            selected_ids.add(candidate.chunk_id)
            used_tokens += candidate.token_count
        return selected, used_tokens

    @staticmethod
    def format(selected: list[KnowledgeSearchResult]) -> str:
        sections = [
            (
                f"[KNOWLEDGE chunk_id={item.chunk_id} title={item.title!r} "
                f"source={item.source_reference!r}]\n{item.content}"
            )
            for item in selected
        ]
        return "\n\n".join(sections)
