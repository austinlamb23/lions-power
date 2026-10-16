"""Best-ball simulation for the CURRENT season, live -- for each real fantasy
team, compares what they actually started that week against the highest-
scoring lineup their full roster (starters + bench) could have produced
under the league's real slot rules.

Live-only, current-season-only, by construction: the underlying data comes
from roster_pool.get_rosters_for_week, which reflects ESPN's CURRENT roster
membership with that week's scoring attached -- not a historical snapshot of
who was actually rostered during a past week. For the week that's currently
being played this is exactly right; for an EARLIER week this season where
waiver moves have happened since, a bench player's points here may reflect
someone who wasn't actually on that roster back then. (Complete historical
seasons don't have this problem at all -- weekly_rosters/ingest_weekly_rosters.py
uses ESPN's mBoxscore rosterForMatchupPeriod field instead, a true per-week
snapshot -- but that field is starters-only, no bench, which is exactly the
gap this endpoint exists to cover for the live season.)

The league's real starting lineup (confirmed empirically against historical
weekly_rosters, not assumed) is QB/RB/RB/WR/WR/TE/FLEX(RB-WR-TE)/D-ST/K --
the exact same 9-slot structure already used by All-Star Roster, reused
directly rather than redefined here.
"""
from __future__ import annotations

import sqlite3

import requests
from fastapi import APIRouter, Depends, HTTPException

from database import get_db
import roster_pool
from routers.all_star_roster import SLOTS

router = APIRouter(prefix="/api/best-ball", tags=["best-ball"])

# QB/DST/K have exactly one eligible position AND no interaction with FLEX --
# genuinely independent, "just take the best available" slots. RB1/RB2/WR1/
# WR2/TE are ALSO individually single-position (per SLOT_ELIGIBLE_POSITIONS),
# but must NOT be lumped in with QB/DST/K here -- they compete with FLEX for
# the same players, so they're handled together with it below instead. Listed
# explicitly rather than derived from SLOT_ELIGIBLE_POSITIONS by "exactly one
# eligible position", since that filter can't tell these two groups apart.
_FIXED_SLOTS = {"QB": "QB", "DST": "D/ST", "K": "K"}
_FLEX_GROUP_SLOTS = {"RB1": "RB", "RB2": "RB", "WR1": "WR", "WR2": "WR", "TE": "TE"}


def _optimal_lineup(players: list[dict]) -> tuple[float, list[dict]]:
    """players: [{"player_id", "player_name", "position", "points"}, ...] --
    a team's full roster pool (starters+bench) for one week. Greedy
    assignment is PROVABLY optimal for this exact slot structure (one flex
    spot pooling from positions that also have their own dedicated slots):
    since every RB/WR/TE/FLEX slot pays identically regardless of its label,
    the only real choice is WHICH 2 RBs + 2 WRs + 1 TE + 1 more (any of
    RB/WR/TE) to start at all -- taking the top-2/top-2/top-1 for the
    dedicated slots and the single best leftover for FLEX is that choice,
    not an approximation of it."""
    by_position: dict[str, list[dict]] = {}
    for p in players:
        by_position.setdefault(p["position"], []).append(p)
    for pos in by_position:
        by_position[pos].sort(key=lambda p: -p["points"])

    used_ids: set = set()

    def take_best(pos: str) -> dict | None:
        for p in by_position.get(pos, []):
            if p["player_id"] not in used_ids:
                used_ids.add(p["player_id"])
                return p
        return None

    assigned: dict[str, dict | None] = {}
    for slot, pos in _FIXED_SLOTS.items():
        assigned[slot] = take_best(pos)
    for slot, pos in _FLEX_GROUP_SLOTS.items():
        assigned[slot] = take_best(pos)

    flex_candidates = [
        p for pos in ("RB", "WR", "TE") for p in by_position.get(pos, [])
        if p["player_id"] not in used_ids
    ]
    assigned["FLEX"] = max(flex_candidates, key=lambda p: p["points"]) if flex_candidates else None

    lineup, total = [], 0.0
    for slot in SLOTS:
        p = assigned.get(slot)
        points = round(p["points"], 2) if p else 0.0
        lineup.append({"slot": slot, "player_name": p["player_name"] if p else None, "points": points})
        total += points
    return round(total, 2), lineup


@router.get("/{year}/{week}")
def get_best_ball(
    year: int, week: int,
    team_id: int | None = None,
    db: sqlite3.Connection = Depends(get_db),
):
    try:
        rosters = roster_pool.get_rosters_for_week(year, week)
    except requests.RequestException as e:
        raise HTTPException(502, f"Couldn't reach ESPN: {e}")

    team_info = {
        r["team_id"]: {"team_name": r["team_name"], "owner_name": r["owner_name"]}
        for r in db.execute("SELECT team_id, team_name, owner_name FROM teams WHERE year=?", (year,)).fetchall()
    }

    results = []
    for tid, roster in rosters.items():
        if team_id is not None and tid != team_id:
            continue
        info = team_info.get(tid, {})

        actual_total = 0.0
        actual_lineup = []
        for p in roster["starters"]:
            points = round(p.get("actual_points") or 0.0, 2)
            actual_total += points
            actual_lineup.append({"slot": p.get("slot", "?"), "player_name": p["name"], "points": points})

        pool = [
            {"player_id": p["player_id"], "player_name": p["name"], "position": p["position"], "points": p.get("actual_points") or 0.0}
            for p in roster["starters"] + roster["bench"]
        ]
        optimal_total, optimal_lineup = _optimal_lineup(pool)

        results.append({
            "team_id": tid,
            "team_name": info.get("team_name", "?"),
            "owner_name": info.get("owner_name", "?"),
            "actual_score": round(actual_total, 2),
            "optimal_score": optimal_total,
            "points_left_on_bench": round(optimal_total - actual_total, 2),
            "actual_lineup": actual_lineup,
            "optimal_lineup": optimal_lineup,
        })

    results.sort(key=lambda r: -r["optimal_score"])
    return {"year": year, "week": week, "teams": results}
