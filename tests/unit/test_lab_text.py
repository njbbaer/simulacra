from src.lab import sections, sentences, speech

RESPONSE = """<character>
A thought.
</character>

<playwright>
A note.
</playwright>

(She sits.) No. I am not the one asking. (She stands.)

Go on, then."""


def test_sentences_are_numbered_as_the_users_marks_number_them() -> None:
    spoken = sections(RESPONSE)["spoken"]

    assert sentences(spoken) == ["No.", "I am not the one asking.", "Go on, then."]
    assert speech(spoken) == "No. I am not the one asking. Go on, then."
    assert sections(RESPONSE)["note"] == "A note."
