from __future__ import annotations

import sqlite3

import requests
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import get_active_owner, get_all_owners, get_optional_owner, now_iso
from database import get_db
from game_room_common import player_locked
import roster_pool

router = APIRouter(prefix="/api/all-star-roster", tags=["all-star-roster"])

SLOTS = ["QB", "RB1", "RB2", "WR1", "WR2", "TE", "FLEX", "DST", "K"]
SLOT_ELIGIBLE_POSITIONS = {
    "QB": {"QB"}, "RB1": {"RB"}, "RB2": {"RB"},
    "WR1": {"WR"}, "WR2": {"WR"}, "TE": {"TE"},
    "FLEX": {"RB", "WR", "TE"},
    "DST": {"D/ST"}, "K": {"K"},
}
POOL_POSITIONS = {"QB", "RB", "WR", "TE", "K", "D/ST"}
# D/ST and K aren't in the historical weekly_player_points table (that pipeline's gamelog
# source has no per-game data for them) -- their actual points are instead fetched live
# from roster_pool.get_rosters_for_week, which uses ESPN's own fantasy-scoring endpoint
# and computes them identically to skill positions. See _live_kd_points below.
LIVE_SCORED_POSITIONS = {"D/ST", "K"}


def _live_kd_points(year: int, week: int) -> dict[int, float]:
    try:
        rosters = roster_pool.get_rosters_for_week(year, week)
    except requests.RequestException:
        return {}
    points: dict[int, float] = {}
    for roster in rosters.values():
        for p in roster["starters"] + roster["bench"]:
            if p["position"] in LIVE_SCORED_POSITIONS and p.get("actual_points") is not None:
                points[p["player_id"]] = p["actual_points"]
    return points


# NOTE: static-prefixed routes (/pool/{year}/{week}, /leaderboard/{year}) must
# stay registered before the generic /{year}/{week} route below -- same
# Starlette two-segment ordering pitfall documented at the top of
# power_rankings.py.

def _flat_pool(db: sqlite3.Connection, year: int, week: int) -> list[dict]:
    """Week-scoped so each player carries that week's real opponent and
    projected points -- used both by the team-browsing pool view and by
    submit()'s server-side validation (position/real_team_id are re-derived
    from here, never trusted from the client)."""
    team_names = {
        r["team_id"]: {"team_name": r["team_name"], "owner_name": r["owner_name"]}
        for r in db.execute("SELECT team_id, team_name, owner_name FROM teams WHERE year=?", (year,)).fetchall()
    }
    rosters = roster_pool.get_rosters_for_week(year, week)
    out = []
    for team_id, roster in rosters.items():
        team_info = team_names.get(team_id, {})
        for p in roster["starters"] + roster["bench"]:
            if p["position"] in POOL_POSITIONS and p.get("player_id"):
                out.append({
                    "player_id": p["player_id"], "player_name": p["name"],
                    "position": p["position"], "real_team_id": team_id,
                    "real_team_name": team_info.get("team_name", "?"),
                    "real_owner_name": team_info.get("owner_name", "?"),
                    "opponent": p.get("opponent"),
                    "projected_points": p.get("projected_points"),
                    "kickoff_at": p.get("kickoff_at"),
                    "locked": player_locked(p.get("kickoff_at")),
                })
    return out


@router.get("/pool/{year}/{week}")
def get_pool(year: int, week: int, db: sqlite3.Connection = Depends(get_db)):
    try:
        return {"players": _flat_pool(db, year, week)}
    except Exception as e:
        raise HTTPException(502, f"Couldn't reach ESPN: {e}")


@router.get("/leaderboard/{year}")
def leaderboard(year: int, db: sqlite3.Connection = Depends(get_db)):
    rows = db.execute("""
        SELECT asr.voter_owner, asr.week, asr.player_id, asr.position, COALESCE(wpp.points, 0) AS points
        FROM all_star_roster_picks asr
        LEFT JOIN weekly_player_points wpp
            ON wpp.year=asr.year AND wpp.week=asr.week AND wpp.player_id=asr.player_id
        WHERE asr.year=?
    """, (year,)).fetchall()

    kd_points_by_week: dict[int, dict[int, float]] = {}
    for week in {r["week"] for r in rows if r["position"] in LIVE_SCORED_POSITIONS}:
        kd_points_by_week[week] = _live_kd_points(year, week)

    totals: dict[str, float] = {}
    for r in rows:
        points = kd_points_by_week[r["week"]].get(r["player_id"], 0.0) if r["position"] in LIVE_SCORED_POSITIONS else r["points"]
        totals[r["voter_owner"]] = totals.get(r["voter_owner"], 0.0) + points

    standings = [
        {"owner_name": o, "total": round(totals.get(o, 0.0), 2)}
        for o in get_all_owners(db) if o in totals
    ]
    standings.sort(key=lambda s: -s["total"])
    return {"year": year, "standings": standings}


