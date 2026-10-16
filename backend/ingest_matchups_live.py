"""Pulls the current season's full matchup schedule (all weeks, played and
unplayed) in a single ESPN request and upserts into `matchups`. Confirmed
live against the real 2026 league: ESPN exposes the whole regular season's
home/away pairings in advance, with score=0.0 and winner="UNDECIDED" for
weeks that haven't happened yet -- so this is safe to run at any point in
the season, not just after games finish.

Separate from the historical ingest_espn.py-style scripts (which don't
exist in this repo at all -- confirmed via search) -- this is Game Room's
own live-data source, meant to be re-run repeatedly via live_ingest.py
during the season, not a one-time historical backfill.

Idempotent via INSERT OR REPLACE keyed on matchups' own PK (year, week,
home_team_id) -- every pull returns the complete authoritative schedule, so
there's no risk of stale rows lingering the way a partial pull might leave.

Usage: venv/bin/python3 ingest_matchups_live.py <year>
"""
from __future__ import annotations

import os
import sqlite3
import sys
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
BASE = "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{year}/segments/0/leagues/{league_id}"


def fetch_schedule(year: int) -> list[dict]:
    url = BASE.format(year=year, league_id=LEAGUE_ID)
    r = requests.get(
        url, params=[("view", "mMatchup"), ("view", "mMatchupScore"), ("view", "mSettings")],
        cookies=COOKIES, headers=HEADERS, timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    if isinstance(data, list):
        data = data[0]
    return data.get("schedule", [])


def ingest_year(con: sqlite3.Connection, year: int) -> int:
    schedule = fetch_schedule(year)
    written = 0
    for m in schedule:
        home, away = m.get("home"), m.get("away")
        if not home or not away or "teamId" not in home or "teamId" not in away:
            continue  # bye slot / incomplete bracket entry (e.g. odd team count in playoffs)
        tier = m.get("playoffTierType", "NONE")
        con.execute(
            "INSERT OR REPLACE INTO matchups "
            "(year, week, home_team_id, away_team_id, home_score, away_score, is_playoff, matchup_type) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (
                year, m["matchupPeriodId"], home["teamId"], away["teamId"],
                home.get("totalPoints", 0.0), away.get("totalPoints", 0.0),
                0 if tier == "NONE" else 1, tier,
            ),
        )
        written += 1
    con.commit()
    return written


def main() -> None:
    year = int(sys.argv[1])
    con = sqlite3.connect(DB_PATH)
    written = ingest_year(con, year)
    con.close()
    print(f"{year}: {written} matchup rows upserted")


if __name__ == "__main__":
    main()
