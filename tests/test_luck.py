"""Tests for the skater's luck: condition of the week, strengths and
weaknesses, the landing roll, and the surprise key."""

import random

from skaterrpg.condition import condition_modifier, roll_condition
from skaterrpg.data_loader import load_catalog, load_rules, load_skater
from skaterrpg.engine import effective_consistency
from skaterrpg.minigame import (
    ElementTask,
    LiveKeyExecutor,
    landing_check,
    make_sequence,
    render_timer_line,
    surprise_key,
)
from skaterrpg.models import ElementType, Outcome

from test_minigame import FakeReader


def consistency_of(code, **changes):
    catalog, rules, skater = load_catalog(), load_rules(), load_skater()
    for name, value in changes.items():
        setattr(skater, name, value)
    program = skater.programs["short"]
    return effective_consistency(skater, [catalog[code]], program, 0, 7, rules)


# ---------------------------------------------------------------- condition


def test_condition_changes_consistency():
    great = consistency_of("3T", condition="Great")
    normal = consistency_of("3T", condition="Normal")
    bad = consistency_of("3T", condition="Bad")
    assert great > normal > bad


def test_tired_skaters_have_worse_weeks():
    rules = load_rules()

    def average(fatigue):
        skater = load_skater()
        skater.fatigue = fatigue
        rng = random.Random(1)
        return sum(condition_modifier(roll_condition(skater, rules, rng), rules) for _ in range(500)) / 500

    assert average(0) > average(90)


def test_roll_condition_stores_a_known_tier():
    rules, skater = load_rules(), load_skater()
    name = roll_condition(skater, rules, random.Random(3))
    assert skater.condition == name
    assert name in {t["name"] for t in rules.conditions}


# ---------------------------------------------------------------- strengths


def test_strengths_and_weaknesses_shift_consistency():
    # Same practised consistency (80) for both, only the strength/weakness lists differ.
    neutral = consistency_of("3F", consistency={"3F": 80}, strengths=[], weaknesses=[])
    strong = consistency_of("3F", consistency={"3F": 80}, strengths=["F"], weaknesses=[])
    weak = consistency_of("3F", consistency={"3F": 80}, strengths=[], weaknesses=["F"])
    assert strong > neutral > weak


# ---------------------------------------------------------------- landing roll


def test_perfect_consistency_never_slips():
    rng = random.Random(0)
    for _ in range(200):
        assert landing_check(Outcome.CLEAN, 100, ElementType.JUMP, 1.0, rng) == (Outcome.CLEAN, "")


def test_zero_consistency_always_slips_one_step():
    rng = random.Random(0)
    outcome, note = landing_check(Outcome.CLEAN, 0, ElementType.JUMP, 1.0, rng)
    assert outcome is Outcome.SHAKY and note
    assert landing_check(Outcome.UNDER_ROTATED, 0, ElementType.SPIN, 1.0, rng)[0] is Outcome.FALL


def test_a_fall_cannot_get_worse():
    assert landing_check(Outcome.FALL, 0, ElementType.JUMP, 1.0, random.Random(0)) == (Outcome.FALL, "")


def test_better_trained_elements_slip_less():
    def slips(consistency):
        rng = random.Random(5)
        return sum(landing_check(Outcome.CLEAN, consistency, ElementType.JUMP, 0.35, rng)[1] != "" for _ in range(2000))

    assert slips(90) < slips(50)


# ---------------------------------------------------------------- surprise key


def test_surprise_key_stays_in_its_group_and_changes():
    groups = [["Q", "W", "Z", "X"], ["P", "O", ".", ","]]
    seq = ["Q", "P", "W", "O"]
    for seed in range(30):
        new = surprise_key(seq, 2, groups, random.Random(seed))
        assert new in groups[0] and new not in ("W", "P", "O")


def test_live_surprise_changes_a_key_ahead():
    keys = {"jump": [["Q", "W", "Z", "X"], ["P", "O", ".", ","]]}
    original = make_sequence(5, keys["jump"], random.Random(0))
    clock, out = [0.0], []
    reader = FakeReader([" "] + original, clock, 0.3)  # type the keys as first shown
    executor = LiveKeyExecutor(keys, random.Random(0), reader, out.append, lambda: clock[0], surprise_chance={"jump": 1.0})
    attempt = executor.attempt(ElementTask(1, "3Lz", ElementType.JUMP, "jump", 5, 9.0, 70))
    screen = "".join(out)
    assert "change!" in screen
    assert attempt.outcome is Outcome.SHAKY  # the old key is now one mistake


def test_render_marks_the_changed_key():
    line = render_timer_line(["Q", "P", "W"], ["Q"], 3.0, 4.0, changed=2)
    assert "W!" in line and "change!" in line
