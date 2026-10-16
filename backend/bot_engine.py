import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from openai import OpenAI

import punishment_squid_game
import side_bets
from database import DB_PATH


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# Schema + business rules live in a shared file, not hardcoded here, because
# the same content is also read by mcp-server/index.js (a separate local MCP
# server for querying the almanac from Claude Code/Desktop) — one source of
# truth for both consumers, so a schema change only needs updating in one
# place instead of silently drifting out of sync (this bit us twice already:
# the division column and the draft-enrichment columns both shipped without
# this file being updated, until the bot's wrong/missing answers gave it away).
SCHEMA_PATH = Path(__file__).parent.parent / "almanac_schema.md"
SCHEMA_AND_RULES = SCHEMA_PATH.read_text()

SYSTEM_PROMPT = f"""You are Gabe, the Lions Power 3 fantasy football league's data
assistant, living in the league's GroupMe chat. You answer questions about league
history by querying a SQLite database via the query_almanac tool. Always use the
tool to look up data — never answer from memory or guess numbers.

{SCHEMA_AND_RULES}

Tone: you're a member of this group chat with perfect recall of the receipts, not a
customer service bot. Dry, a little cocky when the data backs it up, happy to roast
someone with their own stats. Personality is seasoning on top of the data — never
sacrifice accuracy for a joke, and never invent a detail nobody asked about just to
sound clever.

Length: answer like a text message, not a report. One to three sentences for a
typical question — name the person/team and the number, then stop. Only go longer
if the question genuinely asks for a list or multiple data points (e.g. "rank
everyone by championships"), and keep each line in that list tight. No preamble
("Let me check that"), no restating the question, no wrap-up sentence at the end.

Punishment ideas: anyone can submit one for the pre-season punishment pool via the
submit_punishment_idea tool — if someone asks you to add/submit a punishment idea
(e.g. "add this as a punishment idea: ...", "submit an idea: ..."), use that tool.
The submitted_by field must be the ACTUAL sender of the current message (see the
"Message sender" note below, resolved through the nickname list above to their
canonical owner_name) — never credit the idea to a different person just because
another name appears somewhere in their message text. IMPORTANT — this is a write
action, so unlike read-only questions (where guessing the closest name is fine),
do NOT guess here: if the message sender's name doesn't clearly and confidently
match a specific person on the nickname list or roster, do NOT call the tool and
do NOT pick an arbitrary owner_name as a fallback — tell them you don't recognize
their GroupMe name as a league member and can't attribute the idea, and suggest
they submit it on the website instead. After a successful submission, confirm it
back casually (what got added, who it's credited to) — don't recite the raw tool
output.

Side bets: anyone can log a wager between (usually two) owners via the
add_side_bet tool — e.g. "add a side bet: Austin bets Mark $20 the Chiefs miss
the playoffs" or "side bet — Josh vs Dan, loser buys dinner, whoever's team
scores more this week". side_a is required, side_b is optional (omit it for a
prop bet with no specific counterparty, e.g. betting on a real NFL outcome).
Resolve both names through the nickname list to their canonical owner_name —
same no-guessing rule as punishment ideas: if a named party isn't a clear,
confident match to a league member, don't call the tool, ask for clarification
instead. stakes is required; if the message genuinely doesn't say what's on
the line, use "bragging rights" rather than leaving it blank.

Try to also give resolution_query + resolution_note together whenever the bet's
outcome is something the almanac schema above can objectively determine once
the underlying facts exist (a matchup score, a season's final standings, a
weekly points total, a draft position, etc.) — this is the SAME schema you use
for query_almanac, just used to define a condition instead of answer a
question directly. resolution_query must be a single read-only SELECT that
returns AT MOST one row with exactly one column named `winner`: the winning
side's exact owner_name once determinable, the literal string 'PUSH' for a
tie/wash, or zero rows (not an error) while it's genuinely not yet
determinable (e.g. the relevant week hasn't happened, or the season isn't
over). Keep it simple and defensive — a wrong query would call a real bet
incorrectly in front of the whole league, so if you're not confident you can
express the condition correctly and robustly in SQL, leave resolution_query
and resolution_note both out entirely rather than force something fragile;
the commissioner resolves those manually instead, that's expected and fine,
not a failure. Bets about something the schema could never determine (a
subjective judgment call, an event outside the league/ESPN data entirely) also
just skip resolution_query. After adding, confirm back casually including
whether it'll auto-resolve or needs a manual call later — don't recite raw
tool output or paste the SQL into the chat.
"""


