"""Tests for the key mini-game rules."""

import random

from skaterrpg.data_loader import load_rules
from skaterrpg.minigame import KeyPressExecutor, ElementTask, count_errors, judge, make_sequence, time_limit
from skaterrpg.models import ElementType, Outcome


def test_count_errors_ignores_case_and_spaces():
    assert count_errors(["J", "K", "D"], "j k d") == 0


def test_count_errors_one_missing_key_is_one_error():
    assert count_errors(["J", "K", "D", "F"], "JDF") == 1
    assert count_errors(["J", "K", "D", "F"], "JKXF") == 1
    assert count_errors(["J", "K", "D", "F"], "") == 4


def test_judge_outcomes():
    assert judge(0, 1.0, 4.0).outcome is Outcome.CLEAN
    assert judge(1, 1.0, 4.0).outcome is Outcome.SHAKY
    assert judge(2, 1.0, 4.0).outcome is Outcome.UNDER_ROTATED
    assert judge(3, 1.0, 4.0).outcome is Outcome.FALL
    assert judge(0, 4.5, 4.0).outcome is Outcome.FALL  # too slow


def test_sequence_length_and_no_immediate_repeats():
    seq = make_sequence(6, ["A", "S", "D"], random.Random(1))
    assert len(seq) == 6
    assert all(a != b for a, b in zip(seq, seq[1:]))


def test_better_skater_gets_more_time():
    rules = load_rules()
    assert time_limit(5, 90, 80, rules) > time_limit(5, 40, 30, rules)


def test_keypress_executor_with_scripted_input():
    """Type the shown keys exactly -> clean."""
    shown = []
    answers = iter(["", None])  # Enter for 'ready', then the typed keys

    def fake_input(prompt):
        value = next(answers)
        return "".join(shown[-1].split()) if value is None else value

    times = iter([0.0, 1.2])
    executor = KeyPressExecutor(["A", "S", "D", "F"], random.Random(0), fake_input, shown.append, lambda: next(times))
    task = ElementTask(1, "3Lz", ElementType.JUMP, 5, 6.0, 70)
    attempt = executor.attempt(task)
    assert attempt.outcome is Outcome.CLEAN
    assert abs(attempt.speed_ratio - 0.2) < 1e-9
