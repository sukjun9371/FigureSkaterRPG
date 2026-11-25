"""Checks that a program follows the (simplified) senior layout rules."""

from __future__ import annotations

from collections import Counter

from .engine import parse_element
from .models import ElementDef, ElementType, Program, Rules


def validate_program(program: Program, catalog: dict[str, ElementDef], rules: Rules) -> list[str]:
    """Return a list of problems; an empty list means the program is legal."""
    spec = rules.program_rules[program.segment]
    problems: list[str] = []
    counts: Counter[ElementType] = Counter()
    combos = 0
    jump_uses: Counter[str] = Counter()
    has_axel = False

    for code in program.elements:
        try:
            parts = parse_element(code, catalog)
        except ValueError as err:
            problems.append(str(err))
            continue
        counts[parts[0].type] += 1
        if parts[0].is_jump:
            if len(parts) > 1:
                combos += 1
            for p in parts:
                jump_uses[p.code] += 1
                if p.family == "A":
                    has_axel = True

    expected = {
        ElementType.JUMP: spec["jumps"],
        ElementType.SPIN: spec["spins"],
        ElementType.STEP: spec["steps"],
        ElementType.CHOREO: spec["choreo"],
    }
    for kind, want in expected.items():
        if counts[kind] != want:
            problems.append(f"{program.segment} program needs {want} {kind.value} element(s), has {counts[kind]}")
    if combos > spec["max_combos"]:
        problems.append(f"At most {spec['max_combos']} jump combination(s) allowed, has {combos}")
    if spec.get("needs_axel") and not has_axel:
        problems.append("Short program needs an Axel jump")
    max_repeats = spec.get("max_repeats")
    if max_repeats:
        for code, uses in jump_uses.items():
            if uses > max_repeats:
                problems.append(f"{code} is used {uses} times (max {max_repeats})")
    return problems
