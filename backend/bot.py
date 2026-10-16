import os

import requests
from fastapi import APIRouter, BackgroundTasks, Request

from bot_engine import answer_question

router = APIRouter(prefix="/api/bot", tags=["bot"])

GROUPME_MAX_LEN = 1000


def _handle_mention_and_reply(text: str):
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

    answer = answer_question(question)
    if len(answer) > GROUPME_MAX_LEN:
        answer = answer[: GROUPME_MAX_LEN - 1] + "…"

    requests.post(
        "https://api.groupme.com/v3/bots/post",
        json={"bot_id": bot_id, "text": answer},
        timeout=10,
    )


@router.post("/groupme-webhook")
async def groupme_webhook(request: Request, background_tasks: BackgroundTasks):
    payload = await request.json()

    # Never react to the bot's own posts — avoids a self-reply loop.
    if payload.get("sender_type") == "bot":
        return {"status": "ignored"}

    text = payload.get("text") or ""
    bot_name = os.environ.get("GROUPME_BOT_NAME", "")

    # GroupMe always renders a mention as literal "@DisplayName" text in the
    # message body, so a substring check is a robust way to detect it without
    # depending on the exact structured `mentions` attachment schema.
    if not bot_name or f"@{bot_name}".lower() not in text.lower():
        return {"status": "ignored"}

    # Ack GroupMe immediately; the LLM call can take several seconds and
    # GroupMe doesn't read the reply from this response body anyway — the
    # reply is a separate POST to the bots/post endpoint.
    background_tasks.add_task(_handle_mention_and_reply, text)
    return {"status": "queued"}
