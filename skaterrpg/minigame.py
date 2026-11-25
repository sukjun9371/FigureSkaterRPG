"""The key-sequence mini-game played for each element.

The game shows a random sequence such as  J K D F  and the player types it and
presses Enter before the timer runs out. Fewer mistakes and a faster answer
mean a better outcome:

    0 errors           -> clean (faster = higher GOE)
    1 error            -> shaky
    2 errors           -> under-rotated (jumps) / lost a level (spins, steps)
    3+ errors or late  -> fall

Each element uses a key layout (its "layout" column in elements.csv, keys
in rules.json): spins and steps use comfortable rows, jumps take turns between
the far left and far right of the keyboard, with wider reaches for harder
jumps. In a jump combination every jump is its own attempt.

The functions here are pure so they can be tested; KeyPressExecutor is the
small piece that actually talks to the keyboard.
"""

from __future__ import annotations

import random
import sys
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
    layout: str  # key layout name, e.g. "jump_hard"
    n_keys: int
    time_limit: float  # seconds
    consistency: float  # 0-100, effective chance to do it cleanly
    part: str = ""  # for combinations, e.g. "jump 1 of 2: 3Lz"
    code: str = ""  # this element or jump on its own, e.g. "3Lz"


@dataclass(frozen=True)
class Attempt:
    outcome: Outcome
    speed_ratio: float  # time used / time allowed (0-1, lower is faster)
    note: str = ""


# ---------------------------------------------------------------- pure helpers


def make_sequence(n_keys: int, groups: list[list[str]], rng: random.Random) -> list[str]:
    """Random keys, never the same key twice in a row (easier to read).

    With several key groups the sequence takes turns between them, starting
    from a random group: two groups on opposite sides of the keyboard make
    the hands jump back and forth (Q . W ; ...).
    """
    start = rng.randrange(len(groups))
    seq: list[str] = []
    for i in range(n_keys):
        group = groups[(start + i) % len(groups)]
        choices = [k for k in group if not seq or k != seq[-1]]
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


def outcome_for_errors(errors: int) -> Outcome:
    return {0: Outcome.CLEAN, 1: Outcome.SHAKY, 2: Outcome.UNDER_ROTATED}.get(errors, Outcome.FALL)


def errors_note(errors: int) -> str:
    return f"{errors} error{'s' if errors != 1 else ''}"


def judge(errors: int, elapsed: float, limit: float) -> Attempt:
    """Turn errors and time into an outcome."""
    if elapsed > limit:
        return Attempt(Outcome.FALL, 1.0, "too late")
    return Attempt(outcome_for_errors(errors), elapsed / limit, errors_note(errors))


# One step worse, and what the commentator says when the landing roll fails.
SLIP = {Outcome.CLEAN: Outcome.SHAKY, Outcome.SHAKY: Outcome.UNDER_ROTATED, Outcome.UNDER_ROTATED: Outcome.FALL}
SLIP_NOTES = {
    ElementType.JUMP: {
        Outcome.SHAKY: "she steps out of the landing",
        Outcome.UNDER_ROTATED: "the jump is short of rotation",
        Outcome.FALL: "she can't hold the landing and falls",
    },
    ElementType.SPIN: {
        Outcome.SHAKY: "the spin travels",
        Outcome.UNDER_ROTATED: "she loses a position and a level",
        Outcome.FALL: "she stumbles out of the spin",
    },
    ElementType.STEP: {
        Outcome.SHAKY: "a wobble on a turn",
        Outcome.UNDER_ROTATED: "she misses a turn and loses a level",
        Outcome.FALL: "she catches an edge and falls",
    },
}
SLIP_NOTES[ElementType.CHOREO] = SLIP_NOTES[ElementType.STEP]


