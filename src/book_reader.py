import rapidfuzz


class BookReader:
    def __init__(self, path):
        self.path = path
        self._load()

    def next_chunk(self, query, start_idx=0):
        if query and query.strip() != "":
            end_idx = self._find_position(query)
        else:
            end_idx = len(self.text)

        if start_idx >= end_idx:
            raise Exception("Match cannot be before latest position")

        chunk = self.text[start_idx:end_idx].strip()
        return chunk, end_idx

    def _load(self):
        with open(self.path, "r", encoding="utf-8") as f:
            self.text = f.read()

    def _find_position(self, query):
        match = rapidfuzz.fuzz.partial_ratio_alignment(query, self.text)
        if match.score < 80:
            raise Exception("No match found in text")

        end_position = self.text.find("\n", match.dest_end)
        return end_position
