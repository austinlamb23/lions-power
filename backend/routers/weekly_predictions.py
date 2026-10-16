from __future__ import annotations

import sqlite3

import requests
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import get_active_owner, get_all_owners, get_optional_owner, now_iso
from database import get_db
from game_room_common import get_lock_at, is_locked, real_matchups_for_week
import roster_pool

router = APIRouter(prefix="/api/weekly-predictions", tags=["weekly-predictions"])

# Display order for a team's starting lineup in the matchup-detail expand view.
SLOT_ORDER = ["QB", "RB", "WR", "TE", "FLEX", "D/ST", "K"]


# NOTE: static-prefixed routes (like /leaderboard/{year}) must stay registered
# before the generic /{year}/{week} route below -- same Starlette two-segment
# ordering pitfall documented at the top of power_rankings.py.

def compute_leaderboard(db: sqlite3.Connection, year: int) -> list[dict]:
    """Season-long standings -- shared with weekly_digest.py's Tuesday
    digest, not just the /leaderboard endpoint below."""
    rows = db.execute("""
        SELECT wp.voter_owner, wp.picked_team_id, m.home_team_id, m.away_team_id, m.home_score, m.away_score
        FROM weekly_predictions wp
        JOIN matchups m ON m.year=wp.year AND m.week=wp.week AND m.home_team_id=wp.home_team_id
        WHERE wp.year=?
    """, (year,)).fetchall()

    correct: dict[str, int] = {}
    total: dict[str, int] = {}
    for r in rows:
        if r["home_score"] == 0 and r["away_score"] == 0:
            continue  # not decided yet
        if r["home_score"] == r["away_score"]:
            continue  # push, nobody credited
        actual_winner = r["home_team_id"] if r["home_score"] > r["away_score"] else r["away_team_id"]
        total[r["voter_owner"]] = total.get(r["voter_owner"], 0) + 1
        if r["picked_team_id"] == actual_winner:
            correct[r["voter_owner"]] = correct.get(r["voter_owner"], 0) + 1

    standings = [
        {"owner_name": o, "correct": correct.get(o, 0), "total": total.get(o, 0)}
        for o in get_all_owners(db) if total.get(o, 0) > 0
    ]
    standings.sort(key=lambda s: (-s["correct"], -s["total"]))
    return standings


@router.get("/leaderboard/{year}")
def leaderboard(year: int, db: sqlite3.Connection = Depends(get_db)):
    return {"year": year, "standings": compute_leaderboard(db, year)}


@router.get("/{year}/{week}")
def get_week(
    year: int, week: int,
    db: sqlite3.Connection = Depends(get_db),
    owner: str | None = Depends(get_optional_owner),
):
    matchups = real_matchups_for_week(db, year, week)
    lock_at, is_override = get_lock_at(db, year, week)
    locked = is_locked(db, year, week)

    my_picks = {}
    if owner:
        my_picks = {
            r["home_team_id"]: r["picked_team_id"] for r in db.execute(
                "SELECT home_team_id, picked_team_id FROM weekly_predictions "
                "WHERE year=? AND week=? AND voter_owner=?", (year, week, owner)
            ).fetchall()
        }

    # Aggregate pick percentages are shown pre-lock too (owner explicitly OK'd this --
    # anonymous split is fine, only WHO picked what needs to stay hidden until lock).
    # Individual identities never appear here at any point; that's a separate, still
    # lock-gated reveal (see all_star_roster.py's all_picks for the analogous pattern).
    consensus = {}
    for m in matchups:
        rows = db.execute(
            "SELECT picked_team_id, COUNT(*) AS c FROM weekly_predictions "
            "WHERE year=? AND week=? AND home_team_id=? GROUP BY picked_team_id",
            (year, week, m["home_team_id"]),
        ).fetchall()
        total = sum(r["c"] for r in rows)
        consensus[m["home_team_id"]] = {
            "total": total,
            "by_team": {
                r["picked_team_id"]: {"count": r["c"], "pct": round(100 * r["c"] / total)}
                for r in rows
            } if total else {},
        }

    # Named picks only reveal once the week is locked -- pre-lock, only the
    # anonymous consensus above is visible (see get_active_owner call sites /
    # all_star_roster.py's all_picks for the analogous pattern).
    all_picks: dict[str, dict[int, int]] = {}
    if locked:
        rows = db.execute(
            "SELECT voter_owner, home_team_id, picked_team_id FROM weekly_predictions "
            "WHERE year=? AND week=?", (year, week),
        ).fetchall()
        for r in rows:
            all_picks.setdefault(r["voter_owner"], {})[r["home_team_id"]] = r["picked_team_id"]

    return {
        "year": year, "week": week,
        "lock_at": lock_at, "is_override": is_override, "locked": locked,
        "matchups": matchups,
        "my_picks": my_picks,
        "consensus": consensus,  # anonymous aggregate, visible regardless of lock
        "all_picks": all_picks,  # named picks, empty until locked
    }


