from thefuzz import process


class ProgressiveBook:
    bookmark = "@@@"

    def __init__(self, path):
        self.path = path
        self._load()

    def progress(self, query):
        start_idx = self.text.find(self.bookmark) + len(self.bookmark) or 0
        end_idx = self._locate_position(query)

        if start_idx >= end_idx:
            raise Exception("Match found before bookmark")

        book_chunk = self.text[start_idx:end_idx].strip()
        self._move_bookmark(end_idx)
        return book_chunk

    def _load(self):
        with open(self.path, "r", encoding="utf-8") as f:
            self.text = f.read()

    def _move_bookmark(self, position):
        self.text = self.text.replace(self.bookmark, "")
        self.text = self.text[:position] + self.bookmark + self.text[position:]
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(self.text)
        self._load()

    def _locate_position(self, query):
        chunk_size = len(query)
        step = chunk_size // 2
        choices_with_positions = [
            (self.text[i : i + chunk_size], i) for i in range(0, len(self.text), step)
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
