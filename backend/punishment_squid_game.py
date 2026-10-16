"""Punishment Squid Game -- the top-13 punishment pool locked in from the
idea-voting phase, with one idea eliminated each week by that week's lowest
real-scoring team, until only one punishment survives (what the season's
actual loser gets).

Locking in freezes punishment_ideas.status/lock_rank -- voting and new
submissions are closed from that point on (see is_locked, used to gate both
the REST endpoints in routers/punishments.py and bot_engine.py's
submit_punishment_idea tool).

The weekly elimination itself is scheduled and posted by weekly_digest.py
(as the last section of its weekly digest, once daily at 9am ET) -- this
module just provides the primitives that orchestration composes:
is_locked/active_ideas/lowest_scorer (plus game_room_common.week_is_complete)
to find and describe the next eliminable week, and handle_possible_reply to
match that week's lowest scorer's GroupMe reply back to one of the active
ideas (via an LLM call in _match_idea -- deliberately conservative, returns
no match rather than guessing, since a wrong guess would eliminate the wrong
punishment in front of the whole league with no undo) and record the
outcome.
"""
from __future__ import annotations

import json
import os
import sqlite3

from openai import OpenAI

import groupme
from auth import now_iso

MODEL = "deepseek-v4-flash"


def is_locked(db: sqlite3.Connection) -> bool:
    return db.execute("SELECT 1 FROM punishment_ideas WHERE status IS NOT NULL LIMIT 1").fetchone() is not None


def active_ideas(db: sqlite3.Connection) -> list[dict]:
    rows = db.execute("SELECT id, text FROM punishment_ideas WHERE status='active' ORDER BY lock_rank").fetchall()
    return [{"id": r["id"], "text": r["text"]} for r in rows]


def lock_in_top_n(db: sqlite3.Connection, n: int = 13) -> dict:
    """One-time action: freezes the current vote standings into
    status/lock_rank. Refuses to run twice -- there's no unlock, since
    votes aren't preserved once submissions/voting close on the frontend."""
    if is_locked(db):
        raise ValueError("The squid game is already locked in.")

    rows = db.execute("""
        SELECT i.id, COALESCE(SUM(v.weight), 0) AS votes
        FROM punishment_ideas i
        LEFT JOIN punishment_votes v ON v.idea_id = i.id
        GROUP BY i.id
        ORDER BY votes DESC, i.created_at ASC
    """).fetchall()

    for rank, row in enumerate(rows, 1):
        status = "active" if rank <= n else "honorable_mention"
        db.execute("UPDATE punishment_ideas SET status=?, lock_rank=? WHERE id=?", (status, rank, row["id"]))
    db.commit()
    return {"active": min(n, len(rows)), "honorable_mention": max(0, len(rows) - n)}


def lowest_scorer(db: sqlite3.Connection, year: int, week: int) -> tuple[str, float] | None:
    """(owner_name, score) for the real team with the fewest points league-wide
    that week -- not the loser of any specific matchup. Ties broken by lowest
    team_id (deterministic, but arbitrary -- real point ties are rare)."""
    rows = db.execute(
        "SELECT home_team_id AS team_id, home_score AS score FROM matchups WHERE year=? AND week=? AND is_playoff=0 "
        "UNION ALL "
        "SELECT away_team_id AS team_id, away_score AS score FROM matchups WHERE year=? AND week=? AND is_playoff=0",
        (year, week, year, week),
    ).fetchall()
    if not rows:
        return None
    lowest = min(rows, key=lambda r: (r["score"], r["team_id"]))
    team = db.execute(
        "SELECT owner_name FROM teams WHERE year=? AND team_id=?", (year, lowest["team_id"])
    ).fetchone()
    if not team:
        return None
    return team["owner_name"], lowest["score"]


