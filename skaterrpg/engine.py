"""The performance engine: skate a whole program and get a scored result.

    perform_program(skater, program, ...) -> SegmentResult

It is the single entry point for skating a program. Competitions call it
today; practice runs can call it later with the same arguments and simply
use the result to grow consistency instead of to rank skaters.

For each planned element:
  1. look up its data (base value, key count) in the element catalog
  2. work out the skater's effective consistency right now
  3. ask the executor (key mini-game or dice) how it went -> Outcome
  4. turn the outcome into an executed element with base value and GOE
Then add components and deductions.
"""

from __future__ import annotations

import random
from typing import Callable, Protocol

from . import scoring
from .minigame import Attempt, ElementTask, time_limit
from .models import ElementDef, ExecutedElement, Outcome, Program, Rules, SegmentResult, Skater


class Executor(Protocol):
    def attempt(self, task: ElementTask) -> Attempt: ...


# ---------------------------------------------------------------- lookups


def parse_element(code: str, catalog: dict[str, ElementDef]) -> list[ElementDef]:
    """'3Lz+3T' -> [3Lz, 3T]. Raises ValueError for unknown codes."""
    parts = []
    for part in code.split("+"):
        if part not in catalog:
            raise ValueError(f"Unknown element '{part}' in '{code}'. Add it to data/elements.csv.")
        parts.append(catalog[part])
    return parts


def level_down(defn: ElementDef, catalog: dict[str, ElementDef]) -> ElementDef:
    """CCoSp4 -> CCoSp3, StSq1 -> StSqB. Unchanged if already base or no levels."""
    if defn.level is None or defn.level == 0:
        return defn
    for other in catalog.values():
        if other.family == defn.family and other.level == defn.level - 1:
            return other
    return defn


# ---------------------------------------------------------------- difficulty


def effective_consistency(
    skater: Skater,
    parts: list[ElementDef],
    program: Program,
    position: int,
    n_elements: int,
    rules: Rules,
) -> float:
    """Chance (0-100) to do this element cleanly right now.

    Starts from the skater's practised consistency (a combination uses its
    weakest jump), then: low familiarity, fatigue and poor composure lower it,
    and in the second half of the free program low stamina lowers it too.
    """
    base = min(skater.consistency.get(p.code, 0) for p in parts)
    if len(parts) > 1:
        base *= rules.combo_consistency_factor
    value = base * (0.75 + 0.25 * program.familiarity / 100)
    value -= skater.fatigue * 0.1
    value -= (50 - skater.composure) * 0.1
    if program.segment == "free" and position >= n_elements / 2:
        value -= (100 - skater.stat("stamina")) * 0.15
    return max(5.0, min(99.0, value))


def key_count(parts: list[ElementDef]) -> int:
    """Hardest jump sets the length; each extra jump in a combo adds one key."""
    return max(p.keys for p in parts) + len(parts) - 1


# ---------------------------------------------------------------- GOE


def decide_goe(outcome: Outcome, quality: float, speed_ratio: float, skater: Skater, rules: Rules, rng: random.Random) -> int:
    """GOE from the outcome, skater quality (0-100) and how fast the keys were typed."""
    if outcome is Outcome.FALL:
        return rules.goe_min
    if outcome is Outcome.UNDER_ROTATED:
        goe = -rng.randint(2, 4)
    elif outcome is Outcome.SHAKY:
        goe = -rng.randint(1, 3)
    else:  # clean
        goe = round((quality - 40) / 12)
        if speed_ratio < 0.5:
            goe += 1
        goe += rng.choice([-1, 0, 0, 1])
        if "Perfectionist" in skater.traits:
            goe += 1
        goe = max(0, goe)
    return max(rules.goe_min, min(rules.goe_max, goe))


# ---------------------------------------------------------------- one element


def score_element(
    number: int,
    planned: str,
    parts: list[ElementDef],
    attempt: Attempt,
    skater: Skater,
    catalog: dict[str, ElementDef],
    rules: Rules,
    rng: random.Random,
) -> ExecutedElement:
    outcome = attempt.outcome
    info = "F" if outcome is Outcome.FALL else ""

    if parts[0].is_jump:
        # An error happens on the last jump of a combination.
        base_values = [p.base_value for p in parts]
        marks = [""] * len(parts)
        if outcome in (Outcome.UNDER_ROTATED, Outcome.FALL):
            factor = rules.under_rotation_factor if outcome is Outcome.UNDER_ROTATED else rules.fall_base_factor
            base_values[-1] = scoring.reduced_base_value(base_values[-1], factor)
            marks[-1] = "<"
            info = ("< " + info).strip()
        executed = "+".join(p.code + m for p, m in zip(parts, marks))
    else:
        defn = parts[0]
        if outcome in (Outcome.UNDER_ROTATED, Outcome.FALL):
            defn = level_down(defn, catalog)
        base_values = [defn.base_value]
        executed = defn.code

    quality = (skater.stat(parts[0].stat) + skater.stat("artistry")) / 2
    goe = decide_goe(outcome, quality, attempt.speed_ratio, skater, rules, rng)
    bv, gv, score = scoring.element_score(base_values, goe, rules.goe_step)
    return ExecutedElement(number, planned, executed, info, outcome, bv, goe, gv, score)


# ---------------------------------------------------------------- whole program


def perform_program(
    skater: Skater,
    program: Program,
    catalog: dict[str, ElementDef],
    rules: Rules,
    executor: Executor,
    rng: random.Random,
    on_element: Callable[[ExecutedElement], None] | None = None,
) -> SegmentResult:
    """Skate every element of the program and return the scored segment."""
    elements: list[ExecutedElement] = []
    n = len(program.elements)
    for i, planned in enumerate(program.elements):
        parts = parse_element(planned, catalog)
        consistency = effective_consistency(skater, parts, program, i, n, rules)
        n_keys = key_count(parts)
        task = ElementTask(
            number=i + 1,
            label=planned,
            kind=parts[0].type,
            n_keys=n_keys,
            time_limit=time_limit(n_keys, consistency, skater.composure, rules),
            consistency=consistency,
        )
        attempt = executor.attempt(task)
        executed = score_element(i + 1, planned, parts, attempt, skater, catalog, rules, rng)
        elements.append(executed)
        if on_element:
            on_element(executed)

    falls = sum(1 for e in elements if e.outcome is Outcome.FALL)
    components = scoring.program_components(skater, program, falls)
    factor = rules.pcs_factor[program.segment]
    tes = scoring.total_element_score(e.score for e in elements)
    pcs = scoring.program_component_score(components, factor)
    deductions = {}
    if falls:
        deductions[f"Falls ({falls})"] = scoring.fall_deduction(falls, rules.fall_deductions)
    total = scoring.segment_score(tes, pcs, sum(deductions.values()))
    return SegmentResult(skater.name, program.segment, elements, components, factor, tes, pcs, deductions, total)
