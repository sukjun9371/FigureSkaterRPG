"""Tests for the key mini-game rules."""

import random

from skaterrpg.data_loader import load_catalog, load_rules
from skaterrpg.minigame import KeyPressExecutor, LiveKeyExecutor, ElementTask, render_timer_line, count_errors, judge, make_sequence, time_limit
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
    seq = make_sequence(6, [["A", "S", "D"]], random.Random(1))
    assert len(seq) == 6
    assert all(a != b for a, b in zip(seq, seq[1:]))


def test_two_key_groups_take_turns():
    left, right = ["Q", "W", "Z"], ["P", ".", ";"]
    for seed in range(20):
        seq = make_sequence(5, [left, right], random.Random(seed))
        sides = ["L" if k in left else "R" for k in seq]
        assert all(a != b for a, b in zip(sides, sides[1:])), seq


def test_every_element_has_a_known_layout():
    keys = load_rules().keys
    for element in load_catalog().values():
        assert element.layout in keys, element.code


def test_jumps_spins_and_steps_use_different_keys():
    keys = load_rules().keys
    flat = {name: {k for group in groups for k in group} for name, groups in keys.items()}
    jumps = flat["jump_easy"] | flat["jump_mid"] | flat["jump_hard"]
    assert not flat["spin"] & flat["step"]
    assert not jumps & flat["spin"] and not jumps & flat["step"]
    for name in ("jump_easy", "jump_mid", "jump_hard"):
        assert len(keys[name]) == 2  # far left / far right


def test_harder_jumps_get_harder_layouts():
    catalog = load_catalog()
    assert catalog["2T"].layout == "jump_easy"
    assert catalog["3T"].layout == "jump_mid"
    assert catalog["3Lz"].layout == "jump_hard"


def test_punctuation_keys_count_as_typed():
    assert count_errors(["Q", ".", "W", ";"], "q.w;") == 0


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
    keys = {"jump": [["Q", "W"], ["P", "."]]}
    executor = KeyPressExecutor(keys, random.Random(0), fake_input, shown.append, lambda: next(times))
    task = ElementTask(1, "3Lz", ElementType.JUMP, "jump", 5, 6.0, 70)
    attempt = executor.attempt(task)
    assert attempt.outcome is Outcome.CLEAN
    assert abs(attempt.speed_ratio - 0.2) < 1e-9
    assert "JUMP" in shown[0]
    typed = "".join(shown[-2].split())
    assert all(k in "QWP." for k in typed)


class FakeReader:
    """Stands in for the terminal: hands out scripted keys, one per read,
    and moves a fake clock forward by `step` seconds each read."""

    def __init__(self, keys, clock, step=0.3):
        self.keys, self.clock, self.step = list(keys), clock, step

    def __call__(self):  # used as the reader factory
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        pass

    def read(self, timeout=None):
        self.clock[0] += self.step
        return self.keys.pop(0) if self.keys else None


def live_attempt(keys_for, step=0.3, limit=6.0):
    """Run LiveKeyExecutor; keys_for(seq) returns what the player types after Space."""
    clock = [0.0]
    out = []
    keys = {"jump": [["Q", "W"], ["P", "."]]}
    seq = make_sequence(5, keys["jump"], random.Random(0))  # the same sequence the executor will draw
    reader = FakeReader([" "] + keys_for(seq), clock, step)
    executor = LiveKeyExecutor(keys, random.Random(0), reader, out.append, lambda: clock[0])
    attempt = executor.attempt(ElementTask(1, "3Lz", ElementType.JUMP, "jump", 5, limit, 70))
    return attempt, "".join(out)


def test_live_typing_the_keys_is_clean_without_enter():
    attempt, screen = live_attempt(lambda seq: [k.lower() for k in seq])
    assert attempt.outcome is Outcome.CLEAN
    assert "s " in screen and "█" in screen  # the timer bar was drawn


def test_live_backspace_fixes_a_mistake():
    attempt, _ = live_attempt(lambda seq: ["X", "\x7f"] + seq)
    assert attempt.outcome is Outcome.CLEAN


def test_live_running_out_of_time_is_a_fall():
    attempt, _ = live_attempt(lambda seq: seq[:2], step=1.0, limit=4.0)
    assert attempt.outcome is Outcome.FALL
    assert attempt.note == "time ran out"


def test_timer_bar_shrinks():
    full = render_timer_line(["Q", "P"], [], 4.0, 4.0)
    half = render_timer_line(["Q", "P"], [], 2.0, 4.0)
    assert full.count("█") > half.count("█") > 0


# ---------------------------------------------------------------- live combinations


def combo_tasks(limit=6.0):
    keys = {"jump": [["Q", "W", "Z", "X"], ["P", "O", ".", ","]]}
    tasks = [
        ElementTask(3, "3Lz+3T", ElementType.JUMP, "jump", 5, limit, 70, "jump 1 of 2: 3Lz", "3Lz"),
        ElementTask(3, "3Lz+3T", ElementType.JUMP, "jump", 4, limit, 70, "jump 2 of 2: 3T", "3T"),
    ]
    rng = random.Random(0)
    seqs = [make_sequence(t.n_keys, keys["jump"], rng) for t in tasks]  # what the executor will draw
    return keys, tasks, seqs


def run_combo(typing, step=0.3, limit=6.0):
    keys, tasks, seqs = combo_tasks(limit)
    clock, out = [0.0], []
    reader = FakeReader([" "] + typing(seqs), clock, step)
    executor = LiveKeyExecutor(keys, random.Random(0), reader, out.append, lambda: clock[0])
    return executor.attempt_combination(tasks), "".join(out)


def test_live_combination_is_one_element_on_one_line():
    attempts, screen = run_combo(lambda seqs: seqs[0] + seqs[1])
    assert [a.outcome for a in attempts] == [Outcome.CLEAN, Outcome.CLEAN]
    assert screen.count("Press Space") == 1  # one "ready" for the whole combination
    assert screen.count("[3]") == 1  # one header
    assert "5+4 keys" in screen and "12.0s" in screen  # both jumps' keys and time
    assert "3Lz: " in screen and "3T: " in screen


def test_live_combination_stops_after_a_fall():
    attempts, screen = run_combo(lambda seqs: ["1", "2", "3", "4", "5"] + seqs[1])
    assert len(attempts) == 1 and attempts[0].outcome is Outcome.FALL
    assert "(not done)" in screen
    assert "ends the combination" in screen


def test_live_combination_carries_time_over():
    # Each jump alone is allowed 3.0s. 3T keys take 4 reads x 1.0s = 4.0s,
    # which only fits because the 3Lz was typed fast (5 x 0.3s at the start).
    keys, tasks, seqs = combo_tasks(limit=3.0)
    clock, out = [0.0], []

    class Uneven(FakeReader):
        def read(self, timeout=None):
            key = super().read(timeout)
            self.step = 1.0 if len(self.keys) < 4 else 0.3
            return key

    reader = Uneven([" "] + seqs[0] + seqs[1], clock, 0.3)
    executor = LiveKeyExecutor(keys, random.Random(0), reader, out.append, lambda: clock[0])
    attempts = executor.attempt_combination(tasks)
    assert [a.outcome for a in attempts] == [Outcome.CLEAN, Outcome.CLEAN]
