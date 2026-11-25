"""Text formatting for score sheets and standings. Returns strings, prints nothing."""

from __future__ import annotations

from .competition import Entry
from .models import SegmentResult

SEGMENT_NAMES = {"short": "Short Program", "free": "Free Skating"}


def _signed(x: float) -> str:
    return f"{x:+.2f}" if x else " 0.00"


def format_segment(result: SegmentResult, event_name: str) -> str:
    title = f"{event_name}  |  {SEGMENT_NAMES[result.segment]}  |  JUDGES DETAILS"
    lines = [
        "=" * 68,
        title,
        f"Skater: {result.skater_name}",
        "=" * 68,
        f"{'#':>2}  {'Executed':<16}{'Info':<6}{'Base':>7}{'GOE':>6}{'GOE pts':>9}{'Score':>9}",
        "-" * 68,
    ]
    for e in result.elements:
        lines.append(
            f"{e.number:>2}  {e.executed:<16}{e.info:<6}{e.base_value:>7.2f}{e.goe:>+6d}"
            f"{_signed(e.goe_value):>9}{e.score:>9.2f}"
        )
    base_total = sum(e.base_value for e in result.elements)
    lines += [
        "-" * 68,
        f"{'Base value total':<24}{base_total:>7.2f}{'TES':>15}{result.tes:>9.2f}",
        "",
        f"Program components (x{result.pcs_factor:.2f})",
    ]
    for name, mark in result.components.items():
        lines.append(f"    {name:<20}{mark:>6.2f}")
    lines.append(f"{'PCS':<56}{result.pcs:>9.2f}")
    if result.deductions:
        lines.append("Deductions")
        for reason, amount in result.deductions.items():
            lines.append(f"    {reason:<52}{-amount:>9.2f}")
    lines += ["=" * 68, f"{'SEGMENT SCORE':<56}{result.total:>9.2f}", "=" * 68]
    return "\n".join(lines)


def format_standings(entries: list[Entry], after: str) -> str:
    if after == "short":
        header = f"{'Pl':>3}  {'Name':<22}{'Club':<20}{'SP':>8}"
        rows = [f"{i:>3}  {e.name:<22}{e.club:<20}{e.short or 0:>8.2f}" for i, e in enumerate(entries, 1)]
        title = "STANDINGS AFTER SHORT PROGRAM"
    else:
        header = f"{'Pl':>3}  {'Name':<22}{'Club':<20}{'SP':>8}{'FS':>9}{'Total':>9}"
        rows = [
            f"{i:>3}  {e.name:<22}{e.club:<20}{e.short or 0:>8.2f}{e.free or 0:>9.2f}{e.total:>9.2f}"
            for i, e in enumerate(entries, 1)
        ]
        title = "FINAL RESULTS"
    marked = [r + ("   <== you" if e.is_player else "") for r, e in zip(rows, entries)]
    return "\n".join([title, header, "-" * len(header), *marked])
