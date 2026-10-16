"""Shared helpers for anything keyed off REAL, live matchup/game timing --
Game Room's weekly games (Weekly Predictions, All-Star Roster) plus the
punishment squid game, the weekly digest, and Coach Poll's auto-open/close.
Deliberately separate from Power Rankings' `current_week` table: that's a
manually-set editorial pointer (what week to *display*), not a live signal
of which week's real games are actually in progress, and coupling the two
would create real timing bugs (Power Rankings can get posted mid-week;
everything in this file needs to key off real kickoffs/results instead).
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timedelta, timezone

from auth import now_iso

DEFAULT_LOCK_TIME_ET = "20:15"  # 8:15pm ET, standard Thursday Night Football kickoff
ET_OFFSET_HOURS = 4  # ET is UTC-4 during the NFL season (daylight saving); good enough, not DST-exact


def current_live_week(db: sqlite3.Connection, year: int) -> int:
    """Lowest week with any matchup still at (0, 0) -- ESPN's confirmed
    signature for a not-yet-played matchup. Falls back to the highest known
    week if everything's decided, or 1 if there's no matchup data at all."""
    row = db.execute(
        "SELECT MIN(week) AS week FROM matchups WHERE year=? AND home_score=0 AND away_score=0",
        (year,),
    ).fetchone()
    if row and row["week"] is not None:
        return row["week"]
    row = db.execute("SELECT MAX(week) AS week FROM matchups WHERE year=?", (year,)).fetchone()
    return row["week"] if row and row["week"] is not None else 1


def real_matchups_for_week(db: sqlite3.Connection, year: int, week: int) -> list[dict]:
    rows = db.execute("""
        SELECT m.home_team_id, m.away_team_id, m.home_score, m.away_score,
               ht.team_name AS home_team_name, ht.owner_name AS home_owner_name,
               at.team_name AS away_team_name, at.owner_name AS away_owner_name
        FROM matchups m
        JOIN teams ht ON ht.year=m.year AND ht.team_id=m.home_team_id
        JOIN teams at ON at.year=m.year AND at.team_id=m.away_team_id
        WHERE m.year=? AND m.week=? AND m.is_playoff=0
        ORDER BY m.home_team_id
    """, (year, week)).fetchall()

    out = []
    for r in rows:
        decided = not (r["home_score"] == 0 and r["away_score"] == 0) and r["home_score"] != r["away_score"]
        winner_team_id = None
        if decided:
            winner_team_id = r["home_team_id"] if r["home_score"] > r["away_score"] else r["away_team_id"]
        out.append({
            "home_team_id": r["home_team_id"], "home_team_name": r["home_team_name"], "home_owner_name": r["home_owner_name"],
            "away_team_id": r["away_team_id"], "away_team_name": r["away_team_name"], "away_owner_name": r["away_owner_name"],
            "home_score": r["home_score"], "away_score": r["away_score"],
            "decided": decided, "winner_team_id": winner_team_id,
        })
    return out


def default_lock_at(year: int, week: int) -> str:
    week1_thursday = datetime.strptime(os.environ["SEASON_WEEK1_THURSDAY"], "%Y-%m-%d")
    target_date = week1_thursday + timedelta(weeks=week - 1)
    hour, minute = (int(x) for x in DEFAULT_LOCK_TIME_ET.split(":"))
    local_dt = target_date.replace(hour=hour, minute=minute)
    utc_dt = (local_dt + timedelta(hours=ET_OFFSET_HOURS)).replace(tzinfo=timezone.utc)
    return utc_dt.isoformat()


def get_lock_at(db: sqlite3.Connection, year: int, week: int) -> tuple[str, bool]:
    row = db.execute(
        "SELECT lock_at FROM week_lock_overrides WHERE year=? AND week=?", (year, week)
    ).fetchone()
    if row:
        return row["lock_at"], True
    return default_lock_at(year, week), False


def is_locked(db: sqlite3.Connection, year: int, week: int) -> bool:
    lock_at, _ = get_lock_at(db, year, week)
    return now_iso() > lock_at


def player_locked(kickoff_at: str | None) -> bool:
    """Per-player lock for All-Star Roster -- a player on a bye (kickoff_at is
    None) never locks, since there's no game to start."""
    return kickoff_at is not None and now_iso() > kickoff_at


def week_is_complete(db: sqlite3.Connection, year: int, week: int) -> bool:
    """True once every one of that week's real matchups is decided (a
    nonzero, non-tied score doesn't count as tied-and-undecided -- ESPN
    reports 0-0 for a matchup that hasn't started/finished yet, and ties are
    real, final results, not a sign the week's still in progress)."""
    row = db.execute(
        "SELECT COUNT(*) AS total, "
        "SUM(CASE WHEN home_score=0 AND away_score=0 THEN 1 ELSE 0 END) AS undecided "
        "FROM matchups WHERE year=? AND week=? AND is_playoff=0",
        (year, week),
    ).fetchone()
    return bool(row["total"]) and row["undecided"] == 0
