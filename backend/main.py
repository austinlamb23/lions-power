from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import almanac
from routers import hangman
from routers import name_match
from routers import draft_match
from routers import leaderboard
from routers import bot
from routers import punishments
from routers import rules
from routers import power_rankings_roster
from routers import power_rankings
from routers import coach_poll
from routers import forums
from routers import game_room
from routers import weekly_predictions
from routers import all_star_roster
from routers import side_bets
from routers import best_ball
from routers import pod_grades
from routers import pod_episodes
from database import DB_PATH
import sqlite3
import os

IS_PRODUCTION = os.environ.get("ENVIRONMENT") == "production"

app = FastAPI(
    title="Lions Power 3 Almanac API",
    docs_url=None if IS_PRODUCTION else "/docs",
    redoc_url=None if IS_PRODUCTION else "/redoc",
    openapi_url=None if IS_PRODUCTION else "/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server; update for prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def init_game_tables():
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.executescript("""
        CREATE TABLE IF NOT EXISTS hangman_sessions (
            date         TEXT,
            player_name  TEXT,
            word         TEXT,
            guessed_letters TEXT,
            wrong_guesses   INTEGER DEFAULT 0,
            solved          INTEGER DEFAULT 0,
            failed          INTEGER DEFAULT 0,
            score           INTEGER DEFAULT 0,
            PRIMARY KEY (date, player_name)
        );
        CREATE TABLE IF NOT EXISTS name_match_sessions (
            date            TEXT,
            player_name     TEXT,
            correct_owners  TEXT,
            guesses         TEXT,
            score           INTEGER DEFAULT 0,
            submitted       INTEGER DEFAULT 0,
            PRIMARY KEY (date, player_name)
        );
        CREATE TABLE IF NOT EXISTS draft_match_sessions (
            date             TEXT,
            player_name      TEXT,
            correct_manager  TEXT,
            correct_standing INTEGER,
            correct_year     INTEGER,
            manager_guess    TEXT,
            standing_guess   INTEGER,
            year_guess       INTEGER,
            score            INTEGER DEFAULT 0,
            submitted        INTEGER DEFAULT 0,
            PRIMARY KEY (date, player_name)
        );
        CREATE TABLE IF NOT EXISTS punishment_accounts (
            owner_name     TEXT PRIMARY KEY,
            salt           TEXT NOT NULL,
            password_hash  TEXT NOT NULL,
            created_at     TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS punishment_ideas (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            text             TEXT NOT NULL,
            submitted_by     TEXT NOT NULL,
            created_at       TEXT NOT NULL,
            status           TEXT,     -- NULL until locked in; then 'active' | 'honorable_mention' | 'eliminated'
            lock_rank        INTEGER,  -- fixed display rank set once at lock-in time (1=most votes)
            eliminated_week  INTEGER,
            eliminated_by    TEXT,
            eliminated_at    TEXT
        );
        CREATE TABLE IF NOT EXISTS punishment_votes (
            idea_id     INTEGER NOT NULL,
            owner_name  TEXT NOT NULL,
            weight      INTEGER NOT NULL DEFAULT 1,
            created_at  TEXT NOT NULL,
            PRIMARY KEY (idea_id, owner_name)
        );
        CREATE TABLE IF NOT EXISTS punishment_eliminations (
            year        INTEGER NOT NULL,
            week        INTEGER NOT NULL,
            owner_name  TEXT NOT NULL,
            score       REAL,
            status      TEXT NOT NULL DEFAULT 'pending',  -- pending | completed
            idea_id     INTEGER,
            asked_at    TEXT NOT NULL,
            resolved_at TEXT,
            PRIMARY KEY (year, week)
        );
        CREATE TABLE IF NOT EXISTS pod_episodes (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            year          INTEGER NOT NULL,
            week          INTEGER NOT NULL,  -- 0 = preseason, same convention as power_rankings/coach_poll_votes
            title         TEXT NOT NULL,
            youtube_id    TEXT NOT NULL,
            submitted_by  TEXT NOT NULL,
            created_at    TEXT NOT NULL,
            updated_at    TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS pod_room_grades (
            year          INTEGER NOT NULL,
            team_id       INTEGER NOT NULL,
            grader_owner  TEXT NOT NULL,
            category      TEXT NOT NULL,  -- QB | RB | WR | TE | BENCH
            grade         TEXT NOT NULL,  -- letter grade, A+ .. F
            created_at    TEXT NOT NULL,
            updated_at    TEXT NOT NULL,
            PRIMARY KEY (year, team_id, grader_owner, category)
        );
        CREATE TABLE IF NOT EXISTS side_bets (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            description       TEXT NOT NULL,
            side_a            TEXT NOT NULL,   -- owner_name
            side_b            TEXT,            -- owner_name, nullable for a prop bet with no specific counterparty
            stakes            TEXT NOT NULL,
            submitted_by      TEXT NOT NULL,
            resolution_query  TEXT,            -- read-only SQL: one row, one column `winner` -> owner_name | 'PUSH' | no rows/NULL if not yet determinable
            resolution_note   TEXT,            -- human-readable explanation of the resolution logic, always shown alongside the query
            status            TEXT NOT NULL DEFAULT 'open',  -- open | resolved | voided
            winner            TEXT,            -- owner_name | 'PUSH', set once resolved
            resolved_by       TEXT,            -- 'auto' or the commissioner's owner_name
            resolution_error  TEXT,            -- last error trying to auto-run the query, if any -- surfaces a broken query for the commissioner
            created_at        TEXT NOT NULL,
            updated_at        TEXT NOT NULL,
            resolved_at       TEXT
        );
        CREATE TABLE IF NOT EXISTS league_rules (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            category    TEXT NOT NULL,
            title       TEXT,
            text        TEXT NOT NULL,
            sort_order  INTEGER NOT NULL DEFAULT 0,
            created_at  TEXT NOT NULL,
            updated_at  TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS pending_rule_changes (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            text         TEXT NOT NULL,
            proposed_by  TEXT,
            status       TEXT NOT NULL DEFAULT 'pending',
            note         TEXT,
            created_at   TEXT NOT NULL,
            updated_at   TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS shitlist (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_name  TEXT NOT NULL,
            reason      TEXT,
            rank        INTEGER NOT NULL DEFAULT 0,
            created_at  TEXT NOT NULL,
            updated_at  TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS coach_poll_votes (
            year        INTEGER NOT NULL,
            week        INTEGER NOT NULL,
            voter_owner TEXT NOT NULL,
            team_id     INTEGER NOT NULL,
            rank_given  INTEGER NOT NULL,
            created_at  TEXT NOT NULL,
            PRIMARY KEY (year, week, voter_owner, team_id)
        );
        CREATE TABLE IF NOT EXISTS power_rankings (
            year        INTEGER NOT NULL,
            week        INTEGER NOT NULL,
            team_id     INTEGER NOT NULL,
            rank        INTEGER NOT NULL,
            blurb       TEXT,
            image_path  TEXT,
            created_at  TEXT NOT NULL,
            updated_at  TEXT NOT NULL,
            PRIMARY KEY (year, week, team_id)
        );
        CREATE TABLE IF NOT EXISTS power_rankings_drafts (
            year        INTEGER NOT NULL,
            week        INTEGER NOT NULL,
            team_id     INTEGER NOT NULL,
            rank        INTEGER NOT NULL,
            blurb       TEXT,
            image_path  TEXT,
            created_at  TEXT NOT NULL,
            updated_at  TEXT NOT NULL,
            PRIMARY KEY (year, week, team_id)
        );
        CREATE TABLE IF NOT EXISTS current_week (
            id    INTEGER PRIMARY KEY CHECK (id = 1),
            year  INTEGER NOT NULL,
            week  INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS forum_posts (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            title             TEXT NOT NULL,
            body_markdown     TEXT NOT NULL,
            excerpt           TEXT,
            cover_image_path  TEXT,
            cta_url           TEXT,
            cta_label         TEXT,
            submitted_by      TEXT NOT NULL,
            created_at        TEXT NOT NULL,
            updated_at        TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_forum_posts_created_at ON forum_posts(created_at);
        CREATE TABLE IF NOT EXISTS weekly_predictions (
            year           INTEGER NOT NULL,
            week           INTEGER NOT NULL,
            home_team_id   INTEGER NOT NULL,
            voter_owner    TEXT NOT NULL,
            picked_team_id INTEGER NOT NULL,
            created_at     TEXT NOT NULL,
            updated_at     TEXT NOT NULL,
            PRIMARY KEY (year, week, home_team_id, voter_owner)
        );
        CREATE TABLE IF NOT EXISTS all_star_roster_picks (
            year         INTEGER NOT NULL,
            week         INTEGER NOT NULL,
            voter_owner  TEXT NOT NULL,
            slot         TEXT NOT NULL,
            player_id    INTEGER NOT NULL,
            player_name  TEXT NOT NULL,
            position     TEXT NOT NULL,
            real_team_id INTEGER NOT NULL,
            kickoff_at   TEXT,
            created_at   TEXT NOT NULL,
            updated_at   TEXT NOT NULL,
            PRIMARY KEY (year, week, voter_owner, slot)
        );
        CREATE TABLE IF NOT EXISTS week_lock_overrides (
            year       INTEGER NOT NULL,
            week       INTEGER NOT NULL,
            lock_at    TEXT NOT NULL,
            set_by     TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (year, week)
        );
    """)
    con.commit()
    con.close()


app.include_router(almanac.router)
app.include_router(hangman.router)
app.include_router(name_match.router)
app.include_router(draft_match.router)
app.include_router(leaderboard.router)
app.include_router(bot.router)
app.include_router(punishments.router)
app.include_router(rules.router)
app.include_router(power_rankings_roster.router)
app.include_router(power_rankings.router)
app.include_router(coach_poll.router)
app.include_router(forums.router)
app.include_router(game_room.router)
app.include_router(weekly_predictions.router)
app.include_router(all_star_roster.router)
app.include_router(side_bets.router)
app.include_router(best_ball.router)
app.include_router(pod_grades.router)
app.include_router(pod_episodes.router)


@app.get("/")
def root():
    return {"status": "ok", "app": "Lions Power 3 Almanac"}
