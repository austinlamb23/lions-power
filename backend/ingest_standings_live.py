"""Keeps `standings` current for the live season by computing wins/losses/
ties/points_for/points_against directly from the matchups table -- no
separate ESPN call needed, unlike every other ingest_* script, since this is
fully derivable from data ingest_matchups_live.py is already pulling every
3 hours.

final_standing/playoff_wins/playoff_losses are deliberately left untouched
(NULL for a fresh row) -- those are determined only once the season,
including playoffs, is actually over, not derivable from regular-season
matchups alone. Re-running this after they've been set some other way at
season's end won't clobber them; only wins/losses/ties/points_for/
points_against are ever written here.

Usage: venv/bin/python3 ingest_standings_live.py [year]
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "almanac.db"


def compute_and_upsert(con: sqlite3.Connection, year: int) -> int:
    rows = con.execute(
        "SELECT home_team_id, away_team_id, home_score, away_score FROM matchups "
        "WHERE year=? AND is_playoff=0 AND NOT (home_score=0 AND away_score=0)",
        (year,),
    ).fetchall()

    stats: dict[int, dict] = {}
    for home_id, away_id, home_score, away_score in rows:
        for team_id, pf, pa in ((home_id, home_score, away_score), (away_id, away_score, home_score)):
            s = stats.setdefault(team_id, {"wins": 0, "losses": 0, "ties": 0, "points_for": 0.0, "points_against": 0.0})
            s["points_for"] += pf
            s["points_against"] += pa
            if pf > pa:
                s["wins"] += 1
            elif pf < pa:
                s["losses"] += 1
            else:
                s["ties"] += 1

    team_ids = [r[0] for r in con.execute("SELECT team_id FROM teams WHERE year=?", (year,)).fetchall()]
    written = 0
    for team_id in team_ids:
        s = stats.get(team_id, {"wins": 0, "losses": 0, "ties": 0, "points_for": 0.0, "points_against": 0.0})
        con.execute(
            "INSERT INTO standings (year, team_id, wins, losses, ties, points_for, points_against) "
            "VALUES (?,?,?,?,?,?,?) "
            "ON CONFLICT(year, team_id) DO UPDATE SET wins=excluded.wins, losses=excluded.losses, "
            "ties=excluded.ties, points_for=excluded.points_for, points_against=excluded.points_against",
            (year, team_id, s["wins"], s["losses"], s["ties"], round(s["points_for"], 2), round(s["points_against"], 2)),
        )
        written += 1
    con.commit()
    return written


def main() -> None:
    con = sqlite3.connect(DB_PATH)
    year = int(sys.argv[1]) if len(sys.argv) > 1 else con.execute("SELECT MAX(year) FROM seasons").fetchone()[0]
    written = compute_and_upsert(con, year)
    print(f"{year}: {written} standings rows upserted")
    con.close()


if __name__ == "__main__":
    main()
