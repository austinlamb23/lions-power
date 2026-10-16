"""The Pod's episode list -- publicly viewable (embedded YouTube videos, no
login needed), adding/removing restricted to the same small crew that runs
Room Grades (see routers/pod_grades.py) since they're literally the people
making the show. Not imported from there -- kept self-contained like every
other small allowlist-gated router in this codebase.

week follows the same convention as power_rankings/coach_poll_votes: 0 means
preseason, not a real week's episode.
"""
from __future__ import annotations

import re
import sqlite3

import requests
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import get_current_owner, now_iso
from database import get_db

router = APIRouter(prefix="/api/pod-episodes", tags=["pod-episodes"])

CREW = {"Austin Lamb", "Stephen Marshall", "Paul T Knickelbein", "Bubbleface Bob"}


def require_crew(owner: str = Depends(get_current_owner)) -> str:
    if owner not in CREW:
        raise HTTPException(403, "Only the pod crew can do that")
    return owner


def extract_youtube_id(value: str) -> str | None:
    """Accepts a bare 11-char id or any common YouTube URL shape
    (watch?v=, youtu.be/, embed/)."""
    value = value.strip()
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", value):
        return value
    m = re.search(r"(?:[?&]v=|youtu\.be/|embed/)([A-Za-z0-9_-]{11})", value)
    return m.group(1) if m else None


def fetch_youtube_title(youtube_id: str) -> str | None:
    """YouTube's oEmbed endpoint -- public, no API key needed. Used so
    whoever adds an episode doesn't have to retype the real title by hand;
    still overridable via the title field if this fails or gives something
    unwanted."""
    try:
        r = requests.get(
            "https://www.youtube.com/oembed",
            params={"url": f"https://www.youtube.com/watch?v={youtube_id}", "format": "json"},
            timeout=10,
        )
        if r.status_code != 200:
            return None
        return r.json().get("title")
    except requests.RequestException:
        return None


@router.get("")
def list_episodes(db: sqlite3.Connection = Depends(get_db)):
    rows = db.execute(
        "SELECT id, year, week, title, youtube_id, submitted_by, created_at FROM pod_episodes "
        "ORDER BY year DESC, week ASC, id ASC"
    ).fetchall()
    return {"episodes": [dict(r) for r in rows]}


class AddEpisode(BaseModel):
    year: int
    week: int
    url: str
    title: str | None = None


@router.post("")
def add_episode(
    body: AddEpisode,
    db: sqlite3.Connection = Depends(get_db),
    owner: str = Depends(require_crew),
):
    if body.week < 0:
        raise HTTPException(400, "week can't be negative")

    youtube_id = extract_youtube_id(body.url)
    if not youtube_id:
        raise HTTPException(400, "Couldn't find a YouTube video ID in that URL")

    title = body.title.strip() if body.title else None
    if not title:
        title = fetch_youtube_title(youtube_id)
    if not title:
        raise HTTPException(400, "Couldn't fetch the video's title automatically — pass one explicitly")

    now = now_iso()
    cur = db.execute(
        "INSERT INTO pod_episodes (year, week, title, youtube_id, submitted_by, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (body.year, body.week, title, youtube_id, owner, now, now),
    )
    db.commit()
    return {"status": "ok", "id": cur.lastrowid, "title": title}


@router.delete("/{episode_id}")
def delete_episode(
    episode_id: int,
    db: sqlite3.Connection = Depends(get_db),
    owner: str = Depends(require_crew),
):
    cur = db.execute("DELETE FROM pod_episodes WHERE id=?", (episode_id,))
    db.commit()
    if cur.rowcount == 0:
        raise HTTPException(404, f"No episode with id={episode_id}")
    return {"status": "ok"}
