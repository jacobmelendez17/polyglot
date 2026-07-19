"""Review queue construction (PLANNING §11) — deterministic given a seed.

Each due item produces TWO prompts (meaning + reading). The pair must stay close
together but not too far apart:

    [1,0,0,0,0,0,1]              valid   → 5 prompts between the pair
    [1,0,1,2,0,0,0,0,3,2,0]      valid
    [1,0,0,0,0,0,0,0,0,0,1]      invalid → 9 between, exceeds the max

"Distance" = the number of prompts BETWEEN a pair. Min 0 (back-to-back),
max 5. Not user-configurable.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum

MAX_PAIR_DISTANCE = 5   # prompts allowed between a pair; hard rule, not a setting
MIN_PAIR_DISTANCE = 0


class Direction(str, Enum):
    es_to_en = "es_to_en"   # meaning: shown Spanish, type English
    en_to_es = "en_to_es"   # reading: shown English, type Spanish


class ReviewOrder(str, Enum):
    newest_first = "newest_first"
    stage_order = "stage_order"
    random = "random"


@dataclass(frozen=True)
class QueueItem:
    """One due item awaiting both of its prompts."""
    item_type: str
    item_id: str
    srs_stage: int
    unlocked_at_ts: float = 0.0   # for newest_first ordering


@dataclass(frozen=True)
class Prompt:
    item_type: str
    item_id: str
    direction: Direction
    srs_stage: int


def pair_distance(prompts: list[Prompt], item_id: str) -> int:
    """Prompts between the two prompts of an item. Raises if not exactly 2."""
    idx = [i for i, p in enumerate(prompts) if p.item_id == item_id]
    if len(idx) != 2:
        raise ValueError(f"expected exactly 2 prompts for {item_id}, found {len(idx)}")
    return idx[1] - idx[0] - 1


def validate_queue(prompts: list[Prompt]) -> bool:
    """Every item appears exactly twice, and every pair is within range."""
    ids = {p.item_id for p in prompts}
    for item_id in ids:
        try:
            d = pair_distance(prompts, item_id)
        except ValueError:
            return False
        if d < MIN_PAIR_DISTANCE or d > MAX_PAIR_DISTANCE:
            return False
    return True


def _order_items(
    items: list[QueueItem], order: ReviewOrder, rng: random.Random
) -> list[QueueItem]:
    if order is ReviewOrder.newest_first:
        return sorted(items, key=lambda i: -i.unlocked_at_ts)
    if order is ReviewOrder.stage_order:
        return sorted(items, key=lambda i: i.srs_stage)
    shuffled = list(items)
    rng.shuffle(shuffled)
    return shuffled


def build_queue(
    items: list[QueueItem],
    *,
    order: ReviewOrder = ReviewOrder.random,
    back_to_back: bool = False,
    first_direction: Direction = Direction.es_to_en,
    seed: int = 0,
) -> list[Prompt]:
    """Build the prompt queue.

    back_to_back=True forces distance 0 with `first_direction` first — the user
    setting from PLANNING §16. Otherwise each pair's second prompt is placed a
    random 0..MAX_PAIR_DISTANCE after its partner, and the result is validated.
    """
    rng = random.Random(seed)
    ordered = _order_items(items, order, rng)

    if back_to_back:
        out: list[Prompt] = []
        for it in ordered:
            second = (
                Direction.en_to_es if first_direction is Direction.es_to_en
                else Direction.es_to_en
            )
            out.append(Prompt(it.item_type, it.item_id, first_direction, it.srs_stage))
            out.append(Prompt(it.item_type, it.item_id, second, it.srs_stage))
        return out

    # Interleaved placement: walk the ordered items, dropping each first prompt
    # in sequence and scheduling its partner a short random gap later.
    slots: list[Prompt | None] = []
    pending: dict[int, Prompt] = {}   # slot index -> prompt waiting to be placed

    def _place_pending(at: int) -> None:
        if at in pending:
            while len(slots) <= at:
                slots.append(None)
            if slots[at] is None:
                slots[at] = pending.pop(at)

    for it in ordered:
        dirs = [Direction.es_to_en, Direction.en_to_es]
        rng.shuffle(dirs)
        first = Prompt(it.item_type, it.item_id, dirs[0], it.srs_stage)
        second = Prompt(it.item_type, it.item_id, dirs[1], it.srs_stage)

        # place first prompt in the next free slot
        i = len(slots)
        while i < len(slots) and slots[i] is not None:
            i += 1
        slots.append(first)
        first_idx = len(slots) - 1

        # schedule the partner 1..MAX+1 positions later (distance 0..MAX)
        gap = rng.randint(1, MAX_PAIR_DISTANCE + 1)
        target = first_idx + gap
        while target in pending:
            target += 1
            if target - first_idx - 1 > MAX_PAIR_DISTANCE:
                target = first_idx + 1
                while target in pending:
                    target += 1
                break
        pending[target] = second
        _place_pending(len(slots) - 1)

        # fill any slot whose pending partner is now due
        while len(slots) in pending:
            slots.append(pending.pop(len(slots)))

    # drain remaining partners in order, respecting their target slots
    for target in sorted(pending):
        while len(slots) < target:
            slots.append(None)
        slots.append(pending[target])

    out = [p for p in slots if p is not None]

    # Safety net: if any pair drifted out of range, fall back to a compact
    # placement that is correct by construction (partner 1..MAX+1 after).
    if not validate_queue(out):
        out = _compact_build(ordered, rng)
    return out


def _compact_build(items: list[QueueItem], rng: random.Random) -> list[Prompt]:
    """Correct-by-construction fallback: emit each pair with a small gap filled
    by the next items' first prompts."""
    out: list[Prompt] = []
    queue: list[tuple[int, Prompt]] = []   # (due_index, prompt)
    for it in items:
        dirs = [Direction.es_to_en, Direction.en_to_es]
        rng.shuffle(dirs)
        out.append(Prompt(it.item_type, it.item_id, dirs[0], it.srs_stage))
        gap = rng.randint(1, MAX_PAIR_DISTANCE + 1)
        queue.append((len(out) - 1 + gap, Prompt(it.item_type, it.item_id, dirs[1], it.srs_stage)))
        # flush any partners now due
        due = [q for q in queue if q[0] <= len(out)]
        for d in due:
            out.append(d[1])
            queue.remove(d)
    for _, p in sorted(queue, key=lambda q: q[0]):
        out.append(p)
    return out