def query_almanac(sql: str) -> str:
    """Run a read-only SQL query against the league almanac database."""
    stripped = sql.strip().lstrip("(").strip()
    if not stripped[:6].upper().startswith("SELECT") and not stripped[:4].upper().startswith("WITH"):
        return "Error: only SELECT / WITH queries are allowed."

    try:
        con = sqlite3.connect(f"file:{DB_PATH.resolve()}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        rows = con.execute(sql).fetchmany(200)
        result = [dict(r) for r in rows]
        con.close()
    except sqlite3.Error as e:
        return f"SQL error: {e}"

    return json.dumps(result, default=str)


# ── Commissioner-only rules/pending-changes tools ────────────────────────────
# These mutate league_rules / pending_rule_changes. They're deliberately kept
# out of the TOOLS list entirely (see COMMISSIONER_TOOLS below) unless the
# caller is verified as the commissioner — the model literally has no way to
# invoke them otherwise, since the API only allows calling tools it was told
# about for that request. That's the actual security boundary, not a prompt
# instruction the model could be talked out of.

def _write_db() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


def add_rule(category: str, text: str, title: str = None, sort_order: int = 0) -> str:
    con = _write_db()
    now = _now_iso()
    cur = con.execute(
        "INSERT INTO league_rules (category, title, text, sort_order, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?)",
        (category, title, text, sort_order, now, now),
    )
    con.commit()
    rule_id = cur.lastrowid
    con.close()
    return f"Rule added (id={rule_id}, category={category!r})."


def update_rule(rule_id: int, category: str = None, title: str = None,
                 text: str = None, sort_order: int = None) -> str:
    fields, values = [], []
    for col, val in (("category", category), ("title", title), ("text", text), ("sort_order", sort_order)):
        if val is not None:
            fields.append(f"{col}=?")
            values.append(val)
    if not fields:
        return "Error: no fields given to update."
    fields.append("updated_at=?")
    values.append(_now_iso())
    values.append(rule_id)

    con = _write_db()
    cur = con.execute(f"UPDATE league_rules SET {', '.join(fields)} WHERE id=?", values)
    con.commit()
    updated = cur.rowcount
    con.close()
    return f"Rule {rule_id} updated." if updated else f"Error: no rule with id={rule_id}."


def delete_rule(rule_id: int) -> str:
    con = _write_db()
    cur = con.execute("DELETE FROM league_rules WHERE id=?", (rule_id,))
    con.commit()
    deleted = cur.rowcount
    con.close()
    return f"Rule {rule_id} deleted." if deleted else f"Error: no rule with id={rule_id}."


def add_pending_change(text: str, proposed_by: str = None, note: str = None) -> str:
    con = _write_db()
    now = _now_iso()
    cur = con.execute(
        "INSERT INTO pending_rule_changes (text, proposed_by, status, note, created_at, updated_at) "
        "VALUES (?,?,'pending',?,?,?)",
        (text, proposed_by, note, now, now),
    )
    con.commit()
    change_id = cur.lastrowid
    con.close()
    return f"Pending change added (id={change_id}, status=pending)."


def update_pending_change(change_id: int, status: str = None, text: str = None,
                           note: str = None, proposed_by: str = None) -> str:
    if status is not None and status not in ("pending", "approved", "rejected"):
        return "Error: status must be one of pending, approved, rejected."

    fields, values = [], []
    for col, val in (("status", status), ("text", text), ("note", note), ("proposed_by", proposed_by)):
        if val is not None:
            fields.append(f"{col}=?")
            values.append(val)
    if not fields:
        return "Error: no fields given to update."
    fields.append("updated_at=?")
    values.append(_now_iso())
    values.append(change_id)

    con = _write_db()
    cur = con.execute(f"UPDATE pending_rule_changes SET {', '.join(fields)} WHERE id=?", values)
    con.commit()
    updated = cur.rowcount
    con.close()
    return f"Pending change {change_id} updated." if updated else f"Error: no pending change with id={change_id}."


def delete_pending_change(change_id: int) -> str:
    con = _write_db()
    cur = con.execute("DELETE FROM pending_rule_changes WHERE id=?", (change_id,))
    con.commit()
    deleted = cur.rowcount
    con.close()
    return f"Pending change {change_id} deleted." if deleted else f"Error: no pending change with id={change_id}."


# The shit list is a real 1-based ranking (rank 1 = worst offender, at the
# top) that's always kept contiguous 1..N — no gaps, no duplicate ranks. The
# shifting math below happens in Python against a single connection/
# transaction, not left for the model to compute, since getting it wrong
# would corrupt the ordering (duplicate or skipped ranks).

def add_to_shitlist(owner_name: str, reason: str = None, rank: int = None) -> str:
    con = _write_db()
    now = _now_iso()
    count = con.execute("SELECT COUNT(*) FROM shitlist").fetchone()[0]

    if rank is None:
        rank = count + 1
    else:
        rank = max(1, min(rank, count + 1))
        con.execute("UPDATE shitlist SET rank = rank + 1, updated_at=? WHERE rank >= ?", (now, rank))

    cur = con.execute(
        "INSERT INTO shitlist (owner_name, reason, rank, created_at, updated_at) VALUES (?,?,?,?,?)",
        (owner_name, reason, rank, now, now),
    )
    con.commit()
    entry_id = cur.lastrowid
    con.close()
    return f"{owner_name} added to the shit list at #{rank} (id={entry_id})."


def update_shitlist_entry(entry_id: int, owner_name: str = None, reason: str = None, rank: int = None) -> str:
    con = _write_db()
    row = con.execute("SELECT rank FROM shitlist WHERE id=?", (entry_id,)).fetchone()
    if row is None:
        con.close()
        return f"Error: no shit list entry with id={entry_id}."
    old_rank = row[0]
    now = _now_iso()
    moved = False

    if rank is not None:
        count = con.execute("SELECT COUNT(*) FROM shitlist").fetchone()[0]
        new_rank = max(1, min(rank, count))
        if new_rank < old_rank:
            con.execute(
                "UPDATE shitlist SET rank = rank + 1, updated_at=? WHERE rank >= ? AND rank < ?",
                (now, new_rank, old_rank),
            )
            moved = True
        elif new_rank > old_rank:
            con.execute(
                "UPDATE shitlist SET rank = rank - 1, updated_at=? WHERE rank <= ? AND rank > ?",
                (now, new_rank, old_rank),
            )
            moved = True
        if moved:
            con.execute("UPDATE shitlist SET rank=?, updated_at=? WHERE id=?", (new_rank, now, entry_id))

    fields, values = [], []
    for col, val in (("owner_name", owner_name), ("reason", reason)):
        if val is not None:
            fields.append(f"{col}=?")
            values.append(val)
    if fields:
        fields.append("updated_at=?")
        values.append(now)
        values.append(entry_id)
        con.execute(f"UPDATE shitlist SET {', '.join(fields)} WHERE id=?", values)
    elif not moved:
        con.close()
        return "Error: no fields given to update."

    con.commit()
    con.close()
    return f"Shit list entry {entry_id} updated."


def delete_shitlist_entry(entry_id: int) -> str:
    con = _write_db()
    row = con.execute("SELECT rank FROM shitlist WHERE id=?", (entry_id,)).fetchone()
    if row is None:
        con.close()
        return f"Error: no shit list entry with id={entry_id}."
    deleted_rank = row[0]
    now = _now_iso()
    con.execute("DELETE FROM shitlist WHERE id=?", (entry_id,))
    con.execute("UPDATE shitlist SET rank = rank - 1, updated_at=? WHERE rank > ?", (now, deleted_rank))
    con.commit()
    con.close()
    return f"Shit list entry {entry_id} deleted, rankings closed up behind it."


# ── Punishment idea submission — open to everyone, not commissioner-gated ───
# (lives in the general TOOLS list further down, not COMMISSIONER_TOOLS)

IDEA_MAX_LEN = 280
INACTIVE_OWNERS = {"Alex Ziolkowski", "Gabe McGill"}


def submit_punishment_idea(idea_text: str, submitted_by: str) -> str:
    idea_text = idea_text.strip()
    if not idea_text:
        return "Error: idea text can't be empty."
    if len(idea_text) > IDEA_MAX_LEN:
        return f"Error: keep the idea under {IDEA_MAX_LEN} characters."

    con = _write_db()
    if punishment_squid_game.is_locked(con):
        con.close()
        return "Error: the punishment pool is locked in for the season — no new submissions."
    owners = {r[0] for r in con.execute("SELECT DISTINCT owner_name FROM teams").fetchall()} - INACTIVE_OWNERS
    if submitted_by not in owners:
        con.close()
        return (
            f"Error: {submitted_by!r} isn't a recognized owner_name — resolve the sender's "
            "name to their canonical owner_name from the nickname list and retry."
        )

    now = _now_iso()
    con.execute(
        "INSERT INTO punishment_ideas (text, submitted_by, created_at) VALUES (?,?,?)",
        (idea_text, submitted_by, now),
    )
    con.commit()
    con.close()
    return f"Idea added to the punishment pool, credited to {submitted_by}: {idea_text!r}"


# ── Side bets — open to everyone to ADD, commissioner-only to resolve ──────
# (add_side_bet lives in the general TOOLS list; resolve/void are in
# COMMISSIONER_TOOLS, same split as punishment ideas vs the shit list)

STAKES_MAX_LEN = 200
DESCRIPTION_MAX_LEN = 300


def _known_owners(con: sqlite3.Connection) -> set[str]:
    return {r[0] for r in con.execute("SELECT DISTINCT owner_name FROM teams").fetchall()} - INACTIVE_OWNERS


def add_side_bet(
    description: str, side_a: str, stakes: str, submitted_by: str,
    side_b: str = None, resolution_query: str = None, resolution_note: str = None,
) -> str:
    description = description.strip()
    stakes = stakes.strip()
    if not description:
        return "Error: description can't be empty."
    if len(description) > DESCRIPTION_MAX_LEN:
        return f"Error: keep the description under {DESCRIPTION_MAX_LEN} characters."
    if len(stakes) > STAKES_MAX_LEN:
        return f"Error: keep the stakes under {STAKES_MAX_LEN} characters."
    if bool(resolution_query) != bool(resolution_note):
        return "Error: resolution_query and resolution_note must be given together, or both omitted."

    con = _write_db()
    owners = _known_owners(con)
    if side_a not in owners:
        con.close()
        return f"Error: side_a {side_a!r} isn't a recognized owner_name — resolve it from the nickname list and retry."
    if side_b is not None and side_b not in owners:
        con.close()
        return f"Error: side_b {side_b!r} isn't a recognized owner_name — resolve it from the nickname list and retry."

    if resolution_query:
        error = side_bets.validate_resolution_query(resolution_query)
        if error:
            con.close()
            return f"Error: resolution_query didn't run cleanly ({error}) — fix it or omit it and leave resolution manual."

    now = _now_iso()
    cur = con.execute(
        "INSERT INTO side_bets (description, side_a, side_b, stakes, submitted_by, resolution_query, "
        "resolution_note, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?,'open',?,?)",
        (description, side_a, side_b, stakes, submitted_by, resolution_query, resolution_note, now, now),
    )
    con.commit()
    bet_id = cur.lastrowid
    con.close()
    resolves = f"auto-resolves: {resolution_note}" if resolution_note else "resolution: manual (commissioner will call it)"
    return f"Side bet added (id={bet_id}): {description!r}, stakes: {stakes!r}. {resolves}"


def resolve_side_bet(bet_id: int, winner: str, note: str = None) -> str:
    con = _write_db()
    row = con.execute("SELECT side_a, side_b, status FROM side_bets WHERE id=?", (bet_id,)).fetchone()
    if row is None:
        con.close()
        return f"Error: no side bet with id={bet_id}."
    if row[2] != "open":
        con.close()
        return f"Error: side bet {bet_id} is already {row[2]}, not open."
    if winner not in (row[0], row[1], "PUSH"):
        con.close()
        return f"Error: winner must be one of the two sides ({row[0]!r} / {row[1]!r}) or 'PUSH', got {winner!r}."

    now = _now_iso()
    con.execute(
        "UPDATE side_bets SET status='resolved', winner=?, resolved_by='commissioner', resolved_at=?, "
        "updated_at=?, resolution_note=COALESCE(?, resolution_note) WHERE id=?",
        (winner, now, now, note, bet_id),
    )
    con.commit()
    con.close()
    return f"Side bet {bet_id} resolved: {winner} wins."


def void_side_bet(bet_id: int, note: str = None) -> str:
    con = _write_db()
    row = con.execute("SELECT status FROM side_bets WHERE id=?", (bet_id,)).fetchone()
    if row is None:
        con.close()
        return f"Error: no side bet with id={bet_id}."
    if row[0] != "open":
        con.close()
        return f"Error: side bet {bet_id} is already {row[0]}, not open."

    now = _now_iso()
    con.execute(
        "UPDATE side_bets SET status='voided', resolved_by='commissioner', resolved_at=?, updated_at=?, "
        "resolution_note=COALESCE(?, resolution_note) WHERE id=?",
        (now, now, note, bet_id),
    )
    con.commit()
    con.close()
    return f"Side bet {bet_id} voided."


# OpenAI-style function-calling schema for query_almanac — DeepSeek's API is
# OpenAI-compatible (same base_url pattern, same tools/tool_calls shape), but
# has no equivalent of Anthropic's @beta_tool auto-schema-from-function
# decorator, so the schema is written out explicitly here instead.
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "query_almanac",
            "description": "Run a read-only SQL query against the league almanac database.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "A single SELECT (or WITH ... SELECT) statement. No writes.",
                    }
                },
                "required": ["sql"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "submit_punishment_idea",
            "description": "Submit a new idea to the pre-season punishment pool, which gets voted on later. Anyone in the chat can submit one — not commissioner-gated.",
            "parameters": {
                "type": "object",
                "properties": {
                    "idea_text": {
                        "type": "string",
                        "description": f"The punishment idea, max {IDEA_MAX_LEN} characters.",
                    },
                    "submitted_by": {
                        "type": "string",
                        "description": "Canonical owner_name of whoever is ACTUALLY sending the current message (see the 'Message sender' note and resolve nicknames first) — never a different name just because it's mentioned in the message text.",
                    },
                },
                "required": ["idea_text", "submitted_by"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_side_bet",
            "description": "Log a side bet (a wager between owners, or a prop bet) to the side bets library. Anyone in the chat can add one — not commissioner-gated. Resolving/overriding an outcome is commissioner-only (separate tools).",
            "parameters": {
                "type": "object",
                "properties": {
                    "description": {"type": "string", "description": f"Plain description of what the bet is, max {DESCRIPTION_MAX_LEN} characters."},
                    "side_a": {"type": "string", "description": "Canonical owner_name of one side of the bet (resolve nicknames first, do not guess)."},
                    "side_b": {"type": "string", "description": "Canonical owner_name of the other side, if there is a specific counterparty — omit for a prop bet with none."},
                    "stakes": {"type": "string", "description": f"What's on the line, max {STAKES_MAX_LEN} characters. Use \"bragging rights\" if genuinely unspecified."},
                    "submitted_by": {"type": "string", "description": "Canonical owner_name of whoever is ACTUALLY sending the current message (see the 'Message sender' note) — never a different name just because it's mentioned in the message text."},
                    "resolution_query": {"type": "string", "description": "Optional: a single read-only SELECT returning at most one row, one column `winner` (owner_name, 'PUSH', or zero rows if not yet determinable). Omit entirely if you can't confidently express the condition."},
                    "resolution_note": {"type": "string", "description": "Required together with resolution_query: a one-sentence human-readable explanation of the resolution logic, shown publicly alongside it."},
                },
                "required": ["description", "side_a", "stakes", "submitted_by"],
            },
        },
    },
]

