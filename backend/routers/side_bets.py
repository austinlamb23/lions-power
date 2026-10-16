from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends

from database import get_db

router = APIRouter(prefix="/api/side-bets", tags=["side-bets"])


@router.get("")
def list_side_bets(db: sqlite3.Connection = Depends(get_db)):
    rows = db.execute("""
        SELECT id, description, side_a, side_b, stakes, submitted_by, resolution_note,
               status, winner, resolved_by, resolution_error, created_at, resolved_at
        FROM side_bets
        ORDER BY
            CASE status WHEN 'open' THEN 0 WHEN 'resolved' THEN 1 ELSE 2 END,
            created_at DESC
    """).fetchall()
    return {"bets": [dict(r) for r in rows]}
