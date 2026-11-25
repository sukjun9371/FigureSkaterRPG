# Figure Skater RPG

An original figure skating coach RPG, built step by step in Python.
You coach women's singles skaters, build their programs and send them to competitions.

This first slice is the **competition engine**: one skater skates a short program and a
free skate against a generated field, and you get an ISU-style score sheet.

## Run it

Needs Python 3.10 or newer. No packages are needed to play.

```bash
git clone https://github.com/sukjun9371/FigureSkaterRPG.git
cd FigureSkaterRPG
python -m skaterrpg                  # menus: pick an event and a mode
python -m skaterrpg --auto           # skip typing, roll dice for each element
python -m skaterrpg --event nationals --seed 7   # repeatable run
```

On Windows use `py -m skaterrpg` if `python` is not found.

### The element mini-game

For each element you see a key sequence such as `J  K  D  F` and a time limit.
Press Enter when ready, type the keys (spaces and case don't matter), and press Enter again.

| Your input | Result |
|---|---|
| no mistakes | clean, positive GOE (faster = higher) |
| 1 mistake | shaky, GOE -1 to -3 |
| 2 mistakes | under-rotated jump (`<`, 80% base value) or a spin/step that loses a level |
| 3+ mistakes, or too slow | fall: GOE -5, a fall deduction, `<` on jumps |

Harder elements show more keys (2A: 4, 3Lz: 5, a combination: +1 per extra jump).
A skater with higher consistency, familiarity and composure gets more time.

### Run the tests

```bash
pip install -r requirements-dev.txt
python -m pytest
```

## How the code is organised

```
skaterrpg/
  data/
    elements.csv    every element: base value, key count, which stat it uses
    rules.json      tunable numbers: GOE step, PCS factors, fall deductions, timer
    events.json     competitions and their typical winning totals
    skater.json     the sample skater, her stats and both programs
    names.json      made-up names for opponents
  models.py         data classes only (Skater, Program, ElementDef, ...)
  scoring.py        pure score math: base value, GOE, PCS, deductions
  minigame.py       key sequence, timer, judging; the two "executors"
  engine.py         perform_program(): skates a whole program and scores it
  programs.py       checks a program follows the layout rules
  competition.py    the field of opponents and the standings
  scoresheet.py     turns results into the printed score sheet
  __main__.py       the terminal menus (the only file that talks to the player)
tests/              pytest tests for scoring, the mini-game and the engine
```

The idea: **rules live in data files and pure functions; the menu code only prints and asks.**
That keeps the math testable, and a Pygame screen can later replace `__main__.py` alone.

### The flow of one element

```
engine.perform_program
  -> effective_consistency()   how likely is a clean element right now?
  -> executor.attempt(task)    KeyPressExecutor (you type) or AutoExecutor (dice)
       returns an Outcome: clean / shaky / under-rotated / fall
  -> score_element()           outcome -> executed code, base value, GOE
  -> scoring.*                 GOE points, TES, PCS, deductions, segment score
```

An executor is anything with an `attempt(task)` method. Practice mode will reuse
`perform_program` with the same executors and use the result to grow consistency.

## Scoring rules used (simplified)

- **Base values** from `elements.csv` (close to current ISU values; tune freely).
- **GOE** is -5 to +5, each point = 10% of base value. In a combination GOE uses the
  highest-value jump. Under-rotated or fallen jumps keep 80% of their base value.
- **Components**: Composition (choreography quality and familiarity), Presentation
  (artistry and composure, lower after falls), Skating Skills (skating). Marks are 0.25
  to 10 in quarter steps. PCS = sum x 1.33 (short) or 2.67 (free), the senior women's factors.
- **Deductions**: falls cost 1, 1, 2, 2, then 3 each.
- **Opponents** are not simulated element by element yet; their scores are drawn
  around the event's typical winning total.

Event names are in `events.json`. Real-sounding names are fine for private play;
swap any trademarked names before sharing the game.

## Next steps

Practice mode (reuse the engine), training weeks, the season calendar and the club.
See the design doc for the full plan.
