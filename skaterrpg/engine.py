"""The performance engine: skate a whole program and get a scored result.

    perform_program(skater, program, ...) -> SegmentResult

It is the single entry point for skating a program. Competitions call it
today; practice runs can call it later with the same arguments and simply
use the result to grow consistency instead of to rank skaters.

For each planned element:
  1. look up its data (base value, key count) in the element catalog
  2. work out the skater's effective consistency right now
  3. ask the executor (key mini-game or dice) how it went -> Outcome.
     A jump combination is one attempt per jump, and a fall ends it:
     the jumps after the fall are never done and score nothing.
  4. turn the outcomes into an executed element with base value and GOE
Then add components and deductions.
"""

from __future__ import annotations

import random
from typing import Callable, Protocol

from . import scoring
from .condition import condition_modifier
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
    after_jump: bool = False,
) -> float:
    """Chance (0-100) to do this element cleanly right now.

    Starts from the skater's practised consistency, then: low familiarity,
    fatigue and poor composure lower it, and in the second half of the free
    program low stamina lowers it too. A jump done straight after another
    jump in a combination (after_jump) is a little harder.
    Her strengths and weaknesses, and her condition this week, shift it.
    """
    base = min(skater.consistency.get(p.code, 0) for p in parts)
    if after_jump:
        base *= rules.combo_consistency_factor
    value = base * (0.75 + 0.25 * program.familiarity / 100)
    if any(p.family in skater.strengths for p in parts):
        value += rules.strength_bonus
    if any(p.family in skater.weaknesses for p in parts):
        value -= rules.weakness_penalty
    value += condition_modifier(skater.condition, rules)
    value -= skater.fatigue * 0.1
    value -= (50 - skater.composure) * 0.1
    if program.segment == "free" and position >= n_elements / 2:
        value -= (100 - skater.stat("stamina")) * 0.15
    return max(5.0, min(99.0, value))


# ---------------------------------------------------------------- GOE


def speed_term(speed_ratio: float) -> float:
    """+1 for typing in 10% of the time allowed, 0 at half, -1 at 90%."""
    return (0.5 - speed_ratio) * 2.5


def decide_goe(
    outcome: Outcome,
    quality: float,
    speed_ratio: float,
    consistency: float,
    skater: Skater,
    rules: Rules,
    rng: random.Random,
) -> int:
    """GOE (-5..+5) for one element.

    Clean elements build their GOE from:
      effective consistency  training, strengths/weaknesses, condition of the week
                             (50% -> 0, 80% -> +2, 95% -> +3)
      typing speed           fast and confident looks better (up to about +-2)
      quality                the skater's stat for the element and artistry
      small judge variation  -1, 0 or +1, mostly 0
    A clean element never goes below 0. Shaky and under-rotated elements
    start at -2 and -3 and typing speed moves them one step either way.
    A fall is always -5.
    """
    if outcome is Outcome.FALL:
        return rules.goe_min
    if outcome is Outcome.UNDER_ROTATED:
        goe = max(-4, min(-2, -3 + round(speed_term(speed_ratio))))
    elif outcome is Outcome.SHAKY:
        goe = max(-3, min(-1, -2 + round(speed_term(speed_ratio))))
    else:  # clean
        raw = (consistency - 50) / 15 + speed_term(speed_ratio) * 1.6 + (quality - 60) / 20
        if "Perfectionist" in skater.traits:
            raw += 1
        raw += rng.choice([-1, 0, 0, 0, 1])
        goe = max(0, round(raw))
    return max(rules.goe_min, min(rules.goe_max, goe))


# ---------------------------------------------------------------- one element

# Worst outcome last: the element as a whole counts as its worst jump.
OUTCOME_ORDER = [Outcome.CLEAN, Outcome.SHAKY, Outcome.UNDER_ROTATED, Outcome.FALL]


def attempt_element(
    number: int,
    planned: str,
    parts: list[ElementDef],
    skater: Skater,
    program: Program,
    position: int,
    n_elements: int,
    rules: Rules,
    executor: Executor,
) -> tuple[list[ElementTask], list[Attempt]]:
    """Ask the executor how the element went. Returns (tasks, attempts).

    A single element is one attempt. A jump combination is one attempt per
    jump; after a fall the combination is over, so fewer attempts come back
    than there are jumps. Executors that can show a whole combination at once
    (the live timer) get every jump in one attempt_combination() call, so it
    feels like one element; others get the jumps one by one.
    """
    tasks = []
    for j, part in enumerate(parts):
        consistency = effective_consistency(skater, [part], program, position, n_elements, rules, after_jump=j > 0)
        tasks.append(
            ElementTask(
                number=number,
                label=planned,
                kind=part.type,
                layout=part.layout,
                n_keys=part.keys,
                time_limit=time_limit(part.keys, consistency, skater.composure, rules),
                consistency=consistency,
                part=f"jump {j + 1} of {len(parts)}: {part.code}" if len(parts) > 1 else "",
                code=part.code,
            )
        )
    if len(tasks) > 1 and hasattr(executor, "attempt_combination"):
        return tasks, executor.attempt_combination(tasks)
    attempts: list[Attempt] = []
    for task in tasks:
        attempt = executor.attempt(task)
        attempts.append(attempt)
        if attempt.outcome is Outcome.FALL:
            break
    return tasks, attempts


def score_element(
    number: int,
    planned: str,
    parts: list[ElementDef],
    attempts: list[Attempt],
    consistency: float,
    skater: Skater,
    catalog: dict[str, ElementDef],
    rules: Rules,
    rng: random.Random,
) -> ExecutedElement:
    """Turn the attempts into a score sheet line.

    In a combination each jump keeps its own mark: an under-rotated or fallen
    jump gets "<" and loses base value. Jumps never reached after a fall are
    left out. GOE follows the worst jump.
    """
    outcome = max((a.outcome for a in attempts), key=OUTCOME_ORDER.index)
    speed_ratio = sum(a.speed_ratio for a in attempts) / len(attempts)
    info = "F" if outcome is Outcome.FALL else ""

    if parts[0].is_jump:
        base_values, codes = [], []
        for part, attempt in zip(parts, attempts):
            bv, mark = part.base_value, ""
            if attempt.outcome is Outcome.UNDER_ROTATED:
                bv, mark = scoring.reduced_base_value(bv, rules.under_rotation_factor), "<"
            elif attempt.outcome is Outcome.FALL:
                bv, mark = scoring.reduced_base_value(bv, rules.fall_base_factor), "<"
            base_values.append(bv)
            codes.append(part.code + mark)
        if "<" in "".join(codes):
            info = ("< " + info).strip()
        executed = "+".join(codes)
    else:
        defn = parts[0]
        if outcome in (Outcome.UNDER_ROTATED, Outcome.FALL):
            defn = level_down(defn, catalog)
        base_values = [defn.base_value]
        executed = defn.code

    quality = (skater.stat(parts[0].stat) + skater.stat("artistry")) / 2
    goe = decide_goe(outcome, quality, speed_ratio, consistency, skater, rules, rng)
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
        tasks, attempts = attempt_element(i + 1, planned, parts, skater, program, i, n, rules, executor)
        consistency = min(t.consistency for t in tasks[: len(attempts)])  # of the jumps actually done
        executed = score_element(i + 1, planned, parts, attempts, consistency, skater, catalog, rules, rng)
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
