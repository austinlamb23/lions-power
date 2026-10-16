import os
import sqlite3

import requests
from fastapi import APIRouter, BackgroundTasks, Request

import groupme
import punishment_squid_game
from bot_engine import answer_question
from database import DB_PATH

router = APIRouter(prefix="/api/bot", tags=["bot"])

_GROUPME_ID_TO_OWNER = {v: k for k, v in groupme.OWNER_TO_GROUPME_ID.items()}


def _post_to_groupme(bot_id: str, text: str):
    requests.post(
        "https://api.groupme.com/v3/bots/post",
        json={"bot_id": bot_id, "text": text},
        timeout=10,
    )


def _handle_mention_and_reply(text: str, is_commissioner: bool, sender_name: str):
    bot_name = os.environ.get("GROUPME_BOT_NAME", "")
    bot_id = os.environ.get("GROUPME_BOT_ID", "")

    question = text
    if bot_name:
        # Strip a leading "@BotName" mention before handing off the question.
        marker = f"@{bot_name}"
        idx = text.lower().find(marker.lower())
        if idx != -1:
            question = text[:idx] + text[idx + len(marker):]
    question = question.strip()

    if not question:
        answer = "You rang? Ask me something about the league, like \"who has the most championships\" or \"what's Mark's record against Vince\"."
    else:
        try:
            answer = answer_question(question, is_commissioner=is_commissioner, sender_name=sender_name)
        except Exception:
            # Never let an unexpected exception here result in total silence —
            # this background task's return value is discarded either way, so
            # an uncaught exception previously meant no reply and no visible
            # error at all (found 2026-07-22: a truncated tool call crashed
            # this with zero feedback to the group chat).
            answer = "Something broke on my end trying to answer that — try again in a bit."

    for chunk in groupme.split_message(answer):
        _post_to_groupme(bot_id, chunk)


def _handle_possible_elimination_reply(owner_name: str, text: str) -> bool:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        return punishment_squid_game.handle_possible_reply(con, owner_name, text)
    finally:
        con.close()


@router.post("/groupme-webhook")
async def groupme_webhook(request: Request, background_tasks: BackgroundTasks):
    payload = await request.json()

    # Never react to the bot's own posts — avoids a self-reply loop.
    if payload.get("sender_type") == "bot":
        return {"status": "ignored"}

    text = payload.get("text") or ""

    # A message from someone with an open punishment-squid-game elimination
    # pending takes over regardless of whether the bot was @mentioned -- that
    # question was already asked of them specifically, and per the squid
    # game's own rules only THEIR response counts, so this must not require
    # them to re-@mention Gabe to answer it. This check must stay narrow
    # (pending row exists for THIS sender) — otherwise every message from
    # every recognized owner would hijack the normal Gabe Q&A flow below.
    sender_owner = _GROUPME_ID_TO_OWNER.get(str(payload.get("user_id")))
    if sender_owner:
        con = sqlite3.connect(DB_PATH)
        con.row_factory = sqlite3.Row
        try:
            pending = punishment_squid_game.has_pending_elimination(con, sender_owner)
        finally:
            con.close()
        if pending:
            background_tasks.add_task(_handle_possible_elimination_reply, sender_owner, text)
            return {"status": "queued"}

    bot_name = os.environ.get("GROUPME_BOT_NAME", "")

    # GroupMe always renders a mention as literal "@DisplayName" text in the
    # message body, so a substring check is a robust way to detect it without
    # depending on the exact structured `mentions` attachment schema.
    if not bot_name or f"@{bot_name}".lower() not in text.lower():
        return {"status": "ignored"}

    # Commissioner-only rules/pending-changes tools are gated on GroupMe's
    # numeric user_id, not the display name — a name can be duplicated or
    # changed, the account id can't. Compared as strings since GroupMe's
    # JSON sends it as a string already.
    commissioner_id = os.environ.get("GROUPME_COMMISSIONER_ID", "")
    is_commissioner = bool(commissioner_id) and str(payload.get("user_id")) == commissioner_id

    # GroupMe's own display name for whoever actually sent this message —
    # passed through as trusted, server-verified identity (not something the
    # message text itself could spoof) so tools like submit_punishment_idea
    # always attribute correctly.
    sender_name = payload.get("name") or ""

    # Ack GroupMe immediately; the LLM call can take several seconds and
    # GroupMe doesn't read the reply from this response body anyway — the
    # reply is a separate POST to the bots/post endpoint.
    background_tasks.add_task(_handle_mention_and_reply, text, is_commissioner, sender_name)
    return {"status": "queued"}
