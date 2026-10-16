"""The Pod's "room grades" game (Steve's idea, 2026-09 -- grade every team's
QB/RB/WR/TE room and bench with a letter grade, ahead of a podcast episode
comparing notes). A fixed, small allowlist of co-hosts, not a general site
role -- hardcoded rather than env-configurable since it's this specific
group for this specific segment, not something meant to grow or rotate.

Grading is incremental by design (UPSERT per cell, not an all-or-nothing
ballot like Coach Poll) -- there's no fairness reason to force someone to
grade all 50 cells in one sitting before saving any of them. All 4 graders
see everyone's grades as they come in, including their own -- this is prep
work for people making the episode together, not a reveal-gated public
competition, so there's no reason to hide anything among the four of them.
"""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import get_current_owner, now_iso
from database import get_db

router = APIRouter(prefix="/api/pod-grades", tags=["pod-grades"])

GRADERS = {"Austin Lamb", "Stephen Marshall", "Paul T Knickelbein", "Bubbleface Bob"}
CATEGORIES = ["QB", "RB", "WR", "TE", "BENCH"]
GRADE_SCALE = ["A+", "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D+", "D", "D-", "F"]


def require_grader(owner: str = Depends(get_current_owner)) -> str:
    if owner not in GRADERS:
        raise HTTPException(403, "Only the pod's room-grade crew can do that")
    return owner


@router.get("/graders")
def list_graders():
    return {"graders": sorted(GRADERS), "categories": CATEGORIES, "grade_scale": GRADE_SCALE}


@router.get("/{year}/public")
def get_public_grades(year: int, db: sqlite3.Connection = Depends(get_db)):
    """No login required -- unlike get_grades below, this is meant for the
    public Power Rankings display, not the crew's own grading tool. Just the
    raw grade matrix (team -> category -> {grader: grade}); no my_grades
    concept here since there's no "logged in as" for an anonymous viewer.
    Whatever's been graded so far is what's shown -- no separate "publish"
    step, the crew publishing to Power Rankings IS the reveal."""
    rows = db.execute(
        "SELECT team_id, grader_owner, category, grade FROM pod_room_grades WHERE year=?", (year,)
    ).fetchall()
    grades_by_team: dict[int, dict[str, dict[str, str]]] = {}
    for r in rows:
        grades_by_team.setdefault(r["team_id"], {}).setdefault(r["category"], {})[r["grader_owner"]] = r["grade"]
    return {"year": year, "grades_by_team": grades_by_team}


@router.get("/{year}")
def get_grades(
    year: int,
    db: sqlite3.Connection = Depends(get_db),
    owner: str = Depends(require_grader),
):
    teams = db.execute(
        "SELECT team_id, team_name, owner_name FROM teams WHERE year=? ORDER BY team_id", (year,)
    ).fetchall()
    if not teams:
        raise HTTPException(404, f"No teams found for year {year}")

    rows = db.execute(
        "SELECT team_id, grader_owner, category, grade FROM pod_room_grades WHERE year=?", (year,)
    ).fetchall()

    grades_by_team: dict[int, dict[str, dict[str, str]]] = {}
    my_grades: dict[int, dict[str, str]] = {}
    for r in rows:
        grades_by_team.setdefault(r["team_id"], {}).setdefault(r["category"], {})[r["grader_owner"]] = r["grade"]
        if r["grader_owner"] == owner:
            my_grades.setdefault(r["team_id"], {})[r["category"]] = r["grade"]

    return {
        "year": year,
        "teams": [
            {
                "team_id": t["team_id"], "team_name": t["team_name"], "owner_name": t["owner_name"],
                "grades": grades_by_team.get(t["team_id"], {}),
            }
            for t in teams
        ],
        "my_grades": my_grades,
        "graders_started": sorted({r["grader_owner"] for r in rows}),
    }


class GradeEntry(BaseModel):
    team_id: int
    category: str
    grade: str


class SubmitGrades(BaseModel):
    grades: list[GradeEntry]


@router.post("/{year}")
def submit_grades(
    year: int, body: SubmitGrades,
    db: sqlite3.Connection = Depends(get_db),
    owner: str = Depends(require_grader),
):
    team_ids = {r["team_id"] for r in db.execute("SELECT team_id FROM teams WHERE year=?", (year,)).fetchall()}
    if not team_ids:
        raise HTTPException(400, f"No teams found for year {year}")

    for g in body.grades:
        if g.team_id not in team_ids:
            raise HTTPException(400, f"Team {g.team_id} isn't valid for {year}")
        if g.category not in CATEGORIES:
            raise HTTPException(400, f"category must be one of {CATEGORIES}")
        if g.grade not in GRADE_SCALE:
            raise HTTPException(400, f"grade must be one of {GRADE_SCALE}")

    now = now_iso()
    for g in body.grades:
        db.execute(
            "INSERT INTO pod_room_grades (year, team_id, grader_owner, category, grade, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?) "
            "ON CONFLICT(year, team_id, grader_owner, category) "
            "DO UPDATE SET grade=excluded.grade, updated_at=excluded.updated_at",
            (year, g.team_id, owner, g.category, g.grade, now, now),
        )
    db.commit()
    return {"status": "ok"}
