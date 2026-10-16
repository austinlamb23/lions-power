from __future__ import annotations

import os
import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import (
    MIN_PASSWORD_LEN,
    get_active_owner,
    get_all_owners,
    get_optional_owner,
    hash_password,
    make_token,
    now_iso,
    require_commissioner,
    verify_password,
)
from database import get_db
import punishment_squid_game as squid_game

router = APIRouter(prefix="/api/punishments", tags=["punishments"])

IDEA_MAX_LEN = 280
VOTE_BUDGET = 25
MAX_VOTES_PER_IDEA = 3


# ── Auth ─────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    owner_name: str
    password: str


@router.get("/owners")
def list_owners(db: sqlite3.Connection = Depends(get_db)):
    return get_all_owners(db)


@router.post("/auth/login")
def login(body: LoginRequest, db: sqlite3.Connection = Depends(get_db)):
    if body.owner_name not in get_all_owners(db):
        raise HTTPException(400, "Unrecognized owner name")

    row = db.execute(
        "SELECT salt, password_hash FROM punishment_accounts WHERE owner_name=?",
        (body.owner_name,)
    ).fetchone()

    if row is None:
        if len(body.password) < MIN_PASSWORD_LEN:
            raise HTTPException(400, f"Password must be at least {MIN_PASSWORD_LEN} characters")
        salt = os.urandom(16)
        db.execute(
            "INSERT INTO punishment_accounts (owner_name, salt, password_hash, created_at) VALUES (?,?,?,?)",
            (body.owner_name, salt.hex(), hash_password(body.password, salt), now_iso())
        )
        db.commit()
    elif not verify_password(body.password, row["salt"], row["password_hash"]):
        raise HTTPException(401, "Incorrect password")

    return {"owner_name": body.owner_name, "token": make_token(body.owner_name)}


# ── Ideas ────────────────────────────────────────────────────────────────────

class IdeaRequest(BaseModel):
    text: str


@router.get("/ideas")
def list_ideas(db: sqlite3.Connection = Depends(get_db), owner: str | None = Depends(get_optional_owner)):
    locked = squid_game.is_locked(db)
    order_by = "i.lock_rank ASC" if locked else "vote_count DESC, i.created_at ASC"
    rows = db.execute(f"""
        SELECT i.id, i.text, i.submitted_by, i.created_at, COALESCE(SUM(v.weight), 0) AS vote_count,
               i.status, i.lock_rank, i.eliminated_week, i.eliminated_by
        FROM punishment_ideas i
        LEFT JOIN punishment_votes v ON v.idea_id = i.id
        GROUP BY i.id
        ORDER BY {order_by}
    """).fetchall()

    my_weights = {}
    votes_remaining = None
    if owner:
        my_weights = {
            r["idea_id"]: r["weight"] for r in
            db.execute("SELECT idea_id, weight FROM punishment_votes WHERE owner_name=?", (owner,)).fetchall()
        }
        votes_remaining = VOTE_BUDGET - sum(my_weights.values())

    return {
        "locked": locked,
        "ideas": [
            {
                "id": r["id"],
                "text": r["text"],
                "submitted_by": r["submitted_by"],
                "vote_count": r["vote_count"],
                "my_votes": my_weights.get(r["id"], 0),
                "status": r["status"],
                "lock_rank": r["lock_rank"],
                "eliminated_week": r["eliminated_week"],
                "eliminated_by": r["eliminated_by"],
            }
            for r in rows
        ],
        "votes_budget": VOTE_BUDGET,
        "max_votes_per_idea": MAX_VOTES_PER_IDEA,
        "votes_remaining": votes_remaining,
    }


@router.get("/eliminations")
def list_eliminations(db: sqlite3.Connection = Depends(get_db)):
    rows = db.execute("""
        SELECT e.year, e.week, e.owner_name, e.score, e.status, e.asked_at, e.resolved_at,
               i.text AS idea_text
        FROM punishment_eliminations e
        LEFT JOIN punishment_ideas i ON i.id = e.idea_id
        ORDER BY e.year, e.week
    """).fetchall()
    return {"eliminations": [dict(r) for r in rows]}


