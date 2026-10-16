"""Runs every step needed to keep the site's live-season data fresh:
matchups, standings (computed from matchups, no separate ESPN call),
transactions, and weekly player points -- plus side bets' auto-resolution
check, which depends on that data being current. Safe to run unattended and
repeatedly -- every ingestion step is independently idempotent (INSERT OR
REPLACE keyed on each table's own PK; see ingest_matchups_live.py and
ingest_weekly_player_points.py's --live mode for why neither does a blanket
per-year DELETE the way the historical backfills do), and each step past
matchups is wrapped so a failure in one never blocks the rest.

draft_picks does NOT run from here -- see ingest_draft.py's own docstring
for why a draft is a one-time backfill, not a recurring sync.

The punishment squid game's weekly elimination does NOT run from here
anymore (moved to weekly_digest.py, its own once-daily 9am ET schedule --
see that file's docstring for why) even though it depends on this same
data; it just doesn't need to react within 3 hours the way side bets do.

Meant to run on a schedule (systemd timer, every few hours during the
season) via lp3-live-ingest.service -- see almanac_schema.md / deploy notes
for the unit files. Cheap to run year-round; no season-awareness needed.

Usage: venv/bin/python3 live_ingest.py [year]
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import ingest_matchups_live
import ingest_standings_live
import ingest_transactions_live
import ingest_weekly_player_points
import side_bets

DB_PATH = Path(__file__).parent.parent / "almanac.db"


def current_year_from_seasons_table(con: sqlite3.Connection) -> int:
    row = con.execute("SELECT MAX(year) AS year FROM seasons").fetchone()
    return row[0]


def main() -> None:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    year = int(sys.argv[1]) if len(sys.argv) > 1 else current_year_from_seasons_table(con)

    print(f"=== live_ingest for {year} ===")
    written = ingest_matchups_live.ingest_year(con, year)
    print(f"matchups: {written} rows upserted")

    try:
        written = ingest_standings_live.compute_and_upsert(con, year)
        print(f"standings: {written} rows upserted")
    except Exception as e:
        print(f"standings: failed ({e})")

    try:
        written = ingest_transactions_live.ingest_year(con, year)
        print(f"transactions: {written} upserted")
    except Exception as e:
        print(f"transactions: failed ({e})")

    ingest_weekly_player_points.ensure_table(con)
    ingest_weekly_player_points.ingest_year_live(con, year, default_truncated=False)
    ingest_weekly_player_points.validate_against_weekly_rosters(con, year)

    try:
        results = side_bets.try_auto_resolve_bets(con)
        for r in results:
            print(f"side bets: {r}")
    except Exception as e:
        print(f"side bets: failed ({e})")

    con.close()


if __name__ == "__main__":
    main()
