"""Terminal front end:  python -m skaterrpg

Only menus and printing live here. All rules are in engine.py / scoring.py, so
a Pygame front end can later replace this file without touching them.
"""

from __future__ import annotations

import argparse
import random

from .competition import Competition
from .data_loader import load_catalog, load_events, load_names, load_rules, load_skater
from .minigame import AutoExecutor, KeyPressExecutor
from .programs import validate_program
from .scoresheet import SEGMENT_NAMES, format_segment, format_standings


def choose(prompt: str, options: list[str]) -> int:
    for i, opt in enumerate(options, 1):
        print(f"  {i}. {opt}")
    while True:
        answer = input(f"{prompt} [1-{len(options)}]: ").strip()
        if answer.isdigit() and 1 <= int(answer) <= len(options):
            return int(answer) - 1
        print("  Please type one of the numbers above.")


def show_skater(skater) -> None:
    print(f"\n{skater.name}, {skater.age}  ({skater.club})")
    print("  " + "  ".join(f"{k.title()} {v}" for k, v in skater.stats.items()))
    print(f"  Composure {skater.composure}  Fatigue {skater.fatigue}  Traits: {', '.join(skater.traits) or '-'}")
    for seg, prog in skater.programs.items():
        print(f"  {SEGMENT_NAMES[seg]}: {', '.join(prog.elements)}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Figure skating competition prototype")
    parser.add_argument("--auto", action="store_true", help="skip the key mini-game and roll dice")
    parser.add_argument("--event", help="event id from data/events.json, e.g. nationals")
    parser.add_argument("--seed", type=int, help="random seed, for repeatable runs")
    args = parser.parse_args(argv)

    rng = random.Random(args.seed)
    catalog, rules, events = load_catalog(), load_rules(), load_events()
    skater = load_skater()

    print("=" * 68)
    print("  FIGURE SKATER RPG  -  competition prototype")
    print("=" * 68)
    show_skater(skater)

    for program in skater.programs.values():
        for problem in validate_program(program, catalog, rules):
            print(f"  ! {problem}")

    if args.event:
        event = next(e for e in events if e.id == args.event)
    else:
        print("\nWhich competition?")
        event = events[choose("Event", [f"{e.name}  ({e.level})" for e in events])]

    auto = args.auto
    if not auto:
        print("\nHow do you want to skate?")
        auto = choose("Mode", ["Play each element (type the keys, then Enter)", "Auto (dice roll)"]) == 1

    if auto:
        executor = AutoExecutor(rng)
    else:
        executor = KeyPressExecutor(rules.keyset, rng)
        print("\nFor each element you'll see keys like  J  K  D  F.")
        print("Type them (spaces optional) and press Enter before time runs out.")
        print("0 mistakes = clean, 1 = shaky, 2 = under-rotated, 3+ or too slow = fall.")

    competition = Competition(event, skater, catalog, rules, executor, load_names(), rng)

    for segment in ("short", "free"):
        input(f"\nPress Enter to start the {SEGMENT_NAMES[segment]}...")
        result = competition.skate(segment)
        print("\n" + format_segment(result, event.name))
        print("\n" + format_standings(competition.standings(segment), segment))

    place = [e.is_player for e in competition.standings("free")].index(True) + 1
    print(f"\n{skater.name} finishes {place} of {len(competition.entries)} at the {event.name}.")


if __name__ == "__main__":
    main()
