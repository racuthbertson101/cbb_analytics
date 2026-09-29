"""Bracket schema: regions, seeds, play-in games, rounds. Team ids are ESPN ids (strings); seeds are 1-16."""
from __future__ import annotations

from dataclasses import dataclass, field

ROUNDS = ["First Round", "Second Round", "Sweet 16", "Elite Eight", "Final Four", "Championship"]
SEED_ORDER = [1, 16, 8, 9, 5, 12, 4, 13, 6, 11, 3, 14, 7, 10, 2, 15]  # standard first-round pairing order within a region


@dataclass
class Slot:
    seed: int
    team: str | None = None  # None while decided by a play-in game


@dataclass
class PlayIn:
    region: int
    seed: int          # the seed line that the play-in winner occupies
    teams: tuple[str, str]


@dataclass
class Region:
    name: str
    slots: list[Slot]  # length 16, indexed by seed-1


@dataclass
class Bracket:
    regions: list[Region]
    play_in: list[PlayIn] = field(default_factory=list)
    # Final Four pairing: pairs of region indexes that meet in the semifinals
    final_four: tuple[tuple[int, int], tuple[int, int]] = ((0, 1), (2, 3))
    year: int | None = None

    def teams(self) -> list[str]:
        out = [s.team for r in self.regions for s in r.slots if s.team]
        for p in self.play_in:
            out += list(p.teams)
        return out


def standard_bracket(regions: dict[str, list[str]], play_in: list[PlayIn] | None = None, year=None) -> Bracket:
    """regions: name -> 16 team ids ordered by seed 1..16 (use '' for a play-in slot)."""
    rs = []
    for name, ids in regions.items():
        assert len(ids) == 16
        rs.append(Region(name, [Slot(i + 1, t or None) for i, t in enumerate(ids)]))
    return Bracket(rs, play_in or [], year=year)
