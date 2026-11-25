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
python -m skaterrpg --no-live        # old style: type the keys, then Enter
```

On Windows use `py -m skaterrpg` if `python` is not found.

### The element mini-game

For each element you see a key sequence and a time limit. Press Space when ready,
then type the keys while a **live timer bar** counts down:

```
[3] JUMP  3Lz+3T  -  jump 1 of 2: 3Lz   (5 keys, 5.3s)
    ██████████████░░░░░░░░░░  3.1s     1  .  [Q]  /  Z
```

Typed keys turn green (right) or red (wrong), the next key is in brackets, and
the bar goes green, yellow, red. No Enter needed: the element ends when you've
typed all the keys, or as a fall when time runs out. Backspace fixes a key.
(When input is piped rather than typed, or with `--no-live`, the game falls back
to typing the keys and pressing Enter.)

Each kind of element has its own keys, so you can feel the difference:

| Element | Keys | Example |
|---|---|---|
| Spin | home row `A S D F J K L` | `S  J  D  K` |
| Step / choreo sequence | top row `E R T Y U I` | `T  R  U  E` |
| Easy jump (singles, doubles) | `Q W` and `O P`, taking turns | `Q  P  W` |
| Mid jump (2A, 3T, 3S, 3Lo) | adds `Z X` and `. ,` | `Z  P  Q  .` |
| Hard jump (3F, 3Lz, 3A, quads) | `1 2 Q Z` and `9 0 . /` | `1  .  Q  /  Z` |

Each element's layout is the `layout` column of `elements.csv`; the keys are in `rules.json`.

**Surprise keys.** While you type, one key a little ahead of you can change. It turns
magenta with a `!` and the line says `<- change!`. Type the new key. Harder layouts
surprise you more often (`surprise_chance` in `rules.json`, 10% for easy jumps up to
30% for hard ones). Surprises only happen with the live timer.

### The skater's luck

Typing is your part; landing is hers. After each element (or each jump of a
combination) there is a **landing roll**: even with perfect typing she can slip one
step (clean -> shaky -> under-rotated -> fall), e.g. `...but she steps out of the landing!`.

The chance is `(100 - effective consistency)% x luck_scale` (0.35), so a 90% element
slips 3.5% of the time and a 50% element 17.5%. **Effective consistency** is shown
next to each element and is built from:

| Factor | Where it comes from |
|---|---|
| Training | her practised consistency for that element (`skater.json`) |
| Strengths / weaknesses | +8 / -8 for listed element families, e.g. `Lz`, `F`, `LSp`, `StSq` |
| Condition of the week | rolled before the event: Great +8, Good +4, Normal 0, Off -5, Bad -10. Fatigue makes bad weeks likelier, composure good ones |
| Program and body | familiarity, fatigue, composure, stamina late in the free skate, second jump of a combo |

The same number also sets the time limit, so a skater in form gets more time *and*
slips less. Auto mode uses it as its dice roll.

A **jump combination plays as one element**: one "ready", one timer bar with the time
of all its jumps, and all jumps on one line. Time you save on the first jump carries
over to the next:

```
[3] JUMP  3Lz+3T   (5+4 keys, 10.1s, 69/73% consistency)
    ██████████░░  8.7s     3Lz: 9  2  0  Z  . + 3T: W  [O]  X  .
```

Each jump is still judged on its own. A fall ends the combination: the jumps after it
are never done and score nothing, so `3Lz+3T` with a fall on the 3Lz is called just
`3Lz<`. The second and later jumps are also a little harder.

| Your input | Result |
|---|---|
| no mistakes | clean, positive GOE (faster = higher) |
| 1 mistake | shaky, GOE -1 to -3 |
| 2 mistakes | under-rotated jump (`<`, 80% base value) or a spin/step that loses a level |
| 3+ mistakes, or too slow | fall: GOE -5, a fall deduction, `<` on jumps |

Harder elements show more keys (2A: 4, 3Lz: 5, a level 4 spin: 6).
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
    elements.csv    every element: base value, key count, key layout, stat used
    rules.json      tunable numbers: keys per element type, GOE, PCS, falls, timer
    events.json     competitions and their typical winning totals
    skater.json     the sample skater: stats, strengths/weaknesses, consistency, programs
    names.json      made-up names for opponents
  models.py         data classes only (Skater, Program, ElementDef, ...)
  scoring.py        pure score math: base value, GOE, PCS, deductions
  minigame.py       key sequence, timer, judging, landing roll, surprise key; the executors
  condition.py      condition of the week
  terminal.py       reads single key presses for the live timer (Mac, Linux, Windows)
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
  -> attempt_element()         one attempt, or one per jump in a combination
       -> effective_consistency()   how likely is a clean element right now?
       -> executor.attempt(task)    LiveKeyExecutor / KeyPressExecutor (you type) or AutoExecutor (dice)
            returns an Outcome: clean / shaky / under-rotated / fall
  -> score_element()           outcome -> executed code, base value, GOE
  -> scoring.*                 GOE points, TES, PCS, deductions, segment score
```

An executor is anything with an `attempt(task)` method. Practice mode will reuse
`perform_program` with the same executors and use the result to grow consistency.

## Scoring rules used (simplified)

- **Base values** from `elements.csv` (close to current ISU values; tune freely).
- **GOE** is -5 to +5, each point = 10% of base value. A clean element's GOE comes from
  its effective consistency (training, strengths/weaknesses, condition of the week:
  50% -> 0, 80% -> +2, 95% -> +3), how fast you typed (fast adds up to about +2, slow
  takes up to about -2), the skater's stats and a small judge variation (mostly 0);
  it never goes below 0. Shaky starts at -2 and under-rotated at -3, and typing speed
  moves them one step either way. A fall is -5. In a combination GOE uses the
  highest-value jump and follows the worst-landed jump. Under-rotated or fallen jumps
  keep 80% of their base value; jumps never reached after a fall score nothing.
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
