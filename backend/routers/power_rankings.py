from __future__ import annotations

import io
import os
import sqlite3
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import FileResponse
from PIL import Image
from pydantic import BaseModel

from auth import get_current_owner, now_iso
from database import DB_PATH, get_db

router = APIRouter(prefix="/api/power-rankings", tags=["power-rankings"])

RANKINGS_AUTHOR = os.environ.get("POWER_RANKINGS_AUTHOR", "Austin Lamb")

UPLOADS_DIR = DB_PATH.parent / "uploads" / "power_rankings"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
}
MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_IMAGE_DIMENSION = 1600  # journey view never displays taller than ~22rem; way more headroom than needed


def _compress_image(data: bytes, content_type: str) -> tuple[bytes, str]:
    """Resize to a sane max dimension and re-encode as JPEG for a much
    smaller file size -- uploaded images (often full-resolution AI art,
    several MB each) were the real cause of slow slide-to-slide loads in the
    journey view, not the hosting. PNG's lossless compression barely helps
    on busy/detailed art even after resizing, so any transparency is
    flattened onto black rather than kept as PNG -- every place this image
    is displayed (the journey view's hero) already renders it inside a
    black container, so this is visually identical but compresses far
    better. GIFs are left untouched (animation isn't safely reconstructable
    through a single Pillow resize+save)."""
    if content_type == "image/gif":
        return data, ".gif"

    img = Image.open(io.BytesIO(data))
    img.load()
    if img.width > MAX_IMAGE_DIMENSION or img.height > MAX_IMAGE_DIMENSION:
        img.thumbnail((MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION), Image.LANCZOS)

    has_alpha = img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info)
    if has_alpha:
        img = img.convert("RGBA")
        background = Image.new("RGB", img.size, (0, 0, 0))
        background.paste(img, mask=img.split()[-1])
        img = background
    elif img.mode != "RGB":
        img = img.convert("RGB")

    out = io.BytesIO()
    img.save(out, format="JPEG", quality=85, optimize=True)
    return out.getvalue(), ".jpg"


def require_author(owner: str = Depends(get_current_owner)) -> str:
    if owner != RANKINGS_AUTHOR:
        raise HTTPException(403, "Only the power rankings author can do that")
    return owner


# NOTE: every static-path route below (/current-week, /history, /images, ...)
# must stay registered before the generic /{year}/{week} route further down —
# FastAPI/Starlette matches routes in registration order, and since these
# path templates aren't given explicit :int converters, a route like
# /images/{filename} has the same two-segment shape as /{year}/{week} and
# would otherwise get swallowed by it (year="images" fails int parsing -> 422
# instead of falling through to the real match).

# ── Current week ─────────────────────────────────────────────────────────────

@router.get("/current-week")
def get_current_week(db: sqlite3.Connection = Depends(get_db)):
    row = db.execute("SELECT year, week FROM current_week WHERE id = 1").fetchone()
    if row:
        return {"year": row["year"], "week": row["week"]}

    latest = db.execute("SELECT MAX(year) AS year FROM seasons").fetchone()
    year = latest["year"] if latest and latest["year"] else None
    return {"year": year, "week": 0}


class CurrentWeekRequest(BaseModel):
    year: int
    week: int


@router.post("/current-week")
def set_current_week(
    body: CurrentWeekRequest,
    db: sqlite3.Connection = Depends(get_db),
    author: str = Depends(require_author),
):
    if body.week < 0:
        raise HTTPException(400, "week can't be negative")
    db.execute(
        "INSERT INTO current_week (id, year, week) VALUES (1, ?, ?) "
        "ON CONFLICT(id) DO UPDATE SET year=excluded.year, week=excluded.week",
        (body.year, body.week)
    )
    db.commit()
    return {"year": body.year, "week": body.week}


# ── History / archive ────────────────────────────────────────────────────────
#
# Power rankings' predictive value is really about the PRESEASON call (week=0)
# — that's the only week that's a genuine blind prediction rather than a
# during-season read, and it's the only week that exists for 2022-2025 anyway.
# Coach's poll has no preseason concept; for accuracy purposes we use each
# year's LATEST posted week as that year's "final read" (for 2024/2025 that's
# the single FINAL season-end snapshot already documented in almanac_schema.md).

