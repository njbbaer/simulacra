import pytest

from src.book_reader import BookReader


def _make_reader(tmp_path, text):
    path = tmp_path / "book.txt"
    path.write_text(text, encoding="utf-8")
    return BookReader(str(path))


SAMPLE = (
    "Chapter one.\n"
    "The quick brown fox.\n"
    "Jumped over the lazy dog.\n"
    "The end of the book here"  # no trailing newline
)


def test_mid_book_match(tmp_path):
    reader = _make_reader(tmp_path, SAMPLE)
    chunk, end_idx = reader.next_chunk("quick brown fox")
    assert chunk == "Chapter one.\nThe quick brown fox."
    assert end_idx == SAMPLE.index("Jumped") - 1  # the newline after the match


def test_final_passage_without_trailing_newline(tmp_path):
    reader = _make_reader(tmp_path, SAMPLE)
    chunk, end_idx = reader.next_chunk("end of the book")
    assert chunk.endswith("The end of the book here")
    assert end_idx == len(SAMPLE)


def test_empty_query_returns_remainder(tmp_path):
    reader = _make_reader(tmp_path, SAMPLE)
    start = SAMPLE.index("Jumped")
    chunk, end_idx = reader.next_chunk("   ", start_idx=start)
    assert chunk == SAMPLE[start:].strip()
    assert end_idx == len(SAMPLE)


def test_garbage_query_raises(tmp_path):
    reader = _make_reader(tmp_path, SAMPLE)
    with pytest.raises(ValueError, match="Could not find that passage"):
        reader.next_chunk("zxqwv nonsense not present")


def test_quote_before_position_raises(tmp_path):
    reader = _make_reader(tmp_path, SAMPLE)
    start = SAMPLE.index("Jumped")
    with pytest.raises(ValueError, match="ahead of your position"):
        reader.next_chunk("quick brown fox", start_idx=start)


def test_at_end_of_book_raises(tmp_path):
    reader = _make_reader(tmp_path, SAMPLE)
    with pytest.raises(ValueError, match="end of the book"):
        reader.next_chunk("", start_idx=len(SAMPLE))


REPEATED = (
    "The count bowed.\n"
    "A storm rose over the harbor.\n"
    "The count bowed.\n"
    "Morning came quietly.\n"
    "The count bowed.\n"
    "The letter was never sent.\n"
)


def test_quote_matching_twice_ahead_raises(tmp_path):
    reader = _make_reader(tmp_path, REPEATED)
    start = REPEATED.index("A storm")
    with pytest.raises(ValueError, match="more than one place ahead"):
        reader.next_chunk("The count bowed.", start_idx=start)


def test_quote_matching_once_ahead_syncs_despite_earlier_copies(tmp_path):
    reader = _make_reader(tmp_path, REPEATED)
    start = REPEATED.index("Morning")
    chunk, end_idx = reader.next_chunk("The count bowed.", start_idx=start)
    assert chunk == "Morning came quietly.\nThe count bowed."
    assert end_idx == REPEATED.index("The letter") - 1
