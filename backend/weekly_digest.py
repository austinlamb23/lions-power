"""Weekly digest -- one GroupMe post (well, several sequential ones, since it
runs long) combining: the Weekly Predictions season-long leaderboard, that
week's All-Star Roster results, and the punishment squid game's ask to that
week's lowest scorer.

Runs on its own schedule (lp3-weekly-digest.timer, once daily at 9am ET --
most days it's a no-op since the previous week isn't newly complete yet) --
deliberately NOT live_ingest.py's every-3-hours cadence, since 9am ET was
picked for engagement (people actually awake and checking group chat), not
for being the earliest possible moment the underlying data is ready.

Reuses the punishment squid game's own per-week completion tracking
(punishment_eliminations, keyed on (year, week)) as the "has this week
already been digested" signal too -- eliminating a punishment is just this
digest's last section now, there's no separate state to keep in sync.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import game_room_common
import groupme
import punishment_squid_game
from auth import now_iso
from routers.all_star_roster import compute_week_results
from routers.weekly_predictions import compute_leaderboard


def _format_predictions_leaderboard(standings: list[dict]) -> str:
    lines = ["🎯 Weekly Predictions — Season Leaderboard"]
    if not standings:
        lines.append("No picks graded yet.")
    for i, s in enumerate(standings, 1):
        lines.append(f"{i}. {s['owner_name']} — {s['correct']}/{s['total']}")
    return "\n".join(lines)


def _format_all_star_results(week: int, results: dict) -> str:
    lines = [f"🌟 All-Star Roster — Week {week} Results"]
    if not results.get("graded"):
        lines.append("Not graded yet.")
    else:
        for i, s in enumerate(results["standings"], 1):
            lines.append(f"{i}. {s['owner_name']} — {s['total']} pts")
    return "\n".join(lines)


def _format_elimination_ask(owner_name: str, week: int, score: float, remaining: list[dict]) -> str:
    lines = [
        f"🎲 @{owner_name}, you had the lowest score in week {week} ({score} pts) — punishment squid game time.",
        "",
        "Your job: eliminate ONE of these from the pool. Reply here and tell me which one.",
        "",
    ]
    lines += [f"{i}. {idea['text']}" for i, idea in enumerate(remaining, 1)]
    return "\n".join(lines)


def try_post_weekly_digest(db: sqlite3.Connection, year: int) -> str | None:
    """Call once daily (from its own 9am ET scheduled job). Advances the
    punishment squid game by at most one week per call: finds the earliest
    completed week that hasn't been digested yet, and -- if nothing's
    already pending and more than one punishment remains -- posts the full
    digest and records a pending punishment_eliminations row. Weeks are
    processed strictly in order; a week's elimination must resolve before
    the next week's digest can go out, since that ask is the digest's own
    last section."""
    if not punishment_squid_game.is_locked(db):
        return None

    pending = db.execute("SELECT year, week FROM punishment_eliminations WHERE status='pending'").fetchone()
    if pending:
        return f"elimination already pending for {pending['year']} week {pending['week']}"

    remaining = punishment_squid_game.active_ideas(db)
    if len(remaining) <= 1:
        return "squid game is already down to the final punishment"

    weeks = [r["week"] for r in db.execute(
        "SELECT DISTINCT week FROM matchups WHERE year=? AND is_playoff=0 ORDER BY week", (year,)
    ).fetchall()]

    for week in weeks:
        if db.execute(
            "SELECT 1 FROM punishment_eliminations WHERE year=? AND week=?", (year, week)
        ).fetchone():
            continue
        if not game_room_common.week_is_complete(db, year, week):
            break  # in order -- don't digest a later week before an earlier one is even complete
        result = punishment_squid_game.lowest_scorer(db, year, week)
        if not result:
            break
        owner_name, score = result

        sections = [
            _format_predictions_leaderboard(compute_leaderboard(db, year)),
            _format_all_star_results(week, compute_week_results(db, year, week)),
        ]
        for section in sections:
            groupme.post_long_message(section)

        # The elimination ask posts (and pending row commits) exactly like
        # the old standalone version did -- see punishment_squid_game.py's
        # module docstring for why post-then-commit, not the other order.
        ask_text = _format_elimination_ask(owner_name, week, score, remaining)
        groupme.post_long_message(ask_text, mentions=[(owner_name, f"@{owner_name}")])
        db.execute(
            "INSERT INTO punishment_eliminations (year, week, owner_name, score, status, asked_at) "
            "VALUES (?,?,?,?,'pending',?)",
            (year, week, owner_name, score, now_iso()),
        )
        db.commit()
        return f"posted weekly digest + asked {owner_name} to eliminate one (year {year} week {week}, score {score})"

    return None


DB_PATH = Path(__file__).parent.parent / "almanac.db"


def main() -> None:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    if len(sys.argv) > 1:
        year = int(sys.argv[1])
    else:
        year = con.execute("SELECT MAX(year) AS year FROM seasons").fetchone()["year"]

    result = try_post_weekly_digest(con, year)
    print(result or "nothing to digest yet")
    con.close()


if __name__ == "__main__":
    main()