# Only ever added to the request's `tools` list when the caller has been
# verified as the commissioner (see answer_question) — not offered to the
# model at all otherwise, so it can't be invoked regardless of what anyone
# asks for in the chat.
COMMISSIONER_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "add_rule",
            "description": "Add a new league rule under a category.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "description": "e.g. Scoring, Draft, Playoffs, Roster"},
                    "text": {"type": "string", "description": "The rule's full text."},
                    "title": {"type": "string", "description": "Optional short title for the rule."},
                    "sort_order": {"type": "integer", "description": "Optional display order within the category, lower first."},
                },
                "required": ["category", "text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_rule",
            "description": "Edit an existing league rule. Only provide the fields being changed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "rule_id": {"type": "integer"},
                    "category": {"type": "string"},
                    "title": {"type": "string"},
                    "text": {"type": "string"},
                    "sort_order": {"type": "integer"},
                },
                "required": ["rule_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_rule",
            "description": "Permanently delete a league rule by id.",
            "parameters": {
                "type": "object",
                "properties": {"rule_id": {"type": "integer"}},
                "required": ["rule_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_pending_change",
            "description": "Log a proposed rule change for discussion before next season. Always created with status=pending.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "The proposed change."},
                    "proposed_by": {"type": "string", "description": "Optional name of who's proposing it, if mentioned."},
                    "note": {"type": "string", "description": "Optional extra context/discussion notes."},
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_pending_change",
            "description": "Edit a pending rule change, including moving its status to approved/rejected. Only provide the fields being changed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "change_id": {"type": "integer"},
                    "status": {"type": "string", "enum": ["pending", "approved", "rejected"]},
                    "text": {"type": "string"},
                    "note": {"type": "string"},
                    "proposed_by": {"type": "string"},
                },
                "required": ["change_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_pending_change",
            "description": "Permanently delete a pending rule change by id.",
            "parameters": {
                "type": "object",
                "properties": {"change_id": {"type": "integer"}},
                "required": ["change_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_to_shitlist",
            "description": "Add a manager to the commissioner's shit list — a ranked list of people currently pissing off the commissioner, rank 1 = worst offender at the top.",
            "parameters": {
                "type": "object",
                "properties": {
                    "owner_name": {"type": "string", "description": "Canonical owner_name (resolve nicknames first)."},
                    "reason": {"type": "string", "description": "Optional reason they're on the list."},
                    "rank": {
                        "type": "integer",
                        "description": "Optional 1-based position to insert at (1 = the very top/worst). Existing entries at or below this rank shift down automatically. Omit to add to the bottom of the list.",
                    },
                },
                "required": ["owner_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_shitlist_entry",
            "description": "Edit a shit list entry — reason, or its rank (move it up/down/to a specific spot). Only provide the fields being changed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "entry_id": {"type": "integer"},
                    "owner_name": {"type": "string"},
                    "reason": {"type": "string"},
                    "rank": {
                        "type": "integer",
                        "description": "New 1-based rank position to move this entry to. Other entries shift automatically to keep the list contiguous with no gaps or duplicates.",
                    },
                },
                "required": ["entry_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_shitlist_entry",
            "description": "Take a manager off the shit list by entry id.",
            "parameters": {
                "type": "object",
                "properties": {"entry_id": {"type": "integer"}},
                "required": ["entry_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "resolve_side_bet",
            "description": "Commissioner override: declare the outcome of an open side bet (whether it auto-resolves or not — this always wins over the automatic query).",
            "parameters": {
                "type": "object",
                "properties": {
                    "bet_id": {"type": "integer"},
                    "winner": {"type": "string", "description": "Must be exactly side_a's or side_b's owner_name, or the literal string 'PUSH' for a tie/wash."},
                    "note": {"type": "string", "description": "Optional replacement explanation of how/why this was decided."},
                },
                "required": ["bet_id", "winner"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "void_side_bet",
            "description": "Commissioner override: cancel an open side bet entirely (e.g. terms were unclear, called off by agreement) — no winner, just closed out.",
            "parameters": {
                "type": "object",
                "properties": {
                    "bet_id": {"type": "integer"},
                    "note": {"type": "string", "description": "Optional reason it's being voided."},
                },
                "required": ["bet_id"],
            },
        },
    },
]

TOOL_FUNCTIONS = {
    "query_almanac": lambda a: query_almanac(a["sql"]),
    "submit_punishment_idea": lambda a: submit_punishment_idea(**a),
    "add_side_bet": lambda a: add_side_bet(**a),
    "resolve_side_bet": lambda a: resolve_side_bet(**a),
    "void_side_bet": lambda a: void_side_bet(**a),
    "add_rule": lambda a: add_rule(**a),
    "update_rule": lambda a: update_rule(**a),
    "delete_rule": lambda a: delete_rule(**a),
    "add_pending_change": lambda a: add_pending_change(**a),
    "update_pending_change": lambda a: update_pending_change(**a),
    "delete_pending_change": lambda a: delete_pending_change(**a),
    "add_to_shitlist": lambda a: add_to_shitlist(**a),
    "update_shitlist_entry": lambda a: update_shitlist_entry(**a),
    "delete_shitlist_entry": lambda a: delete_shitlist_entry(**a),
}

MODEL = "deepseek-v4-flash"

# Safety cap on the manual tool-use loop below — DeepSeek's API has no
# built-in looping helper (unlike Anthropic's tool_runner, which this file
# used before), so this loop is hand-rolled and needs its own guard against
# the model looping on tool calls without ever producing a final answer.
MAX_TOOL_ROUNDS = 10


def answer_question(question: str, is_commissioner: bool = False, sender_name: str | None = None) -> str:
    client = OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com")

    tools = TOOLS + COMMISSIONER_TOOLS if is_commissioner else TOOLS

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if sender_name:
        # Server-verified identity (GroupMe's own display name for whoever
        # sent this message), injected as trusted context the model can't
        # get from the message text itself — the submit_punishment_idea tool
        # is instructed to always attribute submissions to this, never to a
        # name that just happens to appear inside the message.
        messages.append({
            "role": "system",
            "content": f"Message sender: {sender_name!r} (their real GroupMe display name).",
        })
    messages.append({"role": "user", "content": question})

    for _ in range(MAX_TOOL_ROUNDS):
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=tools,
            # Thinking re-enabled (2026-07-22) — disabled mode was fabricating
            # specific supporting details (e.g. wrong championship years)
            # despite an explicit anti-fabrication rule in the schema/prompt;
            # thinking mode eliminated the fabrication in testing (4/4 clean
            # runs vs frequent errors disabled) and costs less than
            # deepseek-v4-pro, so it's the middle ground on the cost/quality
            # ladder.
            # No max_tokens cap: with thinking enabled, reasoning tokens draw
            # from the same budget as the visible content/tool-call JSON, so
            # a cap here (previously 300) can truncate mid-tool-call and
            # produce invalid JSON — that crashed the bot outright on
            # 2026-07-22 (silent failure, no reply sent at all). Brevity is
            # enforced by the prompt instructions instead, not a token cap.
            extra_body={"thinking": {"type": "enabled"}},
        )
        message = response.choices[0].message
        messages.append(message.model_dump(exclude_none=True))

        if not message.tool_calls:
            return message.content or "I couldn't come up with an answer to that."

        for tool_call in message.tool_calls:
            try:
                args = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                # Malformed tool-call args from the model (e.g. truncated
                # generation) — tell the model, don't crash the whole
                # request. Keeps the loop going instead of an unhandled
                # exception silently killing the GroupMe reply.
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": "Error: your tool call arguments weren't valid JSON. Please retry with valid arguments.",
                })
                continue
            fn = TOOL_FUNCTIONS.get(tool_call.function.name)
            if fn is None:
                result = f"Error: unknown tool {tool_call.function.name!r}."
            else:
                try:
                    result = fn(args)
                except (TypeError, sqlite3.Error) as e:
                    result = f"Error calling {tool_call.function.name}: {e}"
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result,
            })

    return "I couldn't come up with an answer to that."