@router.post("/lock")
def lock_in(db: sqlite3.Connection = Depends(get_db), commissioner: str = Depends(require_commissioner)):
    try:
        result = squid_game.lock_in_top_n(db)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"status": "ok", **result}


@router.get("/vote-totals")
def vote_totals(db: sqlite3.Connection = Depends(get_db)):
    """How much of each manager's vote budget is spent, in aggregate — not
    which ideas they spent it on (that stays private to /ideas' `my_votes`,
    visible only to the logged-in owner themselves)."""
    used = {
        r["owner_name"]: r["total"] for r in db.execute(
            "SELECT owner_name, COALESCE(SUM(weight), 0) AS total FROM punishment_votes GROUP BY owner_name"
        ).fetchall()
    }
    totals = [{"owner_name": o, "votes_used": used.get(o, 0)} for o in get_all_owners(db)]
    totals.sort(key=lambda t: (-t["votes_used"], t["owner_name"]))
    return {"votes_budget": VOTE_BUDGET, "totals": totals}


@router.post("/ideas")
def submit_idea(
    body: IdeaRequest,
    db: sqlite3.Connection = Depends(get_db),
    owner: str = Depends(get_active_owner),
):
    if squid_game.is_locked(db):
        raise HTTPException(423, "The punishment pool is locked in for the season — no new submissions.")

    text = body.text.strip()
    if not text:
        raise HTTPException(400, "Idea text can't be empty")
    if len(text) > IDEA_MAX_LEN:
        raise HTTPException(400, f"Keep it under {IDEA_MAX_LEN} characters")

    db.execute(
        "INSERT INTO punishment_ideas (text, submitted_by, created_at) VALUES (?,?,?)",
        (text, owner, now_iso())
    )
    db.commit()
    return {"status": "ok"}


class VoteRequest(BaseModel):
    votes: int


@router.post("/ideas/{idea_id}/vote")
def set_vote(
    idea_id: int,
    body: VoteRequest,
    db: sqlite3.Connection = Depends(get_db),
    owner: str = Depends(get_active_owner),
):
    if squid_game.is_locked(db):
        raise HTTPException(423, "The punishment pool is locked in for the season — voting is closed.")
    if body.votes < 0 or body.votes > MAX_VOTES_PER_IDEA:
        raise HTTPException(400, f"Votes must be between 0 and {MAX_VOTES_PER_IDEA}")
    if not db.execute("SELECT 1 FROM punishment_ideas WHERE id=?", (idea_id,)).fetchone():
        raise HTTPException(404, "Idea not found")

    row = db.execute(
        "SELECT weight FROM punishment_votes WHERE idea_id=? AND owner_name=?", (idea_id, owner)
    ).fetchone()
    current = row["weight"] if row else 0

    total_used = db.execute(
        "SELECT COALESCE(SUM(weight), 0) AS t FROM punishment_votes WHERE owner_name=?", (owner,)
    ).fetchone()["t"]
    if total_used - current + body.votes > VOTE_BUDGET:
        raise HTTPException(400, "Not enough votes remaining")

    if body.votes == 0:
        if row:
            db.execute("DELETE FROM punishment_votes WHERE idea_id=? AND owner_name=?", (idea_id, owner))
    elif row:
        db.execute(
            "UPDATE punishment_votes SET weight=? WHERE idea_id=? AND owner_name=?",
            (body.votes, idea_id, owner)
        )
    else:
        db.execute(
            "INSERT INTO punishment_votes (idea_id, owner_name, weight, created_at) VALUES (?,?,?,?)",
            (idea_id, owner, body.votes, now_iso())
        )

    db.commit()
    return {"my_votes": body.votes}
