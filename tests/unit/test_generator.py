from typing import Any, cast

from src.generator import Drafts, StageResult


def result(content: str) -> StageResult:
    return StageResult(content, cast(Any, None), cast(Any, None))


class TestDrafts:
    def test_one_draft_records_its_content(self):
        assert Drafts([result("One")]).as_candidate() == {"content": "One"}

    def test_several_drafts_record_a_list(self):
        drafts = Drafts([result("One"), result("Two")])
        assert drafts.contents == ["One", "Two"]
        assert drafts.as_candidate() == {"drafts": ["One", "Two"]}
