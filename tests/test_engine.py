"""End-to-end checks of the performance engine with a fixed executor."""

import random

from skaterrpg.data_loader import load_catalog, load_rules, load_skater
from skaterrpg.engine import level_down, perform_program
from skaterrpg.minigame import Attempt
from skaterrpg.models import Outcome
from skaterrpg.programs import validate_program


class Always:
    """Executor that returns the same outcome every time."""

    def __init__(self, outcome):
        self.outcome = outcome

    def attempt(self, task):
        return Attempt(self.outcome, 0.6)


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
    assert combo.executed == "3Lz+3T<"
    assert combo.base_value == 5.90 + 3.36
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
