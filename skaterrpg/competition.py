"""A competition: the player's skater against a generated field.

Opponents are not simulated element by element; each gets a short and a free
score drawn around the event's typical winning total (see data/events.json).
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from .engine import Executor, perform_program
from .models import ElementDef, Event, Rules, SegmentResult, Skater

SHORT_SHARE = 0.35  # roughly how much of a total comes from the short program


@dataclass
class Entry:
    name: str
    club: str
    short: float | None = None
    free: float | None = None
    is_player: bool = False

    @property
    def total(self) -> float:
        return round((self.short or 0) + (self.free or 0), 2)


def generate_field(event: Event, names: dict[str, list[str]], rng: random.Random) -> list[Entry]:
    """field_size - 1 opponents with pre-rolled segment scores."""
    entries = []
    used: set[str] = set()
    winner_total = event.winning_total * rng.uniform(0.95, 1.05)
    for i in range(event.field_size - 1):
        while True:
            name = f"{rng.choice(names['first'])} {rng.choice(names['last'])}"
            if name not in used:
                used.add(name)
                break
        total = winner_total if i == 0 else winner_total * rng.uniform(0.55, 0.98)
        short_part = total * rng.uniform(SHORT_SHARE - 0.03, SHORT_SHARE + 0.03)
        entries.append(Entry(name, rng.choice(names["clubs"]), round(short_part, 2), round(total - short_part, 2)))
    return entries


class Competition:
    def __init__(
        self,
        event: Event,
        skater: Skater,
        catalog: dict[str, ElementDef],
        rules: Rules,
        executor: Executor,
        names: dict[str, list[str]],
        rng: random.Random,
    ):
        self.event = event
        self.skater = skater
        self.catalog = catalog
        self.rules = rules
        self.executor = executor
        self.rng = rng
        self.player = Entry(skater.name, skater.club, is_player=True)
        self.entries = generate_field(event, names, rng) + [self.player]
        self.results: dict[str, SegmentResult] = {}

    def skate(self, segment: str) -> SegmentResult:
        result = perform_program(
            self.skater, self.skater.programs[segment], self.catalog, self.rules, self.executor, self.rng
        )
        self.results[segment] = result
        setattr(self.player, segment, result.total)
        return result

    def standings(self, after: str) -> list[Entry]:
        """Ranking after 'short' (by short score) or 'free' (by total)."""
        if after == "short":
            return sorted(self.entries, key=lambda e: e.short or 0, reverse=True)
        return sorted(self.entries, key=lambda e: e.total, reverse=True)