def landing_check(outcome: Outcome, consistency: float, kind: ElementType, luck_scale: float, rng: random.Random) -> tuple[Outcome, str]:
    """The skater's own luck after the player has typed the element.

    Even perfect typing is not a guaranteed landing: with chance
    (100 - consistency)% x luck_scale the outcome slips one step. Consistency
    already holds her training, strengths/weaknesses and condition, so a
    well-trained element on a good week rarely slips. A fall cannot get worse.
    Returns (outcome, note); note is "" when nothing slipped.
    """
    if outcome not in SLIP or luck_scale <= 0:
        return outcome, ""
    if rng.random() >= (100 - consistency) / 100 * luck_scale:
        return outcome, ""
    worse = SLIP[outcome]
    return worse, SLIP_NOTES[kind][worse]


def surprise_key(seq: list[str], pos: int, groups: list[list[str]], rng: random.Random) -> str:
    """A different key for position `pos`, from the same key group (so a
    left-hand key stays left-hand) and not equal to its neighbours."""
    group = next((g for g in groups if seq[pos] in g), groups[0])
    neighbours = {seq[pos]} | ({seq[pos - 1]} if pos > 0 else set()) | ({seq[pos + 1]} if pos + 1 < len(seq) else set())
    choices = [k for k in group if k not in neighbours] or [k for k in group if k != seq[pos]]
    return rng.choice(choices) if choices else seq[pos]


# ---------------------------------------------------------------- executors
#
# An "executor" decides how an element went. The engine does not care which
# one it gets, so practice mode, auto-play and (later) a Pygame screen can all
# plug in here.


class KeyPressExecutor:
    """Play the element yourself in the terminal."""

    def __init__(
        self,
        keys: dict[str, list[list[str]]],
        rng: random.Random,
        input_fn: Callable[[str], str] = input,
        output_fn: Callable[[str], None] = print,
        clock: Callable[[], float] = time.monotonic,
        luck_scale: float = 0.0,
    ):
        self.keys = keys
        self.rng = rng
        self.input = input_fn
        self.output = output_fn
        self.clock = clock
        self.luck_scale = luck_scale

    def attempt(self, task: ElementTask) -> Attempt:
        seq = make_sequence(task.n_keys, self.keys[task.layout], self.rng)
        part = f"  -  {task.part}" if task.part else ""
        self.output(
            f"\n[{task.number}] {task.kind.value.upper()}  {task.label}{part}"
            f"   ({task.n_keys} keys, {task.time_limit:.1f}s, {task.consistency:.0f}% consistency)"
        )
        self.input("    Press Enter when ready...")
        self.output("    " + "  ".join(seq))
        start = self.clock()
        typed = self.input("    > ")
        elapsed = self.clock() - start
        result = judge(count_errors(seq, typed), elapsed, task.time_limit)
        self.output(f"    {result.outcome.value.upper()}  ({elapsed:.1f}s, {result.note})")
        outcome, slip = landing_check(result.outcome, task.consistency, task.kind, self.luck_scale, self.rng)
        if slip:
            self.output(f"    ...but {slip}!  -> {outcome.value.upper()}")
            result = Attempt(outcome, result.speed_ratio, f"{result.note}; {slip}")
        return result


GREEN, RED, YELLOW, MAGENTA = "\x1b[32m", "\x1b[31m", "\x1b[33m", "\x1b[35m"
BOLD, RESET = "\x1b[1m", "\x1b[0m"
CLEAR_LINE = "\r\x1b[K"  # back to the start of the line and wipe it


def render_keys(seq: list[str], typed: list[str], changed: int | None = None, active: bool = True) -> str:
    """Keys of one element or jump: typed keys green (right) or red (wrong),
    the next key bold in [brackets] when active, a surprise key magenta with "!"."""
    shown = []
    for i, key in enumerate(seq):
        if i < len(typed):
            shown.append((GREEN if typed[i] == key else RED) + key + RESET)
        elif i == changed:
            shown.append(MAGENTA + BOLD + ("[" + key + "!]" if active and i == len(typed) else key + "!") + RESET)
        elif active and i == len(typed):
            shown.append(BOLD + "[" + key + "]" + RESET)
        else:
            shown.append(key)
    return "  ".join(shown)


