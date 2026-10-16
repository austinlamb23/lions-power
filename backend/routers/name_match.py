from __future__ import annotations
from fastapi import APIRouter, Depends
from pydantic import BaseModel
import sqlite3
import json
import random
from datetime import date
from database import get_db

router = APIRouter(prefix="/api/games/name-match", tags=["name_match"])

EPOCH = date(2025, 1, 1)
POINTS_PER_CORRECT = 50
PUZZLE_SIZE = 3


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_entry_pool(db: sqlite3.Connection) -> list[dict]:
    rows = db.execute(
        "SELECT TRIM(team_name) as team_name, owner_name "
        "FROM teams WHERE team_name IS NOT NULL AND LENGTH(TRIM(team_name)) > 0 "
        "ORDER BY year, team_id"
    ).fetchall()
    entries = []
    for r in rows:
        name = r["team_name"].upper()
        try:
            name.encode('ascii')
        except UnicodeEncodeError:
            continue  # skip garbled/emoji names
        entries.append({"team_name": name, "owner_name": r["owner_name"]})
    return entries


def get_daily_puzzles(db: sqlite3.Connection) -> list[dict]:
    entries = get_entry_pool(db)
    rng = random.Random(3141592)
    rng.shuffle(entries)
    day_num = (date.today() - EPOCH).days
    idx = (day_num * PUZZLE_SIZE) % len(entries)
    return [entries[(idx + i) % len(entries)] for i in range(PUZZLE_SIZE)]


def get_all_managers(db: sqlite3.Connection) -> list[str]:
    rows = db.execute(
        "SELECT DISTINCT owner_name FROM teams ORDER BY owner_name"
    ).fetchall()
    return [r["owner_name"] for r in rows]


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/players")
def get_players(db: sqlite3.Connection = Depends(get_db)):
    return get_all_managers(db)


@router.get("/today")
def get_today(player: str, db: sqlite3.Connection = Depends(get_db)):
    today = str(date.today())
    puzzles = get_daily_puzzles(db)
    team_names = [p["team_name"] for p in puzzles]

    row = db.execute(
        "SELECT * FROM name_match_sessions WHERE date = ? AND player_name = ?",
        (today, player)
    ).fetchone()

    if not row:
        db.execute(
            "INSERT INTO name_match_sessions (date, player_name, correct_owners, guesses, score, submitted) "
            "VALUES (?, ?, ?, ?, 0, 0)",
            (today, player, json.dumps([p["owner_name"] for p in puzzles]), json.dumps([]))
        )
        db.commit()
        submitted = False
        guesses = []
        score = 0
        results = None
    else:
        submitted = bool(row["submitted"])
        guesses = json.loads(row["guesses"])
        score = row["score"]
        if submitted:
            correct_owners = json.loads(row["correct_owners"])
            results = [
                {
                    "team_name": team_names[i],
                    "your_guess": guesses[i] if i < len(guesses) else None,
                    "correct_owner": correct_owners[i],
                    "correct": guesses[i] == correct_owners[i] if i < len(guesses) else False,
                }
                for i in range(PUZZLE_SIZE)
            ]
        else:
            results = None

    return {
        "date": today,
        "team_names": team_names,
        "managers": get_all_managers(db),
        "submitted": submitted,
        "guesses": guesses if submitted else [],
        "score": score if submitted else None,
        "results": results,
    }


class SubmitRequest(BaseModel):
    player_name: str
    guesses: list[str]  # one owner_name per puzzle, in order


@router.post("/submit")
def submit_guesses(body: SubmitRequest, db: sqlite3.Connection = Depends(get_db)):
    today = str(date.today())

    row = db.execute(
        "SELECT * FROM name_match_sessions WHERE date = ? AND player_name = ?",
        (today, body.player_name)
    ).fetchone()

    if not row:
        return {"error": "Session not found. Load the puzzle first."}

    # Always use the team_names and correct_owners stored at session creation
    puzzles = get_daily_puzzles(db)
    team_names = [p["team_name"] for p in puzzles]
    correct_owners = json.loads(row["correct_owners"])

    if row["submitted"]:
        guesses = json.loads(row["guesses"])
        score = row["score"]
    else:
        guesses = body.guesses[:PUZZLE_SIZE]
        score = sum(
            POINTS_PER_CORRECT for i, g in enumerate(guesses)
            if i < len(correct_owners) and g == correct_owners[i]
        )
        db.execute(
            "UPDATE name_match_sessions SET guesses=?, score=?, submitted=1 WHERE date=? AND player_name=?",
            (json.dumps(guesses), score, today, body.player_name)
        )
        db.commit()

    results = [
        {
            "team_name": team_names[i],
            "your_guess": guesses[i] if i < len(guesses) else None,
            "correct_owner": correct_owners[i],
            "correct": guesses[i] == correct_owners[i] if i < len(guesses) else False,
        }
        for i in range(PUZZLE_SIZE)
    ]

    return {
        "date": today,
        "team_names": team_names,
        "managers": get_all_managers(db),
        "submitted": True,
        "guesses": guesses,
        "score": score,
        "results": results,
    }
