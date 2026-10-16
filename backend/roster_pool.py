"""Live current-roster lookup, shared by Power Rankings' journey view
(backend/routers/power_rankings_roster.py) and the Game Room All-Star
Roster player pool (backend/routers/all_star_roster.py).

Extracted from what was originally power_rankings_roster.py's own private
logic -- nothing here is stored in almanac.db, it's a read-through cache in
front of ESPN's mRoster view, using the same lm-api-reads host/cookie
pattern already proven in ingest_weekly_rosters.py.
"""
from __future__ import annotations

import os
import re
import time

import requests
from dotenv import load_dotenv
from pathlib import Path

import pro_schedule

load_dotenv(Path(__file__).parent / ".env")

LEAGUE_ID = os.environ["ESPN_LEAGUE_ID"]
SWID = os.environ["ESPN_SWID"]
ESPN_S2 = os.environ["ESPN_S2"]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
}
COOKIES = {"SWID": SWID, "espn_s2": ESPN_S2}
BASE = "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{year}/segments/0/leagues/{league_id}"

POSITION_MAP = {1: "QB", 2: "RB", 3: "WR", 4: "TE", 5: "K", 16: "D/ST"}
# ESPN roster lineup-slot ids -> starting slot label. 20 = Bench, 21 = IR;
# anything else is a starting lineup slot (same slot ids as the league's own
# roster settings, e.g. 23 = FLEX).
STARTING_SLOT_MAP = {0: "QB", 2: "RB", 4: "WR", 6: "TE", 16: "D/ST", 17: "K", 23: "FLEX"}
BENCH_SLOTS = {20, 21}

CACHE_TTL_SECONDS = 30 * 60
# year -> (fetched_at, {team_id: {"starters": [...], "bench": [...]}})
_cache: dict[int, tuple[float, dict[int, dict]]] = {}


def clean_name(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _fetch_rosters(year: int) -> dict[int, dict]:
    """One league-wide roster pull, split by team_id — cheaper than one
    request per team, and means any caller only needs a single cold ESPN
    call no matter how many teams' rosters it needs this year."""
    url = BASE.format(year=year, league_id=LEAGUE_ID)
    r = requests.get(url, params=[("view", "mRoster")], cookies=COOKIES, headers=HEADERS, timeout=30)
    r.raise_for_status()
    data = r.json()

    rosters: dict[int, dict] = {}
    for team in data.get("teams", []):
        starters, bench = [], []
        for entry in team.get("roster", {}).get("entries", []):
            player = entry.get("playerPoolEntry", {}).get("player", {})
            row = {
                "player_id": player.get("id"),
                "name": clean_name(player.get("fullName", "?")),
                "position": POSITION_MAP.get(player.get("defaultPositionId"), "?"),
            }
            slot_id = entry.get("lineupSlotId")
            if slot_id in BENCH_SLOTS:
                bench.append(row)
            else:
                rows_slot = STARTING_SLOT_MAP.get(slot_id)
                if rows_slot:
                    row["slot"] = rows_slot
                starters.append(row)
        rosters[team["id"]] = {"starters": starters, "bench": bench}
    return rosters


def get_rosters(year: int) -> dict[int, dict]:
    cached = _cache.get(year)
    if cached and (time.time() - cached[0]) < CACHE_TTL_SECONDS:
        return cached[1]
    rosters = _fetch_rosters(year)
    _cache[year] = (time.time(), rosters)
    return rosters


# year,week -> (fetched_at, {team_id: {"starters": [...], "bench": [...]}})
_week_cache: dict[tuple[int, int], tuple[float, dict[int, dict]]] = {}


def _fetch_rosters_for_week(year: int, week: int) -> dict[int, dict]:
    """Same league-wide roster pull as _fetch_rosters, but scoped to a
    specific week -- ESPN's mRoster view returns that week's projected
    points (statSourceId=1) only when scoringPeriodId is passed explicitly,
    plus each player's real-life opponent via pro_schedule."""
    url = BASE.format(year=year, league_id=LEAGUE_ID)
    r = requests.get(
        url, params=[("view", "mRoster"), ("scoringPeriodId", week)],
        cookies=COOKIES, headers=HEADERS, timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    schedule = pro_schedule.get_schedule(year)

    rosters: dict[int, dict] = {}
    for team in data.get("teams", []):
        starters, bench = [], []
        for entry in team.get("roster", {}).get("entries", []):
            player = entry.get("playerPoolEntry", {}).get("player", {})
            projected = actual = None
            for s in player.get("stats", []):
                if s.get("scoringPeriodId") != week:
                    continue
                if s.get("statSourceId") == 1:
                    projected = s["appliedTotal"]
                elif s.get("statSourceId") == 0:
                    actual = s["appliedTotal"]
            row = {
                "player_id": player.get("id"),
                "name": clean_name(player.get("fullName", "?")),
                "position": POSITION_MAP.get(player.get("defaultPositionId"), "?"),
                "opponent": pro_schedule.opponent_label(schedule, player.get("proTeamId"), week),
                "kickoff_at": pro_schedule.kickoff_at(schedule, player.get("proTeamId"), week),
                "projected_points": round(projected, 1) if projected is not None else None,
                # actual_points is None until that player's game for this week is complete --
                # same appliedTotal ESPN's own fantasy scoring uses, works identically for
                # K/D-ST as it does for skill positions (unlike the historical gamelog-based
                # weekly_player_points pipeline, which has no D/ST or reliable K coverage).
                "actual_points": round(actual, 1) if actual is not None else None,
            }
            slot_id = entry.get("lineupSlotId")
            if slot_id in BENCH_SLOTS:
                bench.append(row)
            else:
                slot = STARTING_SLOT_MAP.get(slot_id)
                if slot:
                    row["slot"] = slot
                starters.append(row)
        rosters[team["id"]] = {"starters": starters, "bench": bench}
    return rosters


def get_rosters_for_week(year: int, week: int) -> dict[int, dict]:
    key = (year, week)
    cached = _week_cache.get(key)
    if cached and (time.time() - cached[0]) < CACHE_TTL_SECONDS:
        return cached[1]
    rosters = _fetch_rosters_for_week(year, week)
    _week_cache[key] = (time.time(), rosters)
    return rosters
