import sqlite3

from fastapi import APIRouter, Depends

from database import get_db

router = APIRouter(prefix="/api/rules", tags=["rules"])


@router.get("")
def get_rules(db: sqlite3.Connection = Depends(get_db)):
    rows = db.execute("""
        SELECT id, category, title, text, sort_order, updated_at
        FROM league_rules
        ORDER BY category ASC, sort_order ASC, id ASC
    """).fetchall()

    categories = []
    by_category = {}
    for r in rows:
        cat = r["category"]
        if cat not in by_category:
            by_category[cat] = []
            categories.append(cat)
        by_category[cat].append({
            "id": r["id"],
            "title": r["title"],
            "text": r["text"],
            "updated_at": r["updated_at"],
        })

    return [{"category": cat, "rules": by_category[cat]} for cat in categories]


@router.get("/pending")
def get_pending_changes(db: sqlite3.Connection = Depends(get_db)):
    rows = db.execute("""
        SELECT id, text, proposed_by, status, note, created_at, updated_at
        FROM pending_rule_changes
        ORDER BY
            CASE status WHEN 'pending' THEN 0 WHEN 'approved' THEN 1 ELSE 2 END ASC,
            created_at DESC
    """).fetchall()

    return [
        {
            "id": r["id"],
            "text": r["text"],
            "proposed_by": r["proposed_by"],
            "status": r["status"],
            "note": r["note"],
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
        }
        for r in rows
    ]


@router.get("/shitlist")
def get_shitlist(db: sqlite3.Connection = Depends(get_db)):
    rows = db.execute("""
        SELECT id, owner_name, reason, rank, created_at, updated_at
        FROM shitlist
        ORDER BY rank ASC
    """).fetchall()

    return [
        {
            "id": r["id"],
            "owner_name": r["owner_name"],
            "reason": r["reason"],
            "rank": r["rank"],
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
        }
        for r in rows
    ]
