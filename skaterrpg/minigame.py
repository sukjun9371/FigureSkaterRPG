"""The key-sequence mini-game played for each element.

The game shows a random sequence such as  J K D F  and the player types it and
presses Enter before the timer runs out. Fewer mistakes and a faster answer
mean a better outcome:

    0 errors           -> clean (faster = higher GOE)
    1 error            -> shaky
    2 errors           -> under-rotated (jumps) / lost a level (spins, steps)
    3+ errors or late  -> fall

The functions here are pure so they can be tested; KeyPressExecutor is the
small piece that actually talks to the keyboard.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Callable

from .models import ElementType, Outcome, Rules


@dataclass(frozen=True)
class ElementTask:
    """Everything an executor needs to attempt one element."""

    number: int
    label: str  # "3Lz+3T"
    kind: ElementType
    n_keys: int
    time_limit: float  # seconds
    consistency: float  # 0-100, effective chance to do it cleanly


@dataclass(frozen=True)
class Attempt:
    outcome: Outcome
    speed_ratio: float  # time used / time allowed (0-1, lower is faster)
    note: str = ""


# ---------------------------------------------------------------- pure helpers


def make_sequence(n_keys: int, keyset: list[str], rng: random.Random) -> list[str]:
    """Random keys, never the same key twice in a row (easier to read)."""
    seq: list[str] = []
    for _ in range(n_keys):
        choices = [k for k in keyset if not seq or k != seq[-1]]
        seq.append(rng.choice(choices))
    return seq


def time_limit(n_keys: int, consistency: float, composure: float, rules: Rules) -> float:
    """Seconds allowed. A skater who knows the element well, and stays calm,
    gets more time (the element "feels slower" to them)."""
    skill = 0.6 + 0.6 * (consistency / 100) + 0.2 * (composure / 100)  # 0.6 .. 1.4
    return round(rules.reaction_seconds + n_keys * rules.seconds_per_key * skill, 1)


def normalise(text: str) -> str:
    return "".join(text.split()).upper()


def count_errors(target: list[str], typed: str) -> int:
    """Edit distance between the target keys and what was typed.

    A missed, extra or wrong key each count as one error, so one slip early on
    does not make every later key wrong.
    """
    a, b = "".join(target).upper(), normalise(typed)
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        current = [i]
        for j, cb in enumerate(b, start=1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb)))
        previous = current
    return previous[-1]


def judge(errors: int, elapsed: float, limit: float) -> Attempt:
    """Turn errors and time into an outcome."""
    if elapsed > limit:
        return Attempt(Outcome.FALL, 1.0, "too late")
    outcome = {0: Outcome.CLEAN, 1: Outcome.SHAKY, 2: Outcome.UNDER_ROTATED}.get(errors, Outcome.FALL)
    return Attempt(outcome, elapsed / limit, f"{errors} error{'s' if errors != 1 else ''}")


# ---------------------------------------------------------------- executors
#
# An "executor" decides how an element went. The engine does not care which
# one it gets, so practice mode, auto-play and (later) a Pygame screen can all
# plug in here.


class KeyPressExecutor:
    """Play the element yourself in the terminal."""

    def __init__(
        self,
        keyset: list[str],
        rng: random.Random,
        input_fn: Callable[[str], str] = input,
        output_fn: Callable[[str], None] = print,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.keyset = keyset
        self.rng = rng
        self.input = input_fn
        self.output = output_fn
        self.clock = clock

    def attempt(self, task: ElementTask) -> Attempt:
        seq = make_sequence(task.n_keys, self.keyset, self.rng)
        self.output(f"\n[{task.number}] {task.label}   ({task.n_keys} keys, {task.time_limit:.1f}s)")
        self.input("    Press Enter when ready...")
        self.output("    " + "  ".join(seq))
        start = self.clock()
        typed = self.input("    > ")
        elapsed = self.clock() - start
        result = judge(count_errors(seq, typed), elapsed, task.time_limit)
        self.output(f"    {result.outcome.value.upper()}  ({elapsed:.1f}s, {result.note})")
        return result


class AutoExecutor:
    """Dice roll from the skater's consistency: no typing needed."""

    def __init__(self, rng: random.Random):
        self.rng = rng

    def attempt(self, task: ElementTask) -> Attempt:
        p_clean = task.consistency / 100
        roll = self.rng.random()
        miss = 1 - p_clean
        if roll < p_clean:
            outcome = Outcome.CLEAN
        elif roll < p_clean + miss * 0.45:
            outcome = Outcome.SHAKY
        elif roll < p_clean + miss * 0.70:
            outcome = Outcome.UNDER_ROTATED
        else:
            outcome = Outcome.FALL
        return Attempt(outcome, self.rng.uniform(0.35, 0.9), "auto")
