"""Score arithmetic, ISU-style but simplified.

Everything here is a pure function: same inputs, same output, no randomness.
That keeps the math easy to test (see tests/test_scoring.py).

    segment score = TES + PCS - deductions
    TES = sum over elements of (base value + GOE value)
    GOE value = GOE (-5..+5) x 10% x base value of the element
                (for a jump combination: of its highest-value jump)
    PCS = (Composition + Presentation + Skating Skills) x segment factor
"""

from __future__ import annotations

import math
from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable

from .models import Program, Skater


def round2(value: float) -> float:
    """Round to 2 decimals, halves away from zero (1.005 -> 1.01)."""
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


# ---------------------------------------------------------------- elements


def reduced_base_value(base_value: float, factor: float) -> float:
    """Base value after under-rotation or a fall, e.g. 3Lz 5.90 x 0.8 = 4.72."""
    return round2(base_value * factor)


def goe_value(goe: int, reference_base_value: float, goe_step: float = 0.10) -> float:
    """Points that a GOE adds or removes, e.g. +2 on 3Lz (5.90) = +1.18."""
    return round2(reference_base_value * goe * goe_step)


def element_score(base_values: list[float], goe: int, goe_step: float = 0.10) -> tuple[float, float, float]:
    """Score one element (a single element or a jump combination).

    Returns (total base value, GOE value, element score). In a combination the
    GOE is taken from the highest-value jump, as in the real system.
    """
    total_bv = round2(sum(base_values))
    gv = goe_value(goe, max(base_values), goe_step)
    return total_bv, gv, round2(total_bv + gv)


def total_element_score(scores: Iterable[float]) -> float:
    return round2(sum(scores))


# ---------------------------------------------------------------- deductions


def fall_deduction(falls: int, schedule: list[float]) -> float:
    """Points lost for falls. schedule[i] is the cost of fall number i+1;
    the last entry repeats (senior: -1, -1, -2, -2, then -3 each)."""
    if falls <= 0:
        return 0.0
    return round2(sum(schedule[min(i, len(schedule) - 1)] for i in range(falls)))


# ---------------------------------------------------------------- components


def component_mark(raw: float) -> float:
    """Clamp a raw 0-10 value to a judge's mark: 0.25 to 10 in 0.25 steps."""
    clamped = max(0.25, min(10.0, raw))
    return math.floor(clamped * 4 + 0.5) / 4  # nearest quarter, halves up


def program_components(skater: Skater, program: Program, falls: int) -> dict[str, float]:
    """The three components, each 0.25-10, from stats and the program.

    Composition    <- choreography quality and familiarity
    Presentation   <- artistry and composure, minus 0.5 per fall
    Skating Skills <- skating
    """
    composition = (program.choreo_quality * 0.6 + program.familiarity * 0.4) / 10
    presentation = (skater.stat("artistry") * 0.7 + skater.composure * 0.3) / 10 - 0.5 * falls
    skating_skills = skater.stat("skating") / 10 - 0.25 * falls
    return {
        "Composition": component_mark(composition),
        "Presentation": component_mark(presentation),
        "Skating Skills": component_mark(skating_skills),
    }


def program_component_score(components: dict[str, float], factor: float) -> float:
    """PCS = sum of the component marks x segment factor."""
    return round2(sum(components.values()) * factor)


# ---------------------------------------------------------------- segment


def segment_score(tes: float, pcs: float, deductions: float) -> float:
    return round2(tes + pcs - deductions)