def _accuracy_stats(rows_by_year: dict[int, list[dict]]) -> dict:
    diffs = []
    champion_hits = champion_total = 0
    last_hits = last_total = 0
    for year, rows in rows_by_year.items():
        scored = [r for r in rows if r["final_standing"] is not None]
        if not scored:
            continue
        diffs.extend(abs(r["predicted_rank"] - r["final_standing"]) for r in scored)
        n = len(scored)
        best_pick = min(scored, key=lambda r: r["predicted_rank"])
        champion_total += 1
        if best_pick["final_standing"] == 1:
            champion_hits += 1
        worst_pick = max(scored, key=lambda r: r["predicted_rank"])
        last_total += 1
        if worst_pick["final_standing"] == n:
            last_hits += 1
    return {
        "avg_rank_error": round(sum(diffs) / len(diffs), 2) if diffs else None,
        "champion_hits": champion_hits,
        "champion_total": champion_total,
        "champion_hit_rate": round(champion_hits / champion_total, 2) if champion_total else None,
        "last_place_hits": last_hits,
        "last_place_total": last_total,
        "last_place_hit_rate": round(last_hits / last_total, 2) if last_total else None,
        "years_covered": len(rows_by_year),
    }


@router.get("/history")
def get_history(db: sqlite3.Connection = Depends(get_db)):
    pr_rows = db.execute("""
        SELECT pr.year, pr.team_id, pr.rank AS predicted_rank, t.team_name, t.owner_name,
               s.final_standing
        FROM power_rankings pr
        JOIN teams t ON t.year = pr.year AND t.team_id = pr.team_id
        LEFT JOIN standings s ON s.year = pr.year AND s.team_id = pr.team_id
        WHERE pr.week = 0
        ORDER BY pr.year DESC, pr.rank ASC
    """).fetchall()

    cp_rows = db.execute("""
        SELECT cpv.year, cpv.team_id, AVG(cpv.rank_given) AS predicted_rank, t.team_name, t.owner_name,
               s.final_standing,
               COUNT(DISTINCT cpv.voter_owner) AS ballot_count,
               MAX(CASE WHEN cpv.voter_owner = 'FINAL' THEN 1 ELSE 0 END) AS is_final_snapshot
        FROM coach_poll_votes cpv
        JOIN teams t ON t.year = cpv.year AND t.team_id = cpv.team_id
        LEFT JOIN standings s ON s.year = cpv.year AND s.team_id = cpv.team_id
        WHERE cpv.week = (SELECT MAX(week) FROM coach_poll_votes v2 WHERE v2.year = cpv.year)
        GROUP BY cpv.year, cpv.team_id
        ORDER BY cpv.year DESC, predicted_rank ASC
    """).fetchall()

    pr_by_year: dict[int, list[dict]] = {}
    for r in pr_rows:
        pr_by_year.setdefault(r["year"], []).append(dict(r))

    cp_by_year: dict[int, list[dict]] = {}
    for r in cp_rows:
        cp_by_year.setdefault(r["year"], []).append(dict(r))

    years = sorted(set(pr_by_year) | set(cp_by_year), reverse=True)
    year_entries = []
    for year in years:
        cp_year_rows = cp_by_year.get(year)
        year_entries.append({
            "year": year,
            "power_rankings": {
                "week": 0,
                "entries": [
                    {
                        "team_id": r["team_id"], "team_name": r["team_name"], "owner_name": r["owner_name"],
                        "predicted_rank": r["predicted_rank"], "final_standing": r["final_standing"],
                    }
                    for r in pr_by_year[year]
                ],
            } if year in pr_by_year else None,
            "coach_poll": {
                "is_final_snapshot": bool(cp_year_rows[0]["is_final_snapshot"]),
                "ballot_count": cp_year_rows[0]["ballot_count"],
                "entries": [
                    {
                        "team_id": r["team_id"], "team_name": r["team_name"], "owner_name": r["owner_name"],
                        "predicted_rank": r["predicted_rank"], "final_standing": r["final_standing"],
                    }
                    for r in sorted(cp_year_rows, key=lambda r: r["predicted_rank"])
                ],
            } if cp_year_rows else None,
        })

    return {
        "summary": {
            "power_rankings": _accuracy_stats(pr_by_year),
            "coach_poll": _accuracy_stats(cp_by_year),
        },
        "years": year_entries,
    }


# ── Weeks posted for a season (used by the Current Season page) ─────────────

