import rapidfuzz
from rapidfuzz.distance import ScoreAlignment

_MATCH_SCORE_THRESHOLD = 80


class BookReader:
    def __init__(self, path: str) -> None:
        self.path = path
        with open(path, encoding="utf-8") as f:
            self.text = f.read()

    def next_chunk(self, query: str, start_idx: int = 0) -> tuple[str, int]:
        if start_idx >= len(self.text):
            raise ValueError("Already at the end of the book")
        end_idx = (
            self._find_position(query, start_idx) if query.strip() else len(self.text)
        )
        chunk = self.text[start_idx:end_idx].strip()
        return chunk, end_idx

    @property
    def length(self) -> int:
        return len(self.text)

    def _find_position(self, query: str, start_idx: int) -> int:
        """Return the end of the line holding the query's only match ahead."""
        match = self._match(query, start_idx, len(self.text))
        if match is None:
            raise ValueError("Could not find that passage ahead of your position")
        start, end = start_idx + match.dest_start, start_idx + match.dest_end
        if self._match(query, start_idx, start) or self._match(
            query, end, len(self.text)
        ):
            raise ValueError(
                "That passage matches more than one place ahead, quote more of it"
            )
        newline = self.text.find("\n", end)
        return newline if newline != -1 else len(self.text)

    def _match(self, query: str, start: int, end: int) -> ScoreAlignment | None:
        """Return the span's best match over the threshold, if the query fits."""
        span = self.text[start:end]
        if len(span) < len(query):
            return None
        return rapidfuzz.fuzz.partial_ratio_alignment(
            query, span, score_cutoff=_MATCH_SCORE_THRESHOLD
        )
