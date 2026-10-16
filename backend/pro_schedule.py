"""Real NFL schedule lookup (not fantasy-league-specific), used to show each
player's real-life opponent for a given week. Backed by ESPN's
proTeamSchedules view, which is season-wide and barely changes once
published, so it gets a much longer cache than roster_pool's 30-min TTL.
"""
from __future__ import annotations

import os
import time
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent / ".env")

SWID = os.environ["ESPN_SWID"]
ESPN_S2 = os.environ["ESPN_S2"]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
}
COOKIES = {"SWID": SWID, "espn_s2": ESPN_S2}
BASE = "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{year}"

CACHE_TTL_SECONDS = 12 * 60 * 60
_cache: dict[int, tuple[float, dict[int, dict]]] = {}


def _fetch(year: int) -> dict[int, dict]:
    url = BASE.format(year=year)
    r = requests.get(url, params=[("view", "proTeamSchedules")], cookies=COOKIES, headers=HEADERS, timeout=30)
    r.raise_for_status()
    data = r.json()

    schedule: dict[int, dict] = {}
    for team in data.get("settings", {}).get("proTeams", []):
        pro_id = team.get("id")
        if not pro_id:
            continue  # id 0 is ESPN's "free agent / no team" sentinel
        games_by_week = {}
        for week_str, games in team.get("proGamesByScoringPeriod", {}).items():
            if not games:
                continue
            g = games[0]
            is_home = g.get("homeProTeamId") == pro_id
            opponent_id = g.get("awayProTeamId") if is_home else g.get("homeProTeamId")
            kickoff_ms = g.get("date")
            games_by_week[int(week_str)] = {
                "opponent_id": opponent_id,
                "is_home": is_home,
                # Real per-game kickoff, straight from ESPN (updates itself if a
                # game gets rescheduled) -- used to lock/reveal All-Star Roster
                # picks per-player instead of one whole-week deadline.
                "kickoff_at": (
                    datetime.fromtimestamp(kickoff_ms / 1000, tz=timezone.utc).isoformat()
                    if kickoff_ms else None
                ),
            }
        schedule[pro_id] = {
            "abbrev": team.get("abbrev", "?"),
            "bye_week": team.get("byeWeek"),
            "games_by_week": games_by_week,
        }
    return schedule


def get_schedule(year: int) -> dict[int, dict]:
    cached = _cache.get(year)
    if cached and (time.time() - cached[0]) < CACHE_TTL_SECONDS:
        return cached[1]
    schedule = _fetch(year)
    _cache[year] = (time.time(), schedule)
    return schedule


def opponent_label(schedule: dict[int, dict], pro_team_id: int, week: int) -> str:
    team = schedule.get(pro_team_id)
    if not team:
        return "?"
    if team.get("bye_week") == week:
        return "BYE"
    game = team.get("games_by_week", {}).get(week)
    if not game:
        return "?"
    opponent = schedule.get(game["opponent_id"], {})
    prefix = "vs" if game["is_home"] else "@"
    return f"{prefix} {opponent.get('abbrev', '?')}"


def kickoff_at(schedule: dict[int, dict], pro_team_id: int, week: int) -> str | None:
    """ISO8601 UTC kickoff time for this player's real team's game that week,
    or None on a bye / no data -- callers should treat None as "never locks"."""
    team = schedule.get(pro_team_id)
    if not team:
        return None
    game = team.get("games_by_week", {}).get(week)
    return game.get("kickoff_at") if game else None


def earliest_kickoff(schedule: dict[int, dict], week: int) -> str | None:
    """The earliest real kickoff across every pro team's game that week --
    i.e. when that week's NFL slate actually starts. None if the schedule
    has no games at all for that week (e.g. it hasn't been announced yet)."""
    times = [
        game["kickoff_at"]
        for team in schedule.values()
        if (game := team.get("games_by_week", {}).get(week)) and game.get("kickoff_at")
    ]
    return min(times) if times else None
