from thefuzz import process


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
        choices_with_positions = [
            (self.text[i : i + len(query)], i)
            for i in range(0, len(self.text), len(query) // 2)
        ]
        choices = [chunk for chunk, _ in choices_with_positions]
        best_match = process.extractOne(query, choices)
        matched_text, score = best_match

        if score < 80:
            raise Exception("No match found in text")

        index = choices.index(matched_text)
        position = choices_with_positions[index][1]
        end_position = self.text.find("\n", position)
        return end_position
