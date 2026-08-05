import re

from app.schemas.knowledge import KnowledgeChunk

TOKEN_PATTERN = re.compile(r"\w+|[^\w\s]", re.UNICODE)
PARAGRAPH_PATTERN = re.compile(r"\n\s*\n+")
SENTENCE_PATTERN = re.compile(r"(?<=[.!?])\s+")


def approximate_token_count(text: str) -> int:
    """Stable approximation used for chunk and context budgets."""

    return len(TOKEN_PATTERN.findall(text))


class DeterministicChunker:
    def __init__(self, max_tokens: int, overlap_tokens: int) -> None:
        if max_tokens < 1:
            raise ValueError("max_tokens must be positive")
        if overlap_tokens < 0 or overlap_tokens >= max_tokens:
            raise ValueError("overlap_tokens must be between zero and max_tokens")
        self._max_tokens = max_tokens
        self._overlap_tokens = overlap_tokens

    def chunk(self, content: str) -> list[KnowledgeChunk]:
        normalized = content.replace("\r\n", "\n").strip()
        if not normalized:
            return []

        segments: list[str] = []
        for paragraph in PARAGRAPH_PATTERN.split(normalized):
            clean = paragraph.strip()
            if not clean:
                continue
            segments.extend(self._split_oversized(clean))

        chunks: list[str] = []
        current: list[str] = []
        current_tokens = 0
        for segment in segments:
            segment_tokens = approximate_token_count(segment)
            if current and current_tokens + segment_tokens > self._max_tokens:
                completed = "\n\n".join(current).strip()
                chunks.append(completed)
                overlap_budget = min(
                    self._overlap_tokens,
                    max(0, self._max_tokens - segment_tokens),
                )
                overlap = self._trailing_overlap(completed, overlap_budget)
                current = [overlap] if overlap else []
                current_tokens = approximate_token_count(overlap)
            current.append(segment)
            current_tokens += segment_tokens
        if current:
            chunks.append("\n\n".join(current).strip())

        return [
            KnowledgeChunk(
                chunk_index=index,
                content=chunk,
                token_count=approximate_token_count(chunk),
            )
            for index, chunk in enumerate(chunks)
            if chunk
        ]

    def _split_oversized(self, paragraph: str) -> list[str]:
        if approximate_token_count(paragraph) <= self._max_tokens:
            return [paragraph]

        sentences = [item.strip() for item in SENTENCE_PATTERN.split(paragraph) if item.strip()]
        pieces: list[str] = []
        current: list[str] = []
        current_tokens = 0
        for sentence in sentences:
            sentence_tokens = approximate_token_count(sentence)
            if sentence_tokens > self._max_tokens:
                if current:
                    pieces.append(" ".join(current))
                    current = []
                    current_tokens = 0
                pieces.extend(self._split_words(sentence))
                continue
            if current and current_tokens + sentence_tokens > self._max_tokens:
                pieces.append(" ".join(current))
                current = []
                current_tokens = 0
            current.append(sentence)
            current_tokens += sentence_tokens
        if current:
            pieces.append(" ".join(current))
        return pieces

    def _split_words(self, text: str) -> list[str]:
        words = text.split()
        pieces: list[str] = []
        current: list[str] = []
        for word in words:
            candidate = " ".join([*current, word])
            if current and approximate_token_count(candidate) > self._max_tokens:
                pieces.append(" ".join(current))
                current = [word]
            else:
                current.append(word)
        if current:
            pieces.append(" ".join(current))
        return pieces

    def _trailing_overlap(self, text: str, token_budget: int) -> str:
        if token_budget == 0:
            return ""
        tokens = text.split()
        selected: list[str] = []
        for token in reversed(tokens):
            candidate = " ".join(reversed([*selected, token]))
            if approximate_token_count(candidate) > token_budget:
                break
            selected.append(token)
        return " ".join(reversed(selected))
