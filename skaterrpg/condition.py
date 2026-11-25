"""Condition of the week: how the skater feels going into an event.

Rolled once per week (for now, once per competition). Tiers and their
consistency modifiers live in data/rules.json ("conditions"). A tired skater
is more likely to have a bad week, a calm one a good week.
"""

from __future__ import annotations

import random

from .models import Rules, Skater


def roll_condition(skater: Skater, rules: Rules, rng: random.Random) -> str:
    """Pick this week's condition and store it on the skater. Returns its name."""
    roll = rng.randint(1, 100) - skater.fatigue / 2 + (skater.composure - 50) / 5
    for tier in rules.conditions:  # best first
        if roll >= tier["min"]:
            skater.condition = tier["name"]
            return tier["name"]
    skater.condition = rules.conditions[-1]["name"]
    return skater.condition


def condition_modifier(name: str, rules: Rules) -> int:
    """Consistency points added (or taken away) by a condition."""
    for tier in rules.conditions:
        if tier["name"] == name:
            return tier["modifier"]
    return 0