def render_timer_line(
    seq: list[str],
    typed: list[str],
    remaining: float,
    limit: float,
    width: int = 24,
    changed: int | None = None,
    before: str = "",
    after: str = "",
    tag_change: bool = True,
) -> str:
    """One line of the live mini-game, e.g.

        ██████████████░░░░░░░░░░  3.1s     Q  .  W  ;  Z

    The bar shrinks as time runs out (green, then yellow, then red). Keys
    already typed turn green if right and red if wrong; the next key is bold.
    A surprise key (position `changed`) shows in magenta with a "!" until typed.
    `before` and `after` hold the other jumps of a combination, so the whole
    combination sits on one line:

        ████████░░░░  6.0s     3Lz: 1  .  Q  /  Z + 3T: [P]  Z  P  W
    """
    fraction = max(0.0, min(1.0, remaining / limit)) if limit > 0 else 0.0
    filled = round(width * fraction)
    colour = GREEN if fraction > 0.5 else YELLOW if fraction > 0.25 else RED
    bar = colour + "█" * filled + RESET + "░" * (width - filled)
    line = f"    {bar} {max(0.0, remaining):4.1f}s     {before}{render_keys(seq, typed, changed)}{after}"
    if tag_change and changed is not None and changed >= len(typed):
        line += f"   {MAGENTA}{BOLD}<- change!{RESET}"
    return line


