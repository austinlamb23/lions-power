from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import sqlite3
import json
import random
import re
from datetime import date
from database import get_db

router = APIRouter(prefix="/api/games/hangman", tags=["hangman"])

WRONG_GUESS_LIMIT = 6
EPOCH = date(2025, 1, 1)


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_word_pool(db: sqlite3.Connection) -> list[str]:
    rows = db.execute(
        "SELECT DISTINCT TRIM(team_name) as name FROM teams "
        "WHERE team_name IS NOT NULL AND LENGTH(TRIM(team_name)) > 0"
    ).fetchall()
    names = []
    seen = set()
    for r in rows:
        name = re.sub(r'\s+', ' ', r["name"].upper()).strip()
        try:
            name.encode('ascii')
        except UnicodeEncodeError:
            continue  # skip garbled/emoji names
        if name not in seen:
            seen.add(name)
            names.append(name)
    return sorted(names)


def get_daily_word(db: sqlite3.Connection) -> str:
    words = get_word_pool(db)
    rng = random.Random(8675309)  # fixed seed — same shuffle every run
    rng.shuffle(words)
    day_num = (date.today() - EPOCH).days
    return words[day_num % len(words)]


def mask_word(word: str, guessed_letters: set) -> str:
    return "".join(
        ch if (not ch.isalpha() or ch in guessed_letters) else "_"
        for ch in word
    )


def count_unrevealed(word: str, guessed_letters: set) -> int:
    return sum(1 for ch in word if ch.isalpha() and ch not in guessed_letters)


def calc_score(wrong_guesses: int, unrevealed_at_solve: int) -> int:
    return max(0, 100 + unrevealed_at_solve * 10 - wrong_guesses * 10)


def get_or_create_session(db: sqlite3.Connection, player: str, today: str, word: str) -> dict:
    row = db.execute(
        "SELECT * FROM hangman_sessions WHERE date = ? AND player_name = ?",
        (today, player)
    ).fetchone()
    if row:
        return dict(row)
    db.execute(
        "INSERT INTO hangman_sessions (date, player_name, word, guessed_letters, wrong_guesses, solved, failed, score) "
        "VALUES (?, ?, ?, ?, 0, 0, 0, 0)",
        (today, player, word, json.dumps([]))
    )
    db.commit()
    return dict(db.execute(
        "SELECT * FROM hangman_sessions WHERE date = ? AND player_name = ?",
        (today, player)
    ).fetchone())


def session_to_response(session: dict) -> dict:
    word = session["word"]
    guessed = set(json.loads(session["guessed_letters"]))
    wrong_letters = [l for l in guessed if l not in word]
    game_over = bool(session["solved"] or session["failed"])
    return {
        "date": session["date"],
        "masked_word": mask_word(word, guessed),
        "guessed_letters": sorted(guessed),
        "wrong_letters": wrong_letters,
        "wrong_guesses": session["wrong_guesses"],
        "wrong_guess_limit": WRONG_GUESS_LIMIT,
        "solved": bool(session["solved"]),
        "failed": bool(session["failed"]),
        "score": session["score"] if game_over else None,
        "answer": word if game_over else None,
    }


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/players")
def get_players(db: sqlite3.Connection = Depends(get_db)):
    rows = db.execute(
        "SELECT DISTINCT owner_name FROM teams ORDER BY owner_name"
    ).fetchall()
    return [r["owner_name"] for r in rows]


@router.get("/today")
def get_today(player: str, db: sqlite3.Connection = Depends(get_db)):
    today = str(date.today())
    word = get_daily_word(db)
    session = get_or_create_session(db, player, today, word)
    return session_to_response(session)


class GuessRequest(BaseModel):
    player_name: str
    guess: str  # single letter or full word attempt


@router.post("/guess")
def submit_guess(body: GuessRequest, db: sqlite3.Connection = Depends(get_db)):
    today = str(date.today())
    word = get_daily_word(db)
    session = get_or_create_session(db, body.player_name, today, word)

    if session["solved"] or session["failed"]:
        return session_to_response(session)

    word = session["word"]  # evaluate against the word actually persisted on this session, not a fresh recompute
    guess = body.guess.upper().strip()
    guessed = set(json.loads(session["guessed_letters"]))
    wrong_guesses = session["wrong_guesses"]

    # Full word guess
    if len(guess) > 1:
        if guess == word:
            unrevealed = count_unrevealed(word, guessed)
            score = calc_score(wrong_guesses, unrevealed)
            db.execute(
                "UPDATE hangman_sessions SET solved=1, score=? WHERE date=? AND player_name=?",
                (score, today, body.player_name)
            )
        else:
            wrong_guesses += 1
            failed = 1 if wrong_guesses >= WRONG_GUESS_LIMIT else 0
            db.execute(
                "UPDATE hangman_sessions SET wrong_guesses=?, failed=? WHERE date=? AND player_name=?",
                (wrong_guesses, failed, today, body.player_name)
            )

    # Single letter guess
    else:
        if len(guess) != 1 or not guess.isalpha():
            raise HTTPException(status_code=400, detail="Invalid guess")
        if guess in guessed:
            return session_to_response(session)

        guessed.add(guess)
        if guess in word:
            # Check if this completes the word
            if count_unrevealed(word, guessed) == 0:
                score = calc_score(wrong_guesses, 0)
                db.execute(
                    "UPDATE hangman_sessions SET guessed_letters=?, solved=1, score=? WHERE date=? AND player_name=?",
                    (json.dumps(sorted(guessed)), score, today, body.player_name)
                )
            else:
                db.execute(
                    "UPDATE hangman_sessions SET guessed_letters=? WHERE date=? AND player_name=?",
                    (json.dumps(sorted(guessed)), today, body.player_name)
                )
        else:
            wrong_guesses += 1
            failed = 1 if wrong_guesses >= WRONG_GUESS_LIMIT else 0
            db.execute(
                "UPDATE hangman_sessions SET guessed_letters=?, wrong_guesses=?, failed=? WHERE date=? AND player_name=?",
                (json.dumps(sorted(guessed)), wrong_guesses, failed, today, body.player_name)
            )

    db.commit()
    session = dict(db.execute(
        "SELECT * FROM hangman_sessions WHERE date = ? AND player_name = ?",
        (today, body.player_name)
    ).fetchone())
    return session_to_response(session)
