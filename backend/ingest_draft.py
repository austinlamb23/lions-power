"""Backfills draft_picks for a season's real ESPN draft -- a one-time
ingest, not part of the recurring live_ingest.py cadence, since a draft
happens once and its round/pick/player/team facts never change afterward
(a later trade doesn't rewrite who originally drafted a player -- that's
tracked in transactions/transaction_items instead).

ESPN's mDraftDetail view gives round/pick/team/keeper but only a bare
playerId per pick -- no name/position/pro team. Those are resolved in one
bulk follow-up call to kona_player_info, filtered to exactly this draft's
player_ids via the X-Fantasy-Filter header (confirmed empirically: a single
request with all ~150 ids resolves all of them, no pagination needed at
this league's size).

season_points/position_finish are deliberately left NULL -- those need the
player's full completed season, not knowable mid-season. A season-end
process (outside this script, not yet built) is responsible for filling
those in once real values exist, same as standings.final_standing.

Usage: venv/bin/python3 ingest_draft.py <year>
"""
from __future__ import annotations

import json
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

POSITION_MAP = {1: "QB", 2: "RB", 3: "WR", 4: "TE", 5: "K", 16: "D/ST"}


def fetch_picks(year: int) -> list[dict]:
    url = BASE.format(year=year, league_id=LEAGUE_ID)
    r = requests.get(url, params=[("view", "mDraftDetail")], cookies=COOKIES, headers=HEADERS, timeout=30)
    r.raise_for_status()
    detail = r.json().get("draftDetail", {})
    if not detail.get("drafted"):
        return []
    return detail.get("picks", [])


def fetch_pro_team_map(year: int) -> dict[int, str]:
    # Deliberately the season-wide URL, NOT the league-scoped BASE used
    # everywhere else in this file -- proTeamSchedules/proTeams live under
    # .../seasons/{year} directly; the league-scoped path returns this
    # league's OWN settings instead, with no proTeams data at all (confirmed
    # by testing: proTeams comes back empty from the league-scoped URL).
    url = f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{year}"
    r = requests.get(url, params={"view": "proTeamSchedules"}, cookies=COOKIES, headers=HEADERS, timeout=30)
    r.raise_for_status()
    teams = r.json().get("settings", {}).get("proTeams", [])
    return {t["id"]: t["abbrev"].upper() for t in teams}


def fetch_player_info(year: int, player_ids: list[int]) -> dict[int, dict]:
    """player_id -> {"name", "position", "pro_team_id"} for every id given,
    in one bulk request via X-Fantasy-Filter (confirmed working for this
    league's full ~150-pick draft in a single call)."""
    url = BASE.format(year=year, league_id=LEAGUE_ID)
    headers = dict(HEADERS)
    headers["X-Fantasy-Filter"] = json.dumps({"players": {"filterIds": {"value": player_ids}}})
    r = requests.get(url, params=[("view", "kona_player_info")], cookies=COOKIES, headers=headers, timeout=30)
    r.raise_for_status()
    out = {}
    for entry in r.json().get("players", []):
        p = entry["player"]
        out[p["id"]] = {
            "name": p.get("fullName", "?"),
            "position": POSITION_MAP.get(p.get("defaultPositionId"), "?"),
            "pro_team_id": p.get("proTeamId"),
        }
    return out


def ingest_year(con: sqlite3.Connection, year: int) -> int:
    picks = fetch_picks(year)
    if not picks:
        print(f"{year}: draft not completed on ESPN yet, nothing to ingest")
        return 0

    player_ids = [p["playerId"] for p in picks]
    player_info = fetch_player_info(year, player_ids)
    pro_team_map = fetch_pro_team_map(year)

    con.execute("DELETE FROM draft_picks WHERE year=?", (year,))
    written = 0
    for p in picks:
        info = player_info.get(p["playerId"], {})
        pro_team = pro_team_map.get(info.get("pro_team_id"))
        con.execute(
            "INSERT INTO draft_picks (year, round_num, round_pick, overall_pick, team_id, player_name, "
            "player_id, keeper, pro_team, position, season_points, position_finish) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,NULL,NULL)",
            (
                year, p["roundId"], p["roundPickNumber"], p["overallPickNumber"], p["teamId"],
                info.get("name", "?"), p["playerId"], int(bool(p.get("keeper"))), pro_team, info.get("position"),
            ),
        )
        written += 1
    con.commit()
    return written


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: ingest_draft.py <year>")
        sys.exit(1)
    year = int(sys.argv[1])
    con = sqlite3.connect(DB_PATH)
    written = ingest_year(con, year)
    print(f"{year}: {written} draft picks upserted")
    con.close()


if __name__ == "__main__":
    main()