@router.get("/{year}/{week}")
def get_week(
    year: int, week: int,
    db: sqlite3.Connection = Depends(get_db),
    owner: str | None = Depends(get_optional_owner),
):
    # No single week-wide lock here anymore -- each pick locks (and reveals)
    # individually, the moment that player's real game kicks off. Lock status
    # is read straight off each row's OWN stored kickoff_at (captured at pick
    # time in submit(), below) -- never re-derived from the current live
    # roster pool. That's deliberate: a player can be dropped from every real
    # team's roster after being picked (common for D/ST streaming), which
    # would make them vanish from a live pool lookup with no way to tell
    # whether their game has started -- and guessing "locked" in that gap
    # means revealing someone's pick before their game actually started.
    # Reading the pick's own frozen kickoff_at sidesteps that class of bug
    # entirely: it's a pure function of stored data + wall clock, same as
    # Weekly Predictions' is_locked.
    my_picks = {}
    if owner:
        my_picks = {
            r["slot"]: {
                "player_id": r["player_id"], "player_name": r["player_name"],
                "position": r["position"], "real_team_id": r["real_team_id"],
                "locked": player_locked(r["kickoff_at"]),
            }
            for r in db.execute(
                "SELECT slot, player_id, player_name, position, real_team_id, kickoff_at FROM all_star_roster_picks "
                "WHERE year=? AND week=? AND voter_owner=?", (year, week, owner)
            ).fetchall()
        }

    submitted_count = db.execute(
        "SELECT COUNT(DISTINCT voter_owner) AS c FROM all_star_roster_picks WHERE year=? AND week=?",
        (year, week),
    ).fetchone()["c"]

    # Other owners' picks reveal one slot at a time, as soon as that pick's
    # player's real game starts -- not gated by any single whole-week lock.
    all_picks: dict[str, dict] = {}
    rows = db.execute(
        "SELECT voter_owner, slot, player_id, player_name, position, real_team_id, kickoff_at "
        "FROM all_star_roster_picks WHERE year=? AND week=?", (year, week)
    ).fetchall()
    for r in rows:
        if r["voter_owner"] == owner:
            continue  # you always see your own picks via my_picks, lock or not
        if not player_locked(r["kickoff_at"]):
            continue
        all_picks.setdefault(r["voter_owner"], {})[r["slot"]] = {
            "player_id": r["player_id"], "player_name": r["player_name"],
            "position": r["position"], "real_team_id": r["real_team_id"],
        }

    return {
        "year": year, "week": week,
        "my_picks": my_picks,
        "submitted_count": submitted_count,  # always visible
        "all_picks": all_picks,              # grows in as each pick's player kicks off
    }


class RosterPick(BaseModel):
    slot: str
    player_id: int


class SubmitRoster(BaseModel):
    picks: list[RosterPick]


