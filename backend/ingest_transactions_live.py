"""Keeps `transactions`/`transaction_items` current for the live season.
ESPN's mTransactions2 view returns this league's full transaction history in
one call (confirmed: 99 rows for a partial 2026 season, no pagination
needed at this league's size) -- so like ingest_matchups_live.py, this just
re-pulls everything and upserts each time (INSERT OR REPLACE keyed on
transactions.id) rather than tracking an incremental cursor. That also
means a transaction's status/other fields stay correct as ESPN updates them
(e.g. a pending waiver claim that later executes) without any extra logic
here -- the next sync just overwrites it with current truth.

Player names are resolved via the same bulk X-Fantasy-Filter lookup as
ingest_draft.py -- not imported from there, kept self-contained like every
other ingest_*.py script in this repo.

Usage: venv/bin/python3 ingest_transactions_live.py [year]
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


def fetch_transactions(year: int) -> list[dict]:
    url = BASE.format(year=year, league_id=LEAGUE_ID)
    r = requests.get(url, params=[("view", "mTransactions2")], cookies=COOKIES, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json().get("transactions", [])


def fetch_player_names(year: int, player_ids: list[int]) -> dict[int, str]:
    if not player_ids:
        return {}
    url = BASE.format(year=year, league_id=LEAGUE_ID)
    headers = dict(HEADERS)
    headers["X-Fantasy-Filter"] = json.dumps({"players": {"filterIds": {"value": player_ids}}})
    r = requests.get(url, params=[("view", "kona_player_info")], cookies=COOKIES, headers=headers, timeout=30)
    r.raise_for_status()
    return {entry["player"]["id"]: entry["player"].get("fullName", "?") for entry in r.json().get("players", [])}


def _is_real_move(t: dict) -> bool:
    """Matches the convention the historical (2019-2025) data was ingested
    under -- see almanac_schema.md's transactions/transaction_items note.
    Only completed moves, never negotiation noise: a pending/declined/
    canceled trade offer between two other owners is private to them, not
    something this almanac (or Gabe, who queries it directly with no
    per-owner scoping) should ever be able to surface. WAIVER/FREEAGENT rows
    that failed or are still pending are excluded the same way -- only
    'EXECUTED' ones actually happened. TRADE_ACCEPT is the one type that's
    kept regardless of its status field (historically seen as both NULL and
    'EXECUTED') since that type by itself already means the trade went
    through; TRADE_PROPOSAL/TRADE_DECLINE/TRADE_UPHOLD/ROSTER/FUTURE_ROSTER
    never appear in the historical data at all and are dropped entirely."""
    t_type = t.get("type")
    if t_type == "TRADE_ACCEPT":
        return True
    if t_type in ("WAIVER", "FREEAGENT"):
        return t.get("status") == "EXECUTED"
    return False


def ingest_year(con: sqlite3.Connection, year: int) -> int:
    txns = [t for t in fetch_transactions(year) if _is_real_move(t)]
    if not txns:
        return 0

    player_ids = sorted({
        item["playerId"] for t in txns for item in t.get("items", []) if item.get("playerId")
    })
    names = fetch_player_names(year, player_ids)

    written = 0
    for t in txns:
        con.execute(
            "INSERT OR REPLACE INTO transactions (id, year, week, team_id, type, status, "
            "related_transaction_id, bid_amount, date) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                t["id"], year, t.get("scoringPeriodId"), t.get("teamId"), t.get("type"),
                t.get("status"), t.get("relatedTransactionId"), t.get("bidAmount", 0), t.get("processDate"),
            ),
        )
        con.execute("DELETE FROM transaction_items WHERE transaction_id=?", (t["id"],))
        for seq, item in enumerate(t.get("items", [])):
            con.execute(
                "INSERT INTO transaction_items (transaction_id, item_seq, item_type, player_id, "
                "player_name, from_team_id, to_team_id) VALUES (?,?,?,?,?,?,?)",
                (
                    t["id"], seq, item.get("type"), item.get("playerId"),
                    names.get(item.get("playerId"), "?"), item.get("fromTeamId"), item.get("toTeamId"),
                ),
            )
        written += 1
    con.commit()
    return written


def main() -> None:
    con = sqlite3.connect(DB_PATH)
    year = int(sys.argv[1]) if len(sys.argv) > 1 else con.execute("SELECT MAX(year) FROM seasons").fetchone()[0]
    written = ingest_year(con, year)
    print(f"{year}: {written} transactions upserted")
    con.close()


if __name__ == "__main__":
    main()
