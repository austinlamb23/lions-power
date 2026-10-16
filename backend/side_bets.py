"""Side bets -- a freeform library of wagers between owners, added via asking
Gabe in GroupMe (bot_engine.py's add_side_bet tool). Where a bet's outcome is
objectively determinable from the almanac, the model that adds it also writes
a small read-only SQL query that resolves it -- reusing the exact same
schema-aware SQL-writing ability already proven in query_almanac, just aimed
at "who wins" instead of "answer this question." try_auto_resolve_bets (called
from live_ingest.py's existing periodic run) re-runs every open bet's query
each pass; once it returns a determinate winner, the bet auto-resolves and
Gabe announces it publicly in the chat -- visibly, so a wrong call gets
noticed and corrected fast, not silently locked in.

Bets the model can't reduce to a query (subjective calls, e.g. "whose fantasy
team name is funnier") are left with resolution_query=NULL -- those, and any
query that turns out to be wrong, are what the commissioner's manual
resolve_side_bet/void_side_bet tools are for (see bot_engine.py's
COMMISSIONER_TOOLS).
"""
from __future__ import annotations

import sqlite3

from auth import now_iso
from database import DB_PATH
import groupme


def _run_resolution_query(query: str) -> tuple[str | None, str | None]:
    """Runs a stored resolution query read-only. Returns (winner, error) --
    winner is None if not yet determinable (zero rows, or a NULL winner
    column) OR if the query errored (error will be set in that case);
    error is None on a clean run regardless of whether a winner came back."""
    stripped = query.strip().lstrip("(").strip()
    if not stripped[:6].upper().startswith("SELECT") and not stripped[:4].upper().startswith("WITH"):
        return None, "resolution_query must be a SELECT/WITH statement"
    try:
        con = sqlite3.connect(f"file:{DB_PATH.resolve()}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        rows = con.execute(query).fetchmany(2)
        con.close()
    except sqlite3.Error as e:
        return None, f"SQL error: {e}"

    if not rows:
        return None, None
    if len(rows) > 1:
        return None, "query returned more than one row -- must return exactly one row when determinable"
    if "winner" not in rows[0].keys():
        return None, "query's result column must be named 'winner'"
    winner = rows[0]["winner"]
    return (winner if winner else None), None


def validate_resolution_query(query: str) -> str | None:
    """Best-effort validation at bet-creation time, so a broken query is
    caught immediately instead of silently sitting broken until the next
    scheduled check. Returns an error string, or None if it ran cleanly
    (regardless of whether it resolved anything yet -- a real bet's query
    is expected to return no rows until the underlying facts exist)."""
    _, error = _run_resolution_query(query)
    return error


def _announce(text: str) -> None:
    response = groupme.post_groupme_message(text)
    response.raise_for_status()


def try_auto_resolve_bets(db: sqlite3.Connection) -> list[str]:
    """Call periodically (from live_ingest.py). Re-runs every open bet's
    resolution query; resolves and announces any that are now determinate.
    Returns short status strings for logging, one per bet acted on."""
    results = []
    rows = db.execute(
        "SELECT id, description, side_a, side_b, resolution_query FROM side_bets "
        "WHERE status='open' AND resolution_query IS NOT NULL"
    ).fetchall()

    for row in rows:
        winner, error = _run_resolution_query(row["resolution_query"])
        now = now_iso()
        if error:
            db.execute(
                "UPDATE side_bets SET resolution_error=?, updated_at=? WHERE id=?",
                (error, now, row["id"]),
            )
            db.commit()
            results.append(f"bet {row['id']}: query error ({error})")
            continue
        if winner is None:
            continue  # not yet determinable -- try again next pass

        db.execute(
            "UPDATE side_bets SET status='resolved', winner=?, resolved_by='auto', "
            "resolved_at=?, updated_at=?, resolution_error=NULL WHERE id=?",
            (winner, now, now, row["id"]),
        )
        db.commit()

        outcome = "a push" if winner == "PUSH" else f"{winner} wins"
        vs = f"{row['side_a']} vs {row['side_b']}" if row["side_b"] else row["side_a"]
        _announce(
            f'🎲 Side bet resolved ({vs}): "{row["description"]}" — {outcome}. '
            "Auto-resolved from the almanac — if that's wrong, tell Austin to override it."
        )
        results.append(f"bet {row['id']}: resolved ({outcome})")

    return results
