"""Review queue: pair-distance rules (PLANNING §11)."""
from hypothesis import given, settings
from hypothesis import strategies as st

from app.domain.queue import (
    MAX_PAIR_DISTANCE,
    Direction,
    Prompt,
    QueueItem,
    ReviewOrder,
    build_queue,
    pair_distance,
    validate_queue,
)


def _items(n: int, stage: int = 3) -> list[QueueItem]:
    return [QueueItem("vocabulary", f"i{k}", stage, float(k)) for k in range(n)]


def test_spec_examples_of_validity():
    def q(positions: list[int]) -> list[Prompt]:
        return [Prompt("vocabulary", str(p), Direction.es_to_en, 3) for p in positions]

    # [1,0,0,0,0,0,1] -> the two 1s have 5 prompts between: valid
    assert pair_distance(q([1, 0, 0, 0, 0, 0, 1]), "1") == 5
    # [1,0,...,1] with 9 between: invalid
    far = q([1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1])
    assert pair_distance(far, "1") == 9


def test_every_item_gets_exactly_two_prompts():
    q = build_queue(_items(12), seed=7)
    assert len(q) == 24
    for k in range(12):
        assert sum(1 for p in q if p.item_id == f"i{k}") == 2


def test_pairs_are_always_within_max_distance():
    for seed in range(50):
        q = build_queue(_items(15), seed=seed)
        assert validate_queue(q), f"seed {seed} produced an invalid queue"


@settings(max_examples=40, deadline=None)
@given(n=st.integers(min_value=1, max_value=30), seed=st.integers(min_value=0, max_value=9999))
def test_property_all_queues_valid(n, seed):
    q = build_queue(_items(n), seed=seed)
    assert len(q) == n * 2
    assert validate_queue(q)


def test_back_to_back_setting_gives_distance_zero():
    q = build_queue(_items(5), back_to_back=True, first_direction=Direction.es_to_en, seed=1)
    for k in range(5):
        assert pair_distance(q, f"i{k}") == 0


def test_back_to_back_respects_direction_order():
    q = build_queue(_items(2), back_to_back=True, first_direction=Direction.en_to_es, seed=1)
    assert q[0].direction is Direction.en_to_es
    assert q[1].direction is Direction.es_to_en


def test_same_seed_gives_same_queue():
    a = build_queue(_items(10), seed=42)
    b = build_queue(_items(10), seed=42)
    assert [(p.item_id, p.direction) for p in a] == [(p.item_id, p.direction) for p in b]


def test_stage_order_sorts_by_stage():
    items = [
        QueueItem("vocabulary", "high", 8), QueueItem("vocabulary", "low", 1),
        QueueItem("vocabulary", "mid", 4),
    ]
    q = build_queue(items, order=ReviewOrder.stage_order, back_to_back=True, seed=1)
    assert q[0].item_id == "low"


def test_empty_queue():
    assert build_queue([], seed=1) == []


def test_max_distance_constant_is_five():
    assert MAX_PAIR_DISTANCE == 5
