from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import get_active_owner, get_optional_owner, now_iso
from database import get_db
import game_room_common
import pro_schedule

router = APIRouter(prefix="/api/coach-poll", tags=["coach-poll"])


def _lock_at(year: int, week: int) -> str | None:
    """Coach poll (and Power Rankings) week N is RETROSPECTIVE -- "week 1
    rankings" means the first ranking published reflecting week 1's results,
    not a prediction for week 1's games (that's what week 0/preseason is
    for). So week N's voting window runs until week (N+1)'s real games
    start, not week N's own -- by the time week N's ballot even opens (see
    _has_opened), week N's games are already over. Week 0 falls out of the
    exact same "week + 1" formula for free: it locks at week 1's kickoff,
    since that's when there stops being a "before any games were played"
    state left to rank. None (never locks) only if the schedule has no games
    at all for the relevant week yet."""
    schedule = pro_schedule.get_schedule(year)
    return pro_schedule.earliest_kickoff(schedule, week + 1)


def _is_locked(year: int, week: int) -> bool:
    lock_at = _lock_at(year, week)
    return lock_at is not None and now_iso() > lock_at


def _has_opened(db: sqlite3.Connection, year: int, week: int) -> bool:
    """Week 0 (preseason) has no real prior week to wait on -- it's always
    open (pending its own lock). Week N>=1 doesn't open until week N ITSELF
    is complete, not week N-1 -- see _lock_at's docstring for why: this is a
    retrospective ranking of week N's results, so it can't meaningfully open
    before week N's games have actually finished. This is deliberately
    independent of Power Rankings' current_week pointer -- that's a manual
    editorial "what am I working on" marker, this is a live signal of
    whether the results being ranked actually exist yet."""
    if week == 0:
        return True
    return game_room_common.week_is_complete(db, year, week)


def _power_rankings_published(db: sqlite3.Connection, year: int, week: int) -> bool:
    return db.execute(
        "SELECT 1 FROM power_rankings WHERE year=? AND week=? LIMIT 1", (year, week)
    ).fetchone() is not None


# NOTE: this static-prefixed route must stay registered before the generic
# /{year}/{week} route below -- same Starlette two-segment ordering pitfall
# documented at the top of power_rankings.py.

@router.get("/current-week")
def get_current_open_week(year: int, db: sqlite3.Connection = Depends(get_db)):
    """The single week currently open for coach-poll voting, if any -- weeks
    are sequential and non-overlapping by construction (each one opens only
    once the previous is both complete AND locked, see _has_opened/_lock_at),
    so there's at most one. Deliberately NOT derived from Game Room's
    current-week endpoint by subtracting one -- that's tempting but wrong:
    there's a real blackout window while a week's games are actively being
    played (the previous week already locked at this week's kickoff, but
    this week isn't open yet since it isn't complete), where Game Room's
    forward-looking "current week" has already advanced but no coach-poll
    week is actually open yet. week: null during that blackout, not an
    error -- the frontend should treat it as "nothing to vote on right now,"
    not retry or report a failure."""
    max_week_row = db.execute("SELECT reg_season_weeks FROM seasons WHERE year=?", (year,)).fetchone()
    max_week = max_week_row["reg_season_weeks"] if max_week_row else 17
    for week in range(max_week, -1, -1):
        if _has_opened(db, year, week) and not _is_locked(year, week):
            return {"year": year, "week": week}
    return {"year": year, "week": None}


@router.get("/{year}/{week}")
def get_week(
    year: int, week: int,
    db: sqlite3.Connection = Depends(get_db),
    owner: str | None = Depends(get_optional_owner),
):
    locked = _is_locked(year, week)
    opened = _has_opened(db, year, week)
    # Results stay hidden even after voting closes, until the commissioner
    # publishes Power Rankings for this exact week -- both are meant to
    # reveal to the league at the same moment, on purpose (see
    # almanac_schema.md). ballot_count is NOT part of that -- knowing how
    # many people have voted isn't "the results," same reasoning as All-Star
    # Roster's submitted_count staying visible pre-reveal.
    revealed = _power_rankings_published(db, year, week)

    rows = []
    if revealed:
        rows = db.execute("""
            SELECT cpv.team_id, t.team_name, t.owner_name,
                   AVG(cpv.rank_given) AS consensus_rank,
                   COUNT(*) AS vote_count,
                   SUM(CASE WHEN cpv.rank_given = 1 THEN 1 ELSE 0 END) AS first_place_votes
            FROM coach_poll_votes cpv
            JOIN teams t ON t.year = cpv.year AND t.team_id = cpv.team_id
            WHERE cpv.year = ? AND cpv.week = ?
            GROUP BY cpv.team_id
            ORDER BY consensus_rank ASC
        """, (year, week)).fetchall()

    ballot_count = db.execute(
        "SELECT COUNT(DISTINCT voter_owner) AS c FROM coach_poll_votes WHERE year = ? AND week = ?",
        (year, week)
    ).fetchone()["c"]

    my_ballot = {}
    if owner:
        my_ballot = {
            r["team_id"]: r["rank_given"] for r in db.execute(
                "SELECT team_id, rank_given FROM coach_poll_votes WHERE year=? AND week=? AND voter_owner=?",
                (year, week, owner)
            ).fetchall()
        }

    return {
        "year": year,
        "week": week,
        "lock_at": _lock_at(year, week),
        "locked": locked,
        "voting_open": opened and not locked,
        "revealed": revealed,
        "ballot_count": ballot_count,
        "results": [
            {
                "team_id": r["team_id"],
                "team_name": r["team_name"],
                "owner_name": r["owner_name"],
                "consensus_rank": r["consensus_rank"],
                "vote_count": r["vote_count"],
                "first_place_votes": r["first_place_votes"],
            }
            for r in rows
        ],
        "my_ballot": my_ballot,
    }


class BallotEntry(BaseModel):
    team_id: int
    rank_given: int


class SubmitBallotRequest(BaseModel):
    ballot: list[BallotEntry]


@router.post("/{year}/{week}")
def submit_ballot(
    year: int, week: int,
    body: SubmitBallotRequest,
    db: sqlite3.Connection = Depends(get_db),
    owner: str = Depends(get_active_owner),
):
    if week < 0:
        raise HTTPException(400, "week can't be negative")
    if _is_locked(year, week):
        raise HTTPException(423, "Coach's poll voting is locked — this week's games have already started")
    if not _has_opened(db, year, week):
        raise HTTPException(423, "Coach's poll voting isn't open yet for this week")

    team_ids = {r["team_id"] for r in db.execute(
        "SELECT team_id FROM teams WHERE year = ?", (year,)
    ).fetchall()}
    if not team_ids:
        raise HTTPException(400, f"No teams found for year {year}")

    entry_team_ids = [e.team_id for e in body.ballot]
    if set(entry_team_ids) != team_ids:
        raise HTTPException(400, "Ballot must rank exactly the teams for that year, once each")

    ranks = sorted(e.rank_given for e in body.ballot)
    if ranks != list(range(1, len(team_ids) + 1)):
        raise HTTPException(400, f"Ranks must be 1-{len(team_ids)} with no gaps or duplicates")

    now = now_iso()
    db.execute(
        "DELETE FROM coach_poll_votes WHERE year=? AND week=? AND voter_owner=?",
        (year, week, owner)
    )
    for e in body.ballot:
        db.execute(
            "INSERT INTO coach_poll_votes (year, week, voter_owner, team_id, rank_given, created_at) "
            "VALUES (?,?,?,?,?,?)",
            (year, week, owner, e.team_id, e.rank_given, now)
        )
    db.commit()
    return {"status": "ok"}
