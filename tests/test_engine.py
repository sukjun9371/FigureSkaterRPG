"""End-to-end checks of the performance engine with a fixed executor."""

import random

from skaterrpg.data_loader import load_catalog, load_rules, load_skater
from skaterrpg.engine import level_down, perform_program
from skaterrpg.minigame import Attempt
from skaterrpg.models import Outcome, Program
from skaterrpg.programs import validate_program


class Always:
    """Executor that returns the same outcome every time."""

    def __init__(self, outcome):
        self.outcome = outcome

    def attempt(self, task):
        return Attempt(self.outcome, 0.6)


class Scripted:
    """Executor that plays back a list of outcomes and records the tasks."""

    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.tasks = []

    def attempt(self, task):
        self.tasks.append(task)
        return Attempt(self.outcomes.pop(0), 0.6)


def skate_one(planned, executor):
    """Skate a one-element program and return its score sheet line."""
    catalog, rules, skater = load_catalog(), load_rules(), load_skater()
    program = Program("free", [planned])
    return perform_program(skater, program, catalog, rules, executor, random.Random(0)).elements[0]


def test_sample_programs_are_legal():
    catalog, rules, skater = load_catalog(), load_rules(), load_skater()
    for program in skater.programs.values():
        assert validate_program(program, catalog, rules) == []


def test_illegal_short_program_is_reported():
    catalog, rules, skater = load_catalog(), load_rules(), load_skater()
    program = skater.programs["short"]
    program.elements = ["3F", "3Lz", "3Lz+3T", "FCSp4", "LSp4", "StSq3"]
    problems = validate_program(program, catalog, rules)
    assert any("Axel" in p for p in problems)
    assert any("spin" in p for p in problems)


def test_all_falls_short_program():
    catalog, rules, skater = load_catalog(), load_rules(), load_skater()
    result = perform_program(skater, skater.programs["short"], catalog, rules, Always(Outcome.FALL), random.Random(0))
    assert result.falls == 7
    assert result.deductions == {"Falls (7)": 15.0}  # 1+1+2+2+3+3+3
    assert all(e.goe == -5 for e in result.elements)
    combo = result.elements[2]
    assert combo.executed == "3Lz<"  # fell on the 3Lz, so the 3T never happened
    assert combo.base_value == 4.72
    spin = result.elements[3]
    assert spin.executed == "FCSp3"  # a fall on a spin costs a level
    assert result.total == round(result.tes + result.pcs - 15.0, 2)


def test_clean_skate_scores_more_than_falls():
    catalog, rules, skater = load_catalog(), load_rules(), load_skater()
    clean = perform_program(skater, skater.programs["free"], catalog, rules, Always(Outcome.CLEAN), random.Random(0))
    falls = perform_program(skater, skater.programs["free"], catalog, rules, Always(Outcome.FALL), random.Random(0))
    assert clean.total > falls.total
    assert all(e.goe >= 0 for e in clean.elements)
    assert not clean.deductions


def test_level_down():
    catalog = load_catalog()
    assert level_down(catalog["CCoSp4"], catalog).code == "CCoSp3"
    assert level_down(catalog["StSq1"], catalog).code == "StSqB"
    assert level_down(catalog["StSqB"], catalog).code == "StSqB"
    assert level_down(catalog["3Lz"], catalog).code == "3Lz"


def test_combination_is_one_attempt_per_jump():
    executor = Scripted(Outcome.CLEAN, Outcome.CLEAN, Outcome.CLEAN)
    element = skate_one("3S+2T+2Lo", executor)
    assert [t.part for t in executor.tasks] == ["jump 1 of 3: 3S", "jump 2 of 3: 2T", "jump 3 of 3: 2Lo"]
    assert [t.n_keys for t in executor.tasks] == [4, 3, 3]
    assert element.executed == "3S+2T+2Lo"
    assert element.base_value == 7.30


def test_fall_on_first_jump_ends_the_combination():
    executor = Scripted(Outcome.FALL)
    element = skate_one("3Lz+3T", executor)
    assert len(executor.tasks) == 1  # the 3T is never attempted
    assert element.executed == "3Lz<"
    assert element.info == "< F"
    assert element.base_value == 4.72
    assert element.goe == -5


def test_fall_on_second_jump_keeps_the_first():
    element = skate_one("3Lz+3T", Scripted(Outcome.CLEAN, Outcome.FALL))
    assert element.executed == "3Lz+3T<"
    assert element.base_value == 5.90 + 3.36


def test_each_jump_keeps_its_own_mark():
    element = skate_one("3Lz+3T", Scripted(Outcome.UNDER_ROTATED, Outcome.CLEAN))
    assert element.executed == "3Lz<+3T"
    assert element.info == "<"
    assert element.outcome is Outcome.UNDER_ROTATED  # GOE follows the worst jump
    assert -4 <= element.goe <= -2


def test_second_jump_of_a_combination_is_harder():
    executor = Scripted(Outcome.CLEAN, Outcome.CLEAN)
    skate_one("3T+3T", executor)
    first, second = executor.tasks
    assert second.consistency < first.consistency


def test_single_elements_have_no_part_label():
    executor = Scripted(Outcome.CLEAN)
    skate_one("CCoSp4", executor)
    assert executor.tasks[0].part == ""
    assert executor.tasks[0].n_keys == 6


# ---------------------------------------------------------------- GOE


def goe(outcome, speed, consistency, seed=0, traits=()):
    from skaterrpg.engine import decide_goe

    rules, skater = load_rules(), load_skater()
    skater.traits = list(traits)
    return decide_goe(outcome, 67, speed, consistency, skater, rules, random.Random(seed))


def average_goe(outcome, speed, consistency):
    return sum(goe(outcome, speed, consistency, seed) for seed in range(200)) / 200


def test_faster_typing_earns_more_goe():
    assert average_goe(Outcome.CLEAN, 0.2, 70) > average_goe(Outcome.CLEAN, 0.8, 70)
    assert goe(Outcome.SHAKY, 0.1, 70) > goe(Outcome.SHAKY, 0.9, 70)


def test_better_trained_and_better_condition_earns_more_goe():
    assert average_goe(Outcome.CLEAN, 0.5, 95) > average_goe(Outcome.CLEAN, 0.5, 50)


def test_goe_ranges_per_outcome():
    for speed in (0.05, 0.5, 0.95):
        for seed in range(30):
            assert 0 <= goe(Outcome.CLEAN, speed, 30, seed) <= 5
            assert -3 <= goe(Outcome.SHAKY, speed, 70, seed) <= -1
            assert -4 <= goe(Outcome.UNDER_ROTATED, speed, 70, seed) <= -2
    assert goe(Outcome.FALL, 0.1, 99) == -5


def test_engine_hands_combinations_to_attempt_combination():
    class ComboAware(Scripted):
        def attempt_combination(self, tasks):
            self.combos = [t.code for t in tasks]
            return [Attempt(Outcome.CLEAN, 0.4) for _ in tasks]

    executor = ComboAware()
    element = skate_one("3S+2T+2Lo", executor)
    assert executor.combos == ["3S", "2T", "2Lo"]
    assert element.executed == "3S+2T+2Lo"