@router.get("/weeks/{year}")
def get_weeks_for_year(year: int, db: sqlite3.Connection = Depends(get_db)):
    pr_weeks = [r["week"] for r in db.execute(
        "SELECT DISTINCT week FROM power_rankings WHERE year = ? ORDER BY week ASC", (year,)
    ).fetchall()]
    cp_weeks = [r["week"] for r in db.execute(
        "SELECT DISTINCT week FROM coach_poll_votes WHERE year = ? ORDER BY week ASC", (year,)
    ).fetchall()]
    return {"power_rankings_weeks": pr_weeks, "coach_poll_weeks": cp_weeks}


# ── Team roster for a year (used to build ballot/admin forms) ───────────────

@router.get("/teams/{year}")
def get_teams_for_year(year: int, db: sqlite3.Connection = Depends(get_db)):
    rows = db.execute(
        "SELECT team_id, team_name, owner_name FROM teams WHERE year = ? ORDER BY team_id",
        (year,)
    ).fetchall()
    if not rows:
        raise HTTPException(404, f"No teams found for year {year}")
    return [dict(r) for r in rows]


# ── Images ───────────────────────────────────────────────────────────────────

@router.post("/images")
async def upload_image(file: UploadFile, author: str = Depends(require_author)):
    ext = ALLOWED_IMAGE_TYPES.get(file.content_type)
    if not ext:
        raise HTTPException(400, "Only jpeg, png, gif, or webp images are allowed")

    data = await file.read()
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(400, "Image must be under 8MB")

    try:
        data, ext = _compress_image(data, file.content_type)
    except Exception:
        pass  # if compression fails for any reason, fall back to storing the original rather than blocking the upload

    filename = f"{uuid.uuid4().hex}{ext}"
    (UPLOADS_DIR / filename).write_bytes(data)
    return {"image_path": filename}


@router.get("/images/{filename}")
def get_image(filename: str):
    safe_name = Path(filename).name  # strip any path components
    path = UPLOADS_DIR / safe_name
    if not path.is_file():
        raise HTTPException(404, "Image not found")
    # filenames are random UUIDs, never reused/overwritten by a later upload,
    # so caching forever is always correct -- this is what actually fixes
    # repeat slide-to-slide loads feeling slow (first load still pays for
    # the fetch, but every visit after that is instant from browser cache).
    return FileResponse(path, headers={"Cache-Control": "public, max-age=31536000, immutable"})


# ── Read a week's rankings ───────────────────────────────────────────────────

@router.get("/{year}/{week}")
def get_week(year: int, week: int, db: sqlite3.Connection = Depends(get_db)):
    rows = db.execute("""
        SELECT pr.team_id, pr.rank, pr.blurb, pr.image_path, pr.updated_at,
               t.team_name, t.owner_name
        FROM power_rankings pr
        JOIN teams t ON t.year = pr.year AND t.team_id = pr.team_id
        WHERE pr.year = ? AND pr.week = ?
        ORDER BY pr.rank ASC
    """, (year, week)).fetchall()

    # Rank movement vs the most recently PUBLISHED earlier week this season --
    # not necessarily week-1, in case a week got skipped. previous_week is
    # None when there's nothing earlier posted at all (this is the season's
    # first posted ranking) -- the frontend uses that to distinguish "no
    # comparison possible yet" from "this specific team is new since last
    # time" (previous_rank None but previous_week is set).
    prev_week_row = db.execute(
        "SELECT MAX(week) AS week FROM power_rankings WHERE year=? AND week<?", (year, week)
    ).fetchone()
    previous_week = prev_week_row["week"] if prev_week_row and prev_week_row["week"] is not None else None
    previous_ranks = {}
    if previous_week is not None:
        previous_ranks = {
            r["team_id"]: r["rank"] for r in db.execute(
                "SELECT team_id, rank FROM power_rankings WHERE year=? AND week=?",
                (year, previous_week),
            ).fetchall()
        }

    return {
        "year": year,
        "week": week,
        "posted": len(rows) > 0,
        "updated_at": rows[0]["updated_at"] if rows else None,
        "previous_week": previous_week,
        "rankings": [
            {
                "team_id": r["team_id"],
                "rank": r["rank"],
                "team_name": r["team_name"],
                "owner_name": r["owner_name"],
                "blurb": r["blurb"],
                "image_path": r["image_path"],
                "previous_rank": previous_ranks.get(r["team_id"]),
                # Positive = moved UP (better) -- e.g. rank 3 -> rank 1 is +2,
                # matching "higher number is better" display convention even
                # though the stored rank itself got numerically smaller.
                "rank_change": (previous_ranks[r["team_id"]] - r["rank"]) if r["team_id"] in previous_ranks else None,
            }
            for r in rows
        ],
    }


