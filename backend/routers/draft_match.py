from __future__ import annotations
from fastapi import APIRouter, Depends
from pydantic import BaseModel
import sqlite3
import random
from datetime import date
from database import get_db

router = APIRouter(prefix="/api/games/draft-match", tags=["draft_match"])

EPOCH = date(2025, 1, 1)

# 2013-2018 draft data was backfilled 2026-07-20, but that day's puzzle was
# already in progress for several players — expanding the pool mid-day would
# shift which entry `day_num % len(entries)` picks and desync their
# in-progress session from what's displayed. Gated to start the day after,
# so today's puzzle finishes on the pool it started with.
EXPANDED_POOL_START = date(2026, 7, 21)


def _pool_min_year() -> int:
    return 2013 if date.today() >= EXPANDED_POOL_START else 2019


def get_draft_years() -> list:
    return list(range(_pool_min_year(), 2026))


STEP_ORDER = ["year", "manager", "standing"]
POINTS = {"year": 75, "manager": 50, "standing": 25}
ROUND_LABELS = ["First", "Second", "Third"]


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_entry_pool(db: sqlite3.Connection) -> list[tuple]:
    rows = db.execute(
        "SELECT DISTINCT year, team_id FROM draft_picks "
        "WHERE year >= ? ORDER BY year, team_id",
        (_pool_min_year(),)
    ).fetchall()
    return [(r["year"], r["team_id"]) for r in rows]


def get_daily_entry(db: sqlite3.Connection) -> tuple:
    entries = get_entry_pool(db)
    rng = random.Random(2718281)
    rng.shuffle(entries)
    day_num = (date.today() - EPOCH).days
    return entries[day_num % len(entries)]


def get_corrected_standing(db: sqlite3.Connection, year: int, team_id: int) -> int:
    row = db.execute(
        "SELECT playoff_wins, final_standing FROM standings WHERE year=? AND team_id=?",
        (year, team_id)
    ).fetchone()
    if row["playoff_wins"] is not None:
        return row["final_standing"]
    # Non-playoff: rank by wins DESC, points_for DESC among non-playoff teams
    non_playoff = db.execute(
        "SELECT team_id FROM standings WHERE year=? AND playoff_wins IS NULL "
        "ORDER BY wins DESC, points_for DESC",
        (year,)
    ).fetchall()
    for i, r in enumerate(non_playoff):
        if r["team_id"] == team_id:
            return 4 + i + 1
    return row["final_standing"]


def build_puzzle(db: sqlite3.Connection, year: int, team_id: int) -> dict:
    picks = db.execute(
        "SELECT player_name FROM draft_picks WHERE year=? AND team_id=? "
        "ORDER BY overall_pick LIMIT 3",
        (year, team_id)
    ).fetchall()
    team = db.execute(
        "SELECT owner_name FROM teams WHERE year=? AND team_id=?",
        (year, team_id)
    ).fetchone()
    standing = get_corrected_standing(db, year, team_id)
    return {
        "picks": [
            {"round": i + 1, "round_label": ROUND_LABELS[i], "player_name": r["player_name"]}
            for i, r in enumerate(picks)
        ],
        "correct_manager": team["owner_name"],
        "correct_standing": standing,
        "correct_year": year,
    }


def get_all_managers(db: sqlite3.Connection) -> list[str]:
    rows = db.execute(
        "SELECT DISTINCT owner_name FROM teams ORDER BY owner_name"
    ).fetchall()
    return [r["owner_name"] for r in rows]


def _current_step(row) -> str:
    if row["year_guess"] is None:
        return "year"
    if row["manager_guess"] is None:
        return "manager"
    if row["standing_guess"] is None:
        return "standing"
    return "done"


def _session_state(row, puzzle: dict) -> dict:
    step = _current_step(row)
    guesses = {"year": row["year_guess"], "manager": row["manager_guess"], "standing": row["standing_guess"]}
    correct = {"year": puzzle["correct_year"], "manager": puzzle["correct_manager"], "standing": puzzle["correct_standing"]}

    steps = {}
    for s in STEP_ORDER:
        revealed = guesses[s] is not None
        steps[s] = {
            "guess": guesses[s] if revealed else None,
            "correct": correct[s] if revealed else None,
            "is_correct": (guesses[s] == correct[s]) if revealed else None,
        }

    return {
        "picks": puzzle["picks"],
        "draft_years": get_draft_years(),
        "step": step,
        "steps": steps,
        "submitted": step == "done",
        "score": row["score"],
    }


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/players")
def get_players(db: sqlite3.Connection = Depends(get_db)):
    return get_all_managers(db)


@router.get("/today")
def get_today(player: str, db: sqlite3.Connection = Depends(get_db)):
    today = str(date.today())
    year, team_id = get_daily_entry(db)
    puzzle = build_puzzle(db, year, team_id)

    row = db.execute(
        "SELECT * FROM draft_match_sessions WHERE date=? AND player_name=?",
        (today, player)
    ).fetchone()

    if not row:
        db.execute(
            "INSERT INTO draft_match_sessions "
            "(date, player_name, correct_manager, correct_standing, correct_year, submitted, score) "
            "VALUES (?,?,?,?,?,0,0)",
            (today, player, puzzle["correct_manager"], puzzle["correct_standing"], puzzle["correct_year"])
        )
        db.commit()
        row = db.execute(
            "SELECT * FROM draft_match_sessions WHERE date=? AND player_name=?",
            (today, player)
        ).fetchone()

    state = _session_state(row, puzzle)
    state["date"] = today
    state["managers"] = get_all_managers(db)
    return state


class StepRequest(BaseModel):
    player_name: str
    step: str  # "year" | "manager" | "standing"
    guess: str


@router.post("/submit-step")
def submit_step(body: StepRequest, db: sqlite3.Connection = Depends(get_db)):
    today = str(date.today())

    row = db.execute(
        "SELECT * FROM draft_match_sessions WHERE date=? AND player_name=?",
        (today, body.player_name)
    ).fetchone()

    if not row:
        return {"error": "Session not found. Load the puzzle first."}

    expected_step = _current_step(row)

    if expected_step != "done" and body.step == expected_step:
        if expected_step == "manager":
            guess_value = body.guess
            correct_value = row["correct_manager"]
        else:  # year or standing — both integer-valued
            try:
                guess_value = int(body.guess)
            except ValueError:
                guess_value = None
            correct_value = row["correct_year"] if expected_step == "year" else row["correct_standing"]

        is_correct = guess_value == correct_value
        new_score = row["score"] + (POINTS[expected_step] if is_correct else 0)
        column = f"{expected_step}_guess"
        submitted_flag = 1 if expected_step == "standing" else 0

        db.execute(
            f"UPDATE draft_match_sessions SET {column}=?, score=? WHERE date=? AND player_name=?",
            (guess_value, new_score, today, body.player_name)
        )
        if submitted_flag:
            db.execute(
                "UPDATE draft_match_sessions SET submitted=1 WHERE date=? AND player_name=?",
                (today, body.player_name)
            )
        db.commit()

        row = db.execute(
            "SELECT * FROM draft_match_sessions WHERE date=? AND player_name=?",
            (today, body.player_name)
        ).fetchone()

    year, team_id = get_daily_entry(db)
    puzzle = build_puzzle(db, year, team_id)

    state = _session_state(row, puzzle)
    state["date"] = today
    state["managers"] = get_all_managers(db)
    return state
