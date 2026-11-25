"""Read the files in skaterrpg/data/ into model objects."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from .models import ElementDef, ElementType, Event, Program, Rules, Skater

DATA_DIR = Path(__file__).parent / "data"


def _read_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def load_catalog(path: Path | None = None) -> dict[str, ElementDef]:
    """elements.csv -> {code: ElementDef}."""
    path = path or DATA_DIR / "elements.csv"
    catalog: dict[str, ElementDef] = {}
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            catalog[row["code"]] = ElementDef(
                code=row["code"],
                name=row["name"],
                type=ElementType(row["type"]),
                family=row["family"],
                level=int(row["level"]) if row["level"] else None,
                base_value=float(row["base_value"]),
                keys=int(row["keys"]),
                stat=row["stat"],
                layout=row["layout"],
            )
    return catalog


def load_rules(path: Path | None = None) -> Rules:
    data = _read_json(path or DATA_DIR / "rules.json")
    for key in [k for k in data if k.startswith("_")]:
        data.pop(key)
    return Rules(**data)


def load_events(path: Path | None = None) -> list[Event]:
    data = _read_json(path or DATA_DIR / "events.json")
    return [Event(**e) for e in data["events"]]


def load_names(path: Path | None = None) -> dict[str, list[str]]:
    data = _read_json(path or DATA_DIR / "names.json")
    data.pop("_comment", None)
    return data


def load_skater(path: Path | None = None) -> Skater:
    data = _read_json(path or DATA_DIR / "skater.json")
    data.pop("_comment", None)
    programs = {seg: Program(segment=seg, **p) for seg, p in data.pop("programs", {}).items()}
    return Skater(programs=programs, **data)
