import rapidfuzz

_MATCH_SCORE_THRESHOLD = 80


class BookReader:
    def __init__(self, path: str) -> None:
        self.path = path
        self._load()

    def next_chunk(self, query: str, start_idx: int = 0) -> tuple[str, int]:
        if query and query.strip():
            end_idx = self._find_position(query)
        else:
            end_idx = len(self.text)

        if start_idx >= end_idx:
            raise ValueError("That passage is at or before your current position")

        chunk = self.text[start_idx:end_idx].strip()
        return chunk, end_idx

    @property
    def length(self) -> int:
        return len(self.text)

    def _find_position(self, query: str) -> int:
        match = rapidfuzz.fuzz.partial_ratio_alignment(query, self.text)
        if match is None or match.score < _MATCH_SCORE_THRESHOLD:
            raise ValueError("Could not find that passage in the book")

        newline = self.text.find("\n", match.dest_end)
        return newline if newline != -1 else len(self.text)

    def _load(self) -> None:
        with open(self.path, encoding="utf-8") as f:
            self.text = f.read()
