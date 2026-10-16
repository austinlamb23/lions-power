from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import now_iso, require_commissioner
from database import get_db
from game_room_common import current_live_week, get_lock_at

router = APIRouter(prefix="/api/game-room", tags=["game-room"])


@router.get("/current-week")
def get_current_week(year: int, db: sqlite3.Connection = Depends(get_db)):
    return {"year": year, "week": current_live_week(db, year)}


@router.get("/lock/{year}/{week}")
def get_lock(year: int, week: int, db: sqlite3.Connection = Depends(get_db)):
    lock_at, is_override = get_lock_at(db, year, week)
    return {
        "year": year, "week": week,
        "lock_at": lock_at, "is_override": is_override,
        "locked": now_iso() > lock_at,
    }


class SetLockRequest(BaseModel):
    lock_at: str


@router.post("/lock/{year}/{week}")
def set_lock(
    year: int, week: int, body: SetLockRequest,
    db: sqlite3.Connection = Depends(get_db),
    commissioner: str = Depends(require_commissioner),
):
    now = now_iso()
    db.execute(
        "INSERT INTO week_lock_overrides (year, week, lock_at, set_by, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?) "
        "ON CONFLICT(year, week) DO UPDATE SET lock_at=excluded.lock_at, set_by=excluded.set_by, updated_at=excluded.updated_at",
        (year, week, body.lock_at, commissioner, now, now),
    )
    db.commit()
    return {"status": "ok"}


@router.delete("/lock/{year}/{week}")
def clear_lock(
    year: int, week: int,
    db: sqlite3.Connection = Depends(get_db),
    commissioner: str = Depends(require_commissioner),
):
    db.execute("DELETE FROM week_lock_overrides WHERE year=? AND week=?", (year, week))
    db.commit()
    return {"status": "ok"}