@router.get("/{year}/{week}/matchup/{home_team_id}")
def matchup_detail(year: int, week: int, home_team_id: int, db: sqlite3.Connection = Depends(get_db)):
    """Rosters + real opponent + projected points for both sides of one
    matchup -- not spoiler-sensitive (no owner picks involved), so unlike
    the rest of this router it's visible regardless of lock status."""
    row = db.execute(
        "SELECT home_team_id, away_team_id FROM matchups WHERE year=? AND week=? AND home_team_id=? AND is_playoff=0",
        (year, week, home_team_id),
    ).fetchone()
    if not row:
        raise HTTPException(404, "No matchup found")

    team_names = {
        r["team_id"]: {"team_name": r["team_name"], "owner_name": r["owner_name"]}
        for r in db.execute("SELECT team_id, team_name, owner_name FROM teams WHERE year=?", (year,)).fetchall()
    }

    try:
        rosters = roster_pool.get_rosters_for_week(year, week)
    except requests.RequestException as e:
        raise HTTPException(502, f"Couldn't reach ESPN: {e}")

    def build_side(team_id: int) -> dict:
        starters = rosters.get(team_id, {}).get("starters", [])
        starters = sorted(starters, key=lambda p: SLOT_ORDER.index(p["slot"]) if p.get("slot") in SLOT_ORDER else 99)
        total = sum(p["projected_points"] for p in starters if p["projected_points"] is not None)
        info = team_names.get(team_id, {})
        return {
            "team_id": team_id,
            "team_name": info.get("team_name", "?"),
            "owner_name": info.get("owner_name", "?"),
            "starters": starters,
            "projected_total": round(total, 1),
        }

    return {"home": build_side(row["home_team_id"]), "away": build_side(row["away_team_id"])}


class PredictionPick(BaseModel):
    home_team_id: int
    picked_team_id: int


class SubmitPredictions(BaseModel):
    picks: list[PredictionPick]


@router.post("/{year}/{week}")
def submit(
    year: int, week: int, body: SubmitPredictions,
    db: sqlite3.Connection = Depends(get_db),
    owner: str = Depends(get_active_owner),
):
    if is_locked(db, year, week):
        raise HTTPException(423, "Picks are locked for this week")

    matchups = real_matchups_for_week(db, year, week)
    if not matchups:
        raise HTTPException(400, f"No matchups found for {year} week {week}")

    valid_home_ids = {m["home_team_id"] for m in matchups}
    valid_teams = {m["home_team_id"]: (m["home_team_id"], m["away_team_id"]) for m in matchups}

    submitted_home_ids = {p.home_team_id for p in body.picks}
    if submitted_home_ids != valid_home_ids:
        raise HTTPException(400, "Picks must cover exactly this week's real matchups, once each")

    for p in body.picks:
        home_id, away_id = valid_teams[p.home_team_id]
        if p.picked_team_id not in (home_id, away_id):
            raise HTTPException(400, f"Picked team must be one of the two teams in matchup (home={home_id})")

    now = now_iso()
    db.execute("DELETE FROM weekly_predictions WHERE year=? AND week=? AND voter_owner=?", (year, week, owner))
    for p in body.picks:
        db.execute(
            "INSERT INTO weekly_predictions (year, week, home_team_id, voter_owner, picked_team_id, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (year, week, p.home_team_id, owner, p.picked_team_id, now, now),
        )
    db.commit()
    return {"status": "ok"}
