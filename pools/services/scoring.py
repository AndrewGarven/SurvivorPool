from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Set

from pools.models import Entry, Contestant


@dataclass(frozen=True)
class ScoreBreakdown:
    total: int
    weekly_points: int
    bonus_points: int
    winners_alive: int
    loser_alive: bool


def calculate_weekly_points(
    entry: Entry,
    eliminated: Set[int],
) -> tuple[int, int, bool]:
    """
    Returns (weekly_points, winners_alive, loser_alive).

    Rules:
      +2 for each winner pick still in (max 4)
      -1 if first_out pick is still in
    """
    if entry.winner_1_id is None or entry.winner_2_id is None or entry.first_out_id is None:
        # If picks aren't complete, score is undefined; treat as 0 for now.
        return 0, 0, False

    w1_alive = entry.winner_1_id not in eliminated
    w2_alive = entry.winner_2_id not in eliminated
    winners_alive = int(w1_alive) + int(w2_alive)

    loser_alive = entry.first_out_id not in eliminated

    weekly_points = 2 * winners_alive + (-1 if loser_alive else 0)
    return weekly_points, winners_alive, loser_alive


def calculate_total_points(
    entry: Entry,
    eliminated_each_week: Iterable[Set[int]],
    sole_survivor_id: Optional[int] = None,
    winner_bonus: int = 14,
) -> ScoreBreakdown:
    """
    Sum weekly points across weeks and add end bonus if applicable.

    eliminated_each_week:
      - an iterable where each element is the cumulative eliminated set *up to that week*,
        OR per-week eliminated sets (see note below).

    IMPORTANT: This function expects cumulative eliminated sets.
      Week 1 set = {id_of_first_boot}
      Week 2 set = {week1, week2}
      ...
    """
    eliminated_cum: Set[int] = set()
    total = 0
    last_weekly = 0
    winners_alive = 0
    loser_alive = False

    for elim_set in eliminated_each_week:
        eliminated_cum = set(elim_set)  # treat provided as cumulative
        last_weekly, winners_alive, loser_alive = calculate_weekly_points(entry, eliminated_cum)
        total += last_weekly

    bonus = 0
    if sole_survivor_id is not None and entry.winner_1_id and entry.winner_2_id:
        if sole_survivor_id in (entry.winner_1_id, entry.winner_2_id):
            bonus = winner_bonus
            total += bonus

    return ScoreBreakdown(
        total=total,
        weekly_points=last_weekly,
        bonus_points=bonus,
        winners_alive=winners_alive,
        loser_alive=loser_alive,
    )


def eliminated_ids_from_contestants(contestants: Iterable[Contestant]) -> Set[int]:
    """Helper: turn contestants into a set of contestant IDs."""
    return {c.id for c in contestants}

from typing import List
from pools.models import Episode, Season


def build_cumulative_eliminations(season: Season) -> List[set[int]]:
    """
    Returns a list where each element is the cumulative set of eliminated contestant IDs
    up through that episode number.

    Example (2 eps):
      ep1 eliminated=A -> [{A}]
      ep2 eliminated=B -> [{A}, {A,B}]
    """
    episodes = Episode.objects.filter(season=season).order_by("number")

    cumulative: set[int] = set()
    weeks: List[set[int]] = []

    for ep in episodes:
        eliminated_ids = ep.eliminated.values_list("id", flat=True)
        cumulative.update(eliminated_ids)
        weeks.append(set(cumulative))

    return weeks
