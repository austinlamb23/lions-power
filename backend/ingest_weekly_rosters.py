"""Backfill weekly box scores (starting lineup + per-player points) for every
completed matchup week, using the `mBoxscore` view's rosterForMatchupPeriod
field.

Separate from ingest_espn.py's team-level standings/matchups pull — this
hits ESPN once PER WEEK (rosterForMatchupPeriod is only populated for the
matchupPeriodId matching the requested scoringPeriodId, confirmed by
testing), not once per season, so it's a heavier pull than the other
ingest scripts. Which (year, week) pairs to fetch comes straight from the
already-ingested `matchups` table rather than guessing a week range.

Only the STARTING lineup is present in rosterForMatchupPeriod — bench
players never appear in this field at all (confirmed: entry count per team
matches the league's starting lineup size exactly, and lineupSlotId is
uniformly 0 for every entry regardless of position, so it can't be used to
recover a real slot/bench distinction — there isn't one to recover here).

2018 has no box score data at all for this league (confirmed empty across
multiple weeks) — sits right at ESPN's platform migration boundary, where
this league's endpoint switches from fantasy.espn.com to
lm-api-reads.fantasy.espn.com. Skipped automatically (empty response, not
an error) rather than special-cased.

Usage: venv/bin/python3 ingest_weekly_rosters.py 2013 2025
"""
from __future__ import annotations

import os
import re
import sqlite3
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

LEAGUE_ID = os.environ["ESPN_LEAGUE_ID"]
SWID = os.environ["ESPN_SWID"]
ESPN_S2 = os.environ["ESPN_S2"]

DB_PATH = Path(__file__).parent.parent / "almanac.db"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
}
COOKIES = {"SWID": SWID, "espn_s2": ESPN_S2}

MODERN_BASE = "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{year}/segments/0/leagues/{league_id}"
HISTORY_BASE = "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/leagueHistory/{league_id}"
MODERN_ENDPOINT_CUTOFF = 2019  # confirmed via direct testing: 401/404 below this year

POSITION_MAP = {1: "QB", 2: "RB", 3: "WR", 4: "TE", 5: "K", 16: "D/ST"}


def clean_name(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def get_pro_team_map() -> dict[int, str]:
    url = "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/2025"
    r = requests.get(url, params={"view": "proTeamSchedules"}, headers=HEADERS, timeout=20)
    r.raise_for_status()
    teams = r.json().get("settings", {}).get("proTeams", [])
    return {t["id"]: t["abbrev"].upper() for t in teams}


def fetch_week_boxscore(year: int, week: int) -> dict | None:
    """Returns the raw league-data dict for this year, or None if this
    year/week genuinely has no box score data (e.g. 2018)."""
    if year >= MODERN_ENDPOINT_CUTOFF:
        url = MODERN_BASE.format(year=year, league_id=LEAGUE_ID)
        params = {"view": "mBoxscore", "scoringPeriodId": week}
    else:
        url = HISTORY_BASE.format(league_id=LEAGUE_ID)
        params = {"seasonId": year, "view": "mBoxscore", "scoringPeriodId": week}

    r = requests.get(url, params=params, cookies=COOKIES, headers=HEADERS, timeout=30)
    r.raise_for_status()
    data = r.json()
    if isinstance(data, list):
        data = data[0]
    return data


def extract_rows(data: dict, year: int, week: int) -> list[tuple]:
    rows = []
    for m in data.get("schedule", []):
        if m.get("matchupPeriodId") != week:
            continue
        for side in ("home", "away"):
            team = m.get(side)
            if not team or "teamId" not in team:
                continue
            team_id = team["teamId"]
            entries = team.get("rosterForMatchupPeriod", {}).get("entries", [])
            for e in entries:
                player = e.get("playerPoolEntry", {}).get("player", {})
                if not player:
                    continue
                player_id = player.get("id")
                player_name = clean_name(player.get("fullName", ""))
                position = POSITION_MAP.get(player.get("defaultPositionId"))
                pro_team_id = player.get("proTeamId")
                points = e.get("playerPoolEntry", {}).get("appliedStatTotal")
                rows.append((year, week, team_id, player_id, player_name, position, pro_team_id, points))
    return rows


def ingest_year(con: sqlite3.Connection, year: int, pro_team_map: dict[int, str]):
    weeks = [r[0] for r in con.execute(
        "SELECT DISTINCT week FROM matchups WHERE year=? ORDER BY week", (year,)
    ).fetchall()]
    if not weeks:
        print(f"--- {year}: no weeks in matchups table, skipping ---")
        return

    print(f"--- {year} ({len(weeks)} weeks) ---")
    con.execute("DELETE FROM weekly_rosters WHERE year=?", (year,))

    total_rows = 0
    empty_weeks = []
    for week in weeks:
        # A championship/final week can span two real NFL weeks, in which
        # case the roster snapshot is filed under scoringPeriodId = week+1
        # (confirmed: week 15 across every year here needed this) rather
        # than the matchupPeriodId itself -- retry with small offsets
        # before concluding a week genuinely has no data (e.g. 2018).
        raw_rows = []
        used_offset = 0
        for offset in (0, 1, 2):
            try:
                data = fetch_week_boxscore(year, week + offset)
            except requests.HTTPError as e:
                print(f"  week {week} (+{offset}): SKIP ({e})")
                continue
            raw_rows = extract_rows(data, year, week)
            if raw_rows:
                used_offset = offset
                break
            time.sleep(0.15)

        if not raw_rows:
            empty_weeks.append(week)
            continue
        if used_offset:
            print(f"  week {week}: found via scoringPeriodId+{used_offset}")

        for (y, w, team_id, player_id, player_name, position, pro_team_id, points) in raw_rows:
            pro_team = pro_team_map.get(pro_team_id)
            con.execute(
                "INSERT OR REPLACE INTO weekly_rosters "
                "(year, week, team_id, player_id, player_name, position, pro_team, points) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (y, w, team_id, player_id, player_name, position, pro_team, points),
            )
        total_rows += len(raw_rows)
        time.sleep(0.15)  # light throttle -- ~15-17 requests per year, no need to hammer

    con.commit()
    if empty_weeks:
        print(f"  {total_rows} rows inserted, weeks with no data: {empty_weeks}")
    else:
        print(f"  {total_rows} rows inserted, all {len(weeks)} weeks had data")


def main():
    start, end = int(sys.argv[1]), int(sys.argv[2])
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS weekly_rosters (
            year INTEGER, week INTEGER, team_id INTEGER, player_id INTEGER,
            player_name TEXT, position TEXT, pro_team TEXT, points REAL,
            PRIMARY KEY (year, week, team_id, player_id)
        )
    """)
    con.commit()

    pro_team_map = get_pro_team_map()
    for year in range(start, end + 1):
        ingest_year(con, year, pro_team_map)
    con.close()


if __name__ == "__main__":
    main()
