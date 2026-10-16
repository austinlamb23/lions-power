from fastapi import APIRouter, Depends
from typing import Optional
import sqlite3
import json
from datetime import date, timedelta
from database import get_db

router = APIRouter(prefix="/api/leaderboard", tags=["leaderboard"])

# Shifted back one day from 2025-01-01 on 2026-07-18: the server's system
# clock was UTC instead of America/New_York, so the rotation was flipping at
# 8pm ET instead of midnight ET. Fixed the clock (VM timezone), but the
# rotation had already flipped early to hangman for the evening of 7/18 —
# rather than yank it back, this shift keeps hangman as that evening's bonus
# game and realigns the 3-day cycle from there (7/19 -> name-match, 7/20 ->
# draft-match, 7/21 -> hangman, ...).
EPOCH = date(2024, 12, 31)
GAME_ROTATION = ['hangman', 'name-match', 'draft-match']


def get_today_game() -> str:
    day_num = (date.today() - EPOCH).days
    return GAME_ROTATION[day_num % 3]


@router.get("/today-game")
def today_game():
    return {"game": get_today_game()}


@router.get("/daily")
def daily_leaderboard(player: Optional[str] = None, db: sqlite3.Connection = Depends(get_db)):
    """Today's leaderboard for the day's game. If `player` has completed today's
    game, also reveals everyone's individual guesses (spoiler-safe: locked
    until you've played)."""
    today = str(date.today())
    game = get_today_game()

    if game == 'hangman':
        my_row = db.execute(
            "SELECT solved, failed FROM hangman_sessions WHERE date=? AND player_name=?",
            (today, player)
        ).fetchone() if player else None
        unlocked = bool(my_row and (my_row["solved"] or my_row["failed"]))

        rows = db.execute(
            "SELECT player_name, score, solved, failed, wrong_guesses, guessed_letters "
            "FROM hangman_sessions WHERE date=? AND (solved=1 OR failed=1) "
            "ORDER BY score DESC, player_name",
            (today,)
        ).fetchall()
        out_rows = []
        for r in rows:
            row = {"player": r["player_name"], "score": r["score"]}
            if unlocked:
                row.update({
                    "solved": bool(r["solved"]),
                    "failed": bool(r["failed"]),
                    "wrong_guesses": r["wrong_guesses"],
                    "guessed_letters": json.loads(r["guessed_letters"]),
                })
            out_rows.append(row)
        return {"game": game, "unlocked": unlocked, "rows": out_rows}

    elif game == 'name-match':
        my_row = db.execute(
            "SELECT submitted FROM name_match_sessions WHERE date=? AND player_name=?",
            (today, player)
        ).fetchone() if player else None
        unlocked = bool(my_row and my_row["submitted"])

        rows = db.execute(
            "SELECT player_name, score, guesses, correct_owners FROM name_match_sessions "
            "WHERE date=? AND submitted=1 ORDER BY score DESC, player_name",
            (today,)
        ).fetchall()
        out_rows = []
        team_names = None
        correct_owners = None
        for r in rows:
            row = {"player": r["player_name"], "score": r["score"]}
            if unlocked:
                row["guesses"] = json.loads(r["guesses"])
                if correct_owners is None:
                    correct_owners = json.loads(r["correct_owners"])
            out_rows.append(row)

        if unlocked and rows:
            from routers.name_match import get_daily_puzzles
            team_names = [p["team_name"] for p in get_daily_puzzles(db)]

        result = {"game": game, "unlocked": unlocked, "rows": out_rows}
        if unlocked:
            result["team_names"] = team_names
            result["correct_owners"] = correct_owners
        return result

    else:  # draft-match
        my_row = db.execute(
            "SELECT submitted FROM draft_match_sessions WHERE date=? AND player_name=?",
            (today, player)
        ).fetchone() if player else None
        unlocked = bool(my_row and my_row["submitted"])

        rows = db.execute(
            "SELECT player_name, score, manager_guess, standing_guess, year_guess, "
            "correct_manager, correct_standing, correct_year FROM draft_match_sessions "
            "WHERE date=? AND submitted=1 ORDER BY score DESC, player_name",
            (today,)
        ).fetchall()
        out_rows = []
        correct = None
        for r in rows:
            row = {"player": r["player_name"], "score": r["score"]}
            if unlocked:
                row.update({
                    "manager_guess": r["manager_guess"],
                    "standing_guess": r["standing_guess"],
                    "year_guess": r["year_guess"],
                })
                if correct is None:
                    correct = {
                        "manager": r["correct_manager"],
                        "standing": r["correct_standing"],
                        "year": r["correct_year"],
                    }
            out_rows.append(row)

        result = {"game": game, "unlocked": unlocked, "rows": out_rows}
        if unlocked:
            result["correct"] = correct
        return result


@router.get("/weekly")
def weekly_leaderboard(db: sqlite3.Connection = Depends(get_db)):
    """Same shape as /overall, scoped to the current calendar week (Mon-Sun) —
    resets every Monday rather than accumulating forever."""
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    week_start_str = str(week_start)

    rows = db.execute("""
        SELECT player_name, SUM(score) AS total, COUNT(*) AS games_played
        FROM (
            SELECT player_name, score FROM hangman_sessions WHERE (solved=1 OR failed=1) AND date >= ?
            UNION ALL
            SELECT player_name, score FROM name_match_sessions WHERE submitted=1 AND date >= ?
            UNION ALL
            SELECT player_name, score FROM draft_match_sessions WHERE submitted=1 AND date >= ?
        )
        GROUP BY player_name
        ORDER BY total DESC, player_name
    """, (week_start_str, week_start_str, week_start_str)).fetchall()

    return {
        "week_start": week_start_str,
        "week_end": str(week_start + timedelta(days=6)),
        "rows": [
            {"player": r["player_name"], "total": r["total"], "games_played": r["games_played"]}
            for r in rows
        ],
    }


@router.get("/overall")
def overall_leaderboard(db: sqlite3.Connection = Depends(get_db)):
    rows = db.execute("""
        SELECT player_name, SUM(score) AS total, COUNT(*) AS games_played
        FROM (
            SELECT player_name, score FROM hangman_sessions WHERE solved=1 OR failed=1
            UNION ALL
            SELECT player_name, score FROM name_match_sessions WHERE submitted=1
            UNION ALL
            SELECT player_name, score FROM draft_match_sessions WHERE submitted=1
        )
        GROUP BY player_name
        ORDER BY total DESC, player_name
    """).fetchall()
    return [
        {"player": r["player_name"], "total": r["total"], "games_played": r["games_played"]}
        for r in rows
    ]