@router.post("/{year}/{week}")
def submit(
    year: int, week: int, body: SubmitRoster,
    db: sqlite3.Connection = Depends(get_db),
    owner: str = Depends(get_active_owner),
):
    submitted_slots = [p.slot for p in body.picks]
    if sorted(submitted_slots) != sorted(SLOTS):
        raise HTTPException(400, f"Roster must fill exactly these slots, once each: {', '.join(SLOTS)}")

    try:
        pool_by_id = {p["player_id"]: p for p in _flat_pool(db, year, week)}
    except Exception as e:
        raise HTTPException(502, f"Couldn't reach ESPN: {e}")

    existing_by_slot = {
        r["slot"]: r for r in db.execute(
            "SELECT slot, player_id, player_name, position, real_team_id, kickoff_at FROM all_star_roster_picks "
            "WHERE year=? AND week=? AND voter_owner=?", (year, week, owner),
        ).fetchall()
    }

    used_players: set[int] = set()
    used_teams: set[int] = set()
    rows_to_insert = []
    for p in body.picks:
        existing = existing_by_slot.get(p.slot)
        unchanged = existing is not None and existing["player_id"] == p.player_id

        # A slot whose CURRENT pick's game already started can't be swapped
        # out for anything else -- that's the whole point of locking it.
        # Resubmitting it unchanged is always fine (harmless no-op). Read off
        # the pick's OWN stored kickoff_at, not a live pool lookup -- see
        # get_week()'s comment for why (a dropped/traded player must stay
        # frozen, not become editable again just because it fell out of the
        # live pool).
        if not unchanged and existing is not None and player_locked(existing["kickoff_at"]):
            raise HTTPException(400, f"{p.slot} is locked — {existing['player_name']}'s game has already started")

        if unchanged:
            player_name, position, real_team_id, kickoff_at = (
                existing["player_name"], existing["position"], existing["real_team_id"], existing["kickoff_at"]
            )
        else:
            player = pool_by_id.get(p.player_id)
            if not player:
                raise HTTPException(400, f"Player {p.player_id} not found in this year's league")
            if player["position"] not in SLOT_ELIGIBLE_POSITIONS[p.slot]:
                raise HTTPException(400, f"{player['player_name']} ({player['position']}) isn't eligible for slot {p.slot}")
            # Can't newly assign a player whose game has already started --
            # that would defeat the whole "pick before you know" premise.
            if player["locked"]:
                raise HTTPException(400, f"{player['player_name']}'s game has already started")
            player_name, position, real_team_id, kickoff_at = (
                player["player_name"], player["position"], player["real_team_id"], player["kickoff_at"]
            )

        if p.player_id in used_players:
            raise HTTPException(400, f"{player_name} picked more than once")
        if real_team_id in used_teams:
            raise HTTPException(400, f"Max one player per real team — {player_name}'s team already used")
        used_players.add(p.player_id)
        used_teams.add(real_team_id)
        rows_to_insert.append((p.slot, p.player_id, player_name, position, real_team_id, kickoff_at))

    now = now_iso()
    db.execute("DELETE FROM all_star_roster_picks WHERE year=? AND week=? AND voter_owner=?", (year, week, owner))
    for slot, player_id, player_name, position, real_team_id, kickoff_at in rows_to_insert:
        db.execute(
            "INSERT INTO all_star_roster_picks "
            "(year, week, voter_owner, slot, player_id, player_name, position, real_team_id, kickoff_at, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (year, week, owner, slot, player_id, player_name, position, real_team_id, kickoff_at, now, now),
        )
    db.commit()
    return {"status": "ok"}


def compute_week_results(db: sqlite3.Connection, year: int, week: int) -> dict:
    """One week's All-Star Roster standings -- shared with weekly_digest.py's
    Tuesday digest, not just the /results endpoint below."""
    graded = db.execute(
        "SELECT 1 FROM weekly_player_points WHERE year=? AND week=? LIMIT 1", (year, week)
    ).fetchone()
    if not graded:
        return {"graded": False}

    rows = db.execute("""
        SELECT asr.voter_owner, asr.player_id, asr.player_name, asr.position, asr.slot, COALESCE(wpp.points, 0) AS points
        FROM all_star_roster_picks asr
        LEFT JOIN weekly_player_points wpp
            ON wpp.year=asr.year AND wpp.week=asr.week AND wpp.player_id=asr.player_id
        WHERE asr.year=? AND asr.week=?
    """, (year, week)).fetchall()

    kd_points = _live_kd_points(year, week) if any(r["position"] in LIVE_SCORED_POSITIONS for r in rows) else {}

    by_owner: dict[str, dict] = {}
    for r in rows:
        points = kd_points.get(r["player_id"], 0.0) if r["position"] in LIVE_SCORED_POSITIONS else r["points"]
        entry = by_owner.setdefault(r["voter_owner"], {"total": 0.0, "players": []})
        entry["total"] += points
        entry["players"].append({"slot": r["slot"], "player_name": r["player_name"], "points": points})

    standings = [
        {"owner_name": o, "total": round(d["total"], 2), "players": sorted(d["players"], key=lambda p: SLOTS.index(p["slot"]))}
        for o, d in by_owner.items()
    ]
    standings.sort(key=lambda s: -s["total"])
    return {"graded": True, "standings": standings}


@router.get("/{year}/{week}/results")
def week_results(year: int, week: int, db: sqlite3.Connection = Depends(get_db)):
    return compute_week_results(db, year, week)