def _match_idea(message_text: str, candidates: list[dict]) -> int | None:
    """Conservative LLM match: returns an idea id only when confident exactly
    one candidate is meant, else None. A wrong guess here eliminates the
    wrong punishment live in front of the whole league with no undo, so
    "couldn't tell" must always win over a forced guess."""
    numbered = "\n".join(f"{i + 1}. (id={c['id']}) {c['text']}" for i, c in enumerate(candidates))
    system = (
        "You match a person's casual chat reply to exactly one item in a numbered list, or decide "
        "it's too ambiguous to be sure. Reply with ONLY a JSON object: {\"idea_id\": <id>} if you're "
        "confident which single item they mean (by number, or by clearly describing it), or "
        "{\"idea_id\": null} if the reply doesn't clearly point to exactly one item -- it names none "
        "of them, more than one, is a question, or is unrelated small talk. When in doubt, use null."
    )
    user = f"List:\n{numbered}\n\nTheir reply: {message_text!r}"

    try:
        client = OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com")
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            response_format={"type": "json_object"},
        )
        idea_id = json.loads(response.choices[0].message.content).get("idea_id")
    except Exception:
        return None

    valid_ids = {c["id"] for c in candidates}
    return idea_id if idea_id in valid_ids else None


def has_pending_elimination(db: sqlite3.Connection, owner_name: str) -> bool:
    """Cheap synchronous check the webhook uses to decide whether a message
    should be routed to handle_possible_reply at all, BEFORE requiring the
    bot to be @mentioned -- must stay false for everyone else, or it would
    hijack the normal Gabe Q&A flow for the entire group chat."""
    return db.execute(
        "SELECT 1 FROM punishment_eliminations WHERE owner_name=? AND status='pending'", (owner_name,)
    ).fetchone() is not None


def handle_possible_reply(db: sqlite3.Connection, owner_name: str, message_text: str) -> bool:
    """Called from the GroupMe webhook once has_pending_elimination has
    already confirmed there's an open pending row for owner_name. Returns
    True once it's taken over the message as an elimination attempt (whether
    or not it actually resolved one -- an ambiguous reply gets a clarifying
    question posted back, not silence). Returns False only in the rare race
    where the pending row resolved between the check and this call."""
    pending = db.execute(
        "SELECT year, week FROM punishment_eliminations WHERE owner_name=? AND status='pending'", (owner_name,)
    ).fetchone()
    if not pending:
        return False
    year, week = pending["year"], pending["week"]

    remaining = active_ideas(db)
    if len(remaining) <= 1:
        # Shouldn't normally happen (weekly_digest.py wouldn't have started
        # this), but don't leave a stuck pending row if it does.
        db.execute(
            "UPDATE punishment_eliminations SET status='completed', resolved_at=? WHERE year=? AND week=?",
            (now_iso(), year, week),
        )
        db.commit()
        return True

    idea_id = _match_idea(message_text, remaining)
    if idea_id is None:
        groupme.post_groupme_message(
            f"@{owner_name} I couldn't tell which one you meant — try naming it more specifically, "
            "or just reply with its number from the list above."
        )
        return True

    idea = next(i for i in remaining if i["id"] == idea_id)
    now = now_iso()
    db.execute(
        "UPDATE punishment_ideas SET status='eliminated', eliminated_week=?, eliminated_by=?, eliminated_at=? "
        "WHERE id=?",
        (week, owner_name, now, idea_id),
    )
    db.execute(
        "UPDATE punishment_eliminations SET status='completed', idea_id=?, resolved_at=? WHERE year=? AND week=?",
        (idea_id, now, year, week),
    )
    db.commit()

    still_left = len(remaining) - 1
    if still_left == 1:
        final_idea = next(i for i in remaining if i["id"] != idea_id)
        groupme.post_groupme_message(
            f'Done — "{idea["text"]}" is eliminated. That\'s it, only one punishment survives: '
            f'"{final_idea["text"]}". That\'s what the season\'s loser gets.'
        )
    else:
        groupme.post_groupme_message(f'Done — "{idea["text"]}" is eliminated. {still_left} punishments remain.')
    return True
