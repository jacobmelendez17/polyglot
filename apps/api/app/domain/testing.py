"""Testing maps — pure rules (spec §7).

Comprehension testing in the style of the JLPT (N5–N1): audio + a caption, a
question, four options, one right answer. Three maps: `cefr` (standardized bands),
`app` (only what the learner has covered in the curriculum), and `life` (casual
real-world scenarios).

The rules that must be exact live here: a submitted choice must be a real option
index, grading is a plain equality against the server-held answer, and a session's
score is the count of correct answers. Keeping these pure means the client can never
smuggle in the right index — the correct answer is compared server-side and this
module never sees anything client-controlled beyond the chosen index.
"""
from __future__ import annotations

MAPS: tuple[str, ...] = ("cefr", "app", "life")
OPTIONS_PER_QUESTION = 4


def is_map(value: str) -> bool:
    return value in MAPS


def validate_choice(chosen: int, num_options: int) -> None:
    if not isinstance(chosen, int) or isinstance(chosen, bool):
        raise ValueError("Choice must be an integer index.")
    if chosen < 0 or chosen >= num_options:
        raise ValueError("Choice is out of range.")


def is_correct(chosen: int, correct_index: int) -> bool:
    return chosen == correct_index


def score_from_answers(answers: list[dict]) -> tuple[int, int]:
    """(#correct, #answered) over an attempt's recorded answers."""
    total = len(answers)
    correct = sum(1 for a in answers if a.get("correct"))
    return correct, total


def percentage(correct: int, total: int) -> int:
    return round(100 * correct / total) if total else 0