class LiveKeyExecutor:
    """Play the element yourself, one key at a time, with a live timer bar.

    No Enter needed: the element ends when you have typed as many keys as
    shown, or when time runs out (a fall). Backspace fixes a key but costs time.

    A jump combination is played as one element: one "ready", one timer bar
    holding the time of all its jumps, and all jumps on the same line. Time
    saved on the first jump carries over to the next. A fall ends it there.

    Surprise: with a chance per layout (rules.json "surprise_chance"), one key
    a little ahead of you changes while you type. Then the landing roll
    (landing_check) decides if the skater holds what you typed.
    """

    SEP = " + "

    def __init__(
        self,
        keys: dict[str, list[list[str]]],
        rng: random.Random,
        reader_factory: Callable | None = None,
        write: Callable[[str], None] | None = None,
        clock: Callable[[], float] = time.monotonic,
        tick: float = 0.05,
        luck_scale: float = 0.0,
        surprise_chance: dict[str, float] | None = None,
    ):
        if reader_factory is None:
            from .terminal import KeyReader, enable_ansi

            enable_ansi()
            reader_factory = KeyReader
        self.keys = keys
        self.rng = rng
        self.reader_factory = reader_factory
        self.write = write or self._stdout_write
        self.clock = clock
        self.tick = tick
        self.luck_scale = luck_scale
        self.surprise_chance = surprise_chance or {}

    @staticmethod
    def _stdout_write(text: str) -> None:
        sys.stdout.write(text)
        sys.stdout.flush()

    # -- the two entry points the engine calls

    def attempt(self, task: ElementTask) -> Attempt:
        return self._perform([task])[0]

    def attempt_combination(self, tasks: list[ElementTask]) -> list[Attempt]:
        """All jumps of a combination on one line. Stops after a fall, so it
        can return fewer attempts than jumps."""
        return self._perform(tasks)

    # -- the work

    def _perform(self, tasks: list[ElementTask]) -> list[Attempt]:
        combo = len(tasks) > 1
        first = tasks[0]
        seqs = [make_sequence(t.n_keys, self.keys[t.layout], self.rng) for t in tasks]
        triggers = [self._surprise_trigger(t, len(seq)) for t, seq in zip(tasks, seqs)]
        total = sum(t.time_limit for t in tasks)
        labels = [f"{t.code}: " if combo else "" for t in tasks]
        width = 12 if combo else 24

        n_keys = "+".join(str(t.n_keys) for t in tasks)
        consistency = "/".join(f"{t.consistency:.0f}" for t in tasks)
        self.write(
            f"\n[{first.number}] {BOLD}{first.kind.value.upper()}{RESET}  {first.label}"
            f"   ({n_keys} keys, {total:.1f}s, {consistency}% consistency)\n"
        )

        done: list[str] = []  # finished jumps, drawn
        typed_results: list[Attempt] = []  # what the typing earned
        results: list[Attempt] = []  # after the landing roll
        slips: list[tuple[ElementTask, Outcome, str]] = []
        with self.reader_factory() as reader:
            self.write("    Press Space or Enter when ready...")
            while reader.read(None) not in (" ", "\r", "\n"):
                pass
            start = self.clock()
            deadline = start + total
            for j, (task, seq) in enumerate(zip(tasks, seqs)):
                before = "".join(d + self.SEP for d in done) + labels[j]
                after = "".join(self.SEP + labels[k] + "  ".join(seqs[k]) for k in range(j + 1, len(tasks)))
                jump_start = self.clock()
                typed, changed, timed_out = self._type(reader, seq, triggers[j], task, deadline, total, width, before, after, not combo)
                used = self.clock() - jump_start
                if timed_out:
                    result = Attempt(Outcome.FALL, 1.0, "time ran out")
                else:
                    errors = count_errors(seq, "".join(typed))
                    result = Attempt(outcome_for_errors(errors), min(1.0, used / task.time_limit), errors_note(errors))
                typed_results.append(result)
                outcome, slip = landing_check(result.outcome, task.consistency, task.kind, self.luck_scale, self.rng)
                if slip:
                    slips.append((task, outcome, slip))
                    result = Attempt(outcome, result.speed_ratio, f"{result.note}; {slip}")
                results.append(result)
                done.append(labels[j] + render_keys(seq, typed, changed, active=False))
                if result.outcome is Outcome.FALL:
                    break
            elapsed = self.clock() - start

        not_done = "".join(self.SEP + labels[k] + "(not done)" for k in range(len(results), len(tasks)))
        line = render_timer_line([], [], total - elapsed, total, width, before=self.SEP.join(done), after=not_done)
        self.write(CLEAR_LINE + line + "\n")
        if combo:
            summary = self.SEP.join(f"{t.code} {self._coloured(r.outcome)} ({r.note})" for t, r in zip(tasks, typed_results))
            self.write(f"    {summary}   {elapsed:.1f}s\n")
        else:
            self.write(f"    {self._coloured(typed_results[0].outcome)}  ({elapsed:.1f}s, {typed_results[0].note})\n")
        for task, outcome, slip in slips:
            where = f"on the {task.code} " if combo else ""
            self.write(f"    ...but {where}{slip}!  -> {self._coloured(outcome)}\n")
        if combo and len(results) < len(tasks):
            self.write(f"    The fall ends the combination.\n")
        return results

    def _surprise_trigger(self, task: ElementTask, n: int) -> int | None:
        """How many keys in the surprise happens (None = no surprise)."""
        if n >= 3 and self.rng.random() < self.surprise_chance.get(task.layout, 0.0):
            return self.rng.randint(1, n - 2)
        return None

    def _type(self, reader, seq, trigger, task, deadline, total, width, before, after, tag_change):
        """Read keys for one sequence. Returns (typed, changed position, timed out)."""
        typed: list[str] = []
        changed: int | None = None
        while len(typed) < len(seq):
            remaining = deadline - self.clock()
            if remaining <= 0:
                return typed, changed, True
            if trigger is not None and changed is None and len(typed) >= trigger:
                # The key after the next one changes, so you can see it coming.
                changed = min(trigger + 1, len(seq) - 1)
                seq[changed] = surprise_key(seq, changed, self.keys[task.layout], self.rng)
            line = render_timer_line(seq, typed, remaining, total, width, changed, before, after, tag_change)
            self.write(CLEAR_LINE + line)
            key = reader.read(min(self.tick, remaining))
            if key in ("\x7f", "\x08"):  # Backspace
                if typed:
                    typed.pop()
            elif key and key.strip():
                typed.append(key.upper())
        return typed, changed, False

    @staticmethod
    def _coloured(outcome: Outcome) -> str:
        colour = {Outcome.CLEAN: GREEN, Outcome.FALL: RED}.get(outcome, YELLOW)
        return f"{colour}{BOLD}{outcome.value.upper()}{RESET}"


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
