"""Plain data classes for the game. No game rules live here, only data shapes."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ElementType(str, Enum):
    JUMP = "jump"
    SPIN = "spin"
    STEP = "step"
    CHOREO = "choreo"


class Outcome(str, Enum):
    """How one element went. For spins and steps, UNDER_ROTATED means
    'messy, lost a level' because they cannot be under-rotated."""

    CLEAN = "clean"
    SHAKY = "shaky"
    UNDER_ROTATED = "under-rotated"
    FALL = "fall"


@dataclass(frozen=True)
class ElementDef:
    """One row of data/elements.csv, e.g. 3Lz or CCoSp4."""

    code: str
    name: str
    type: ElementType
    family: str  # "Lz" for jumps, "CCoSp" for spins, "StSq" for steps
    level: int | None  # None for jumps, 0 (= Base) to 4 for spins/steps
    base_value: float
    keys: int  # length of the key sequence in the mini-game
    stat: str  # skater stat that drives quality (jumping, spinning, ...)
    layout: str  # which key layout from rules.json, e.g. "jump_hard"

    @property
    def is_jump(self) -> bool:
        return self.type is ElementType.JUMP


@dataclass(frozen=True)
class Rules:
    """Tunable numbers from data/rules.json."""

    keys: dict[str, list[list[str]]]  # layout name -> key groups, see rules.json
    goe_step: float
    goe_min: int
    goe_max: int
    under_rotation_factor: float
    fall_base_factor: float
    fall_deductions: list[float]
    pcs_factor: dict[str, float]
    seconds_per_key: float
    reaction_seconds: float
    combo_consistency_factor: float
    luck_scale: float  # landing roll strength, see minigame.landing_check
    surprise_chance: dict[str, float]  # layout -> chance one key changes mid-element
    strength_bonus: int
    weakness_penalty: int
    conditions: list[dict]  # condition of the week tiers, best first
    program_rules: dict[str, dict]


@dataclass
class Program:
    segment: str  # "short" or "free"
    elements: list[str]  # planned element codes, combos joined by "+"
    choreo_quality: int = 50  # 0-100, who built the program
    familiarity: int = 50  # 0-100, how well the skater knows it


@dataclass
class Skater:
    name: str
    age: int
    club: str
    stats: dict[str, int]  # skating, jumping, spinning, footwork, artistry, stamina
    composure: int = 50  # "Nerves" in the design doc: higher = calmer
    fatigue: int = 0
    traits: list[str] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)  # element families, e.g. "Lz", "LSp"
    weaknesses: list[str] = field(default_factory=list)
    condition: str = "Normal"  # condition of the week, see condition.py
    consistency: dict[str, int] = field(default_factory=dict)  # element code -> %
    programs: dict[str, Program] = field(default_factory=dict)

    def stat(self, name: str) -> int:
        return self.stats.get(name, 0)


@dataclass(frozen=True)
class Event:
    id: str
    name: str
    level: str
    winning_total: float
    field_size: int


@dataclass
class ExecutedElement:
    """One line of the score sheet."""

    number: int
    planned: str  # what the program said, e.g. "3Lz+3T"
    executed: str  # what was called, e.g. "3Lz+3T<" or "CCoSp3"
    info: str  # "<" under-rotated, "F" fall, "" otherwise
    outcome: Outcome
    base_value: float
    goe: int
    goe_value: float
    score: float


@dataclass
class SegmentResult:
    skater_name: str
    segment: str
    elements: list[ExecutedElement]
    components: dict[str, float]  # component name -> mark (0.25-10)
    pcs_factor: float
    tes: float
    pcs: float
    deductions: dict[str, float]  # reason -> positive number to subtract
    total: float

    @property
    def falls(self) -> int:
        return sum(1 for e in self.elements if e.outcome is Outcome.FALL)
