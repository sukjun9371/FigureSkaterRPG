"""Tests for the pure scoring math in skaterrpg/scoring.py."""

import pytest

from skaterrpg import scoring
from skaterrpg.models import Program, Skater

SENIOR_FALLS = [1.0, 1.0, 2.0, 2.0, 3.0]


def test_round2_rounds_halves_up():
    assert scoring.round2(1.005) == 1.01
    assert scoring.round2(-1.005) == -1.01
    assert scoring.round2(2.344) == 2.34


def test_goe_value_is_ten_percent_of_base_per_point():
    assert scoring.goe_value(2, 5.90) == 1.18  # +2 on 3Lz
    assert scoring.goe_value(-5, 4.20) == -2.10  # fall on 3T
    assert scoring.goe_value(0, 8.00) == 0.0


def test_single_element_score():
    assert scoring.element_score([3.30], 3) == (3.30, 0.99, 4.29)  # 2A +3


def test_combination_goe_uses_highest_jump():
    # 3Lz+3T, +2: GOE from 3Lz (5.90), not from the 10.10 total
    assert scoring.element_score([5.90, 4.20], 2) == (10.10, 1.18, 11.28)


def test_under_rotated_base_value():
    assert scoring.reduced_base_value(5.90, 0.80) == 4.72
    assert scoring.reduced_base_value(4.20, 0.80) == 3.36


def test_under_rotated_combo_reference_is_highest_executed_value():
    # 3T+3T< : 4.20 + 3.36, GOE -3 on 4.20
    assert scoring.element_score([4.20, 3.36], -3) == (7.56, -1.26, 6.30)


@pytest.mark.parametrize(
    "falls, expected",
    [(0, 0.0), (1, 1.0), (2, 2.0), (3, 4.0), (4, 6.0), (5, 9.0), (6, 12.0)],
)
def test_fall_deductions_escalate(falls, expected):
    assert scoring.fall_deduction(falls, SENIOR_FALLS) == expected


@pytest.mark.parametrize("raw, mark", [(6.4, 6.5), (6.1, 6.0), (6.125, 6.25), (-1, 0.25), (12, 10.0)])
def test_component_marks_are_quarter_steps_between_025_and_10(raw, mark):
    assert scoring.component_mark(raw) == mark


def test_pcs_uses_segment_factor():
    components = {"Composition": 7.0, "Presentation": 7.25, "Skating Skills": 7.5}
    assert scoring.program_component_score(components, 1.33) == 28.93  # 21.75 x 1.33 = 28.9275
    assert scoring.program_component_score(components, 2.67) == 58.07  # 21.75 x 2.67


def test_program_components_from_stats_and_falls():
    skater = Skater("Test", 20, "Club", {"skating": 70, "artistry": 60}, composure=50)
    program = Program("short", [], choreo_quality=60, familiarity=70)
    clean = scoring.program_components(skater, program, falls=0)
    assert clean == {"Composition": 6.5, "Presentation": 5.75, "Skating Skills": 7.0}
    one_fall = scoring.program_components(skater, program, falls=1)
    assert one_fall["Presentation"] < clean["Presentation"]
    assert one_fall["Composition"] == clean["Composition"]


def test_segment_score():
    tes = scoring.total_element_score([4.29, 11.28, 3.84])
    assert tes == 19.41
    assert scoring.segment_score(tes, 28.93, 1.0) == 47.34