# ── Post a week's rankings (author-only) ─────────────────────────────────────

class RankingEntry(BaseModel):
    team_id: int
    rank: int
    blurb: str | None = None
    image_path: str | None = None


class PostWeekRequest(BaseModel):
    rankings: list[RankingEntry]


@router.post("/{year}/{week}")
def post_week(
    year: int, week: int,
    body: PostWeekRequest,
    db: sqlite3.Connection = Depends(get_db),
    author: str = Depends(require_author),
):
    if week < 0:
        raise HTTPException(400, "week can't be negative")

    team_ids = {r["team_id"] for r in db.execute(
        "SELECT team_id FROM teams WHERE year = ?", (year,)
    ).fetchall()}
    if not team_ids:
        raise HTTPException(400, f"No teams found for year {year}")

    entry_team_ids = [e.team_id for e in body.rankings]
    if set(entry_team_ids) != team_ids:
        raise HTTPException(400, "Rankings must include exactly the teams for that year, once each")

    ranks = sorted(e.rank for e in body.rankings)
    if ranks != list(range(1, len(team_ids) + 1)):
        raise HTTPException(400, f"Ranks must be 1-{len(team_ids)} with no gaps or duplicates")

    now = now_iso()
    db.execute("DELETE FROM power_rankings WHERE year = ? AND week = ?", (year, week))
    for e in body.rankings:
        db.execute(
            "INSERT INTO power_rankings (year, week, team_id, rank, blurb, image_path, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (year, week, e.team_id, e.rank, e.blurb, e.image_path, now, now)
        )
    db.commit()
    return {"status": "ok"}


# ── Drafts (author-only, never public) ───────────────────────────────────────
#
# Separate table from power_rankings itself -- publishing is a distinct act
# from saving progress. A draft can be incomplete (missing teams, duplicate
# or gapped ranks) since it's just work-in-progress; only publish enforces
# the "every team, ranks 1-N, no gaps" rule that public rankings need.

@router.get("/{year}/{week}/draft")
def get_draft(year: int, week: int, db: sqlite3.Connection = Depends(get_db), author: str = Depends(require_author)):
    rows = db.execute("""
        SELECT prd.team_id, prd.rank, prd.blurb, prd.image_path, prd.updated_at,
               t.team_name, t.owner_name
        FROM power_rankings_drafts prd
        JOIN teams t ON t.year = prd.year AND t.team_id = prd.team_id
        WHERE prd.year = ? AND prd.week = ?
        ORDER BY prd.rank ASC
    """, (year, week)).fetchall()

    return {
        "year": year,
        "week": week,
        "has_draft": len(rows) > 0,
        "updated_at": rows[0]["updated_at"] if rows else None,
        "rankings": [
            {
                "team_id": r["team_id"],
                "rank": r["rank"],
                "team_name": r["team_name"],
                "owner_name": r["owner_name"],
                "blurb": r["blurb"],
                "image_path": r["image_path"],
            }
            for r in rows
        ],
    }


@router.post("/{year}/{week}/draft")
def save_draft(
    year: int, week: int,
    body: PostWeekRequest,
    db: sqlite3.Connection = Depends(get_db),
    author: str = Depends(require_author),
):
    if week < 0:
        raise HTTPException(400, "week can't be negative")

    team_ids = {r["team_id"] for r in db.execute(
        "SELECT team_id FROM teams WHERE year = ?", (year,)
    ).fetchall()}
    if not team_ids:
        raise HTTPException(400, f"No teams found for year {year}")

    bad_ids = {e.team_id for e in body.rankings} - team_ids
    if bad_ids:
        raise HTTPException(400, f"Not valid teams for {year}: {sorted(bad_ids)}")

    now = now_iso()
    db.execute("DELETE FROM power_rankings_drafts WHERE year = ? AND week = ?", (year, week))
    for e in body.rankings:
        db.execute(
            "INSERT INTO power_rankings_drafts (year, week, team_id, rank, blurb, image_path, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (year, week, e.team_id, e.rank, e.blurb, e.image_path, now, now)
        )
    db.commit()
    return {"status": "ok"}
