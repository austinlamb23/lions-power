from __future__ import annotations

import os
import re
import sqlite3
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from auth import get_active_owner, get_optional_owner, now_iso
from database import DB_PATH, get_db

router = APIRouter(prefix="/api/forums", tags=["forums"])

FORUMS_ADMIN = os.environ.get("FORUMS_ADMIN", "Austin Lamb")

UPLOADS_DIR = DB_PATH.parent / "uploads" / "forums"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
}
MAX_IMAGE_BYTES = 8 * 1024 * 1024


def require_post_author_or_admin(
    post_id: int,
    db: sqlite3.Connection = Depends(get_db),
    owner: str = Depends(get_active_owner),
) -> str:
    row = db.execute("SELECT submitted_by FROM forum_posts WHERE id = ?", (post_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Post not found")
    if owner != row["submitted_by"] and owner != FORUMS_ADMIN:
        raise HTTPException(403, "Only the post's author or a commissioner can do that")
    return owner


def _validate_cta(url: str | None, label: str | None) -> None:
    if bool(url) != bool(label):
        raise HTTPException(400, "cta_url and cta_label must be provided together")
    if url and not (url.startswith("/") or url.startswith("http://") or url.startswith("https://")):
        raise HTTPException(400, "cta_url must be a relative path or an absolute http(s) URL")


def _make_excerpt(md: str, length: int = 220) -> str:
    text = re.sub(r"[#*_`>\[\]()!-]", "", md)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:length] + ("…" if len(text) > length else "")


class ForumPostCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    body_markdown: str = Field(min_length=1, max_length=100_000)
    excerpt: str | None = Field(default=None, max_length=500)
    cover_image_path: str | None = None
    cta_url: str | None = Field(default=None, max_length=500)
    cta_label: str | None = Field(default=None, max_length=100)


class ForumPostUpdate(ForumPostCreate):
    pass  # edit is a full replace, same shape as create


# ── List / detail ────────────────────────────────────────────────────────────

@router.get("/posts")
def list_posts(db: sqlite3.Connection = Depends(get_db)):
    rows = db.execute(
        "SELECT id, title, excerpt, body_markdown, cover_image_path, submitted_by, created_at, updated_at "
        "FROM forum_posts ORDER BY created_at DESC"
    ).fetchall()
    return {
        "posts": [
            {
                "id": r["id"],
                "title": r["title"],
                "excerpt": r["excerpt"] or _make_excerpt(r["body_markdown"]),
                "cover_image_path": r["cover_image_path"],
                "submitted_by": r["submitted_by"],
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
            }
            for r in rows
        ]
    }


@router.get("/posts/{post_id}")
def get_post(
    post_id: int,
    db: sqlite3.Connection = Depends(get_db),
    owner: str | None = Depends(get_optional_owner),
):
    row = db.execute("SELECT * FROM forum_posts WHERE id = ?", (post_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Post not found")
    can_edit = owner is not None and (owner == row["submitted_by"] or owner == FORUMS_ADMIN)
    return {
        "id": row["id"],
        "title": row["title"],
        "body_markdown": row["body_markdown"],
        "cover_image_path": row["cover_image_path"],
        "cta_url": row["cta_url"],
        "cta_label": row["cta_label"],
        "submitted_by": row["submitted_by"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "can_edit": can_edit,
    }


# ── Create / update / delete ─────────────────────────────────────────────────

@router.post("/posts", status_code=201)
def create_post(
    body: ForumPostCreate,
    db: sqlite3.Connection = Depends(get_db),
    owner: str = Depends(get_active_owner),
):
    _validate_cta(body.cta_url, body.cta_label)
    now = now_iso()
    cur = db.execute(
        "INSERT INTO forum_posts "
        "(title, body_markdown, excerpt, cover_image_path, cta_url, cta_label, submitted_by, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (body.title, body.body_markdown, body.excerpt, body.cover_image_path,
         body.cta_url, body.cta_label, owner, now, now),
    )
    db.commit()
    return {"id": cur.lastrowid}


@router.put("/posts/{post_id}")
def update_post(
    post_id: int,
    body: ForumPostUpdate,
    db: sqlite3.Connection = Depends(get_db),
    owner: str = Depends(require_post_author_or_admin),
):
    _validate_cta(body.cta_url, body.cta_label)
    db.execute(
        "UPDATE forum_posts SET title=?, body_markdown=?, excerpt=?, cover_image_path=?, "
        "cta_url=?, cta_label=?, updated_at=? WHERE id=?",
        (body.title, body.body_markdown, body.excerpt, body.cover_image_path,
         body.cta_url, body.cta_label, now_iso(), post_id),
    )
    db.commit()
    return {"updated": True}


@router.delete("/posts/{post_id}")
def delete_post(
    post_id: int,
    db: sqlite3.Connection = Depends(get_db),
    owner: str = Depends(require_post_author_or_admin),
):
    db.execute("DELETE FROM forum_posts WHERE id = ?", (post_id,))
    db.commit()
    return {"deleted": True}


# ── Images ───────────────────────────────────────────────────────────────────

@router.post("/images")
async def upload_image(file: UploadFile, owner: str = Depends(get_active_owner)):
    ext = ALLOWED_IMAGE_TYPES.get(file.content_type)
    if not ext:
        raise HTTPException(400, "Only jpeg, png, gif, or webp images are allowed")

    data = await file.read()
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(400, "Image must be under 8MB")

    filename = f"{uuid.uuid4().hex}{ext}"
    (UPLOADS_DIR / filename).write_bytes(data)
    return {"image_path": filename}


@router.get("/images/{filename}")
def get_image(filename: str):
    safe_name = Path(filename).name  # strip any path components
    path = UPLOADS_DIR / safe_name
    if not path.is_file():
        raise HTTPException(404, "Image not found")
    return FileResponse(path)
