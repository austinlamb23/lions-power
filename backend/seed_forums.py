"""Seeds the two launch posts for the Forums section:

  1. A framing post for the existing Draft Intel dashboard, with real teaser
     numbers pulled live from get_draft_intel() (not hand-typed), linking out
     via cta_url to /draft-intel rather than reproducing its interactive
     visuals as static markdown.
  2. "Best Draft of All Time" — three methodologies specified directly by the
     league (pure point volume, best-possible starting lineup, and the "Paco
     method" positional-finish/bench-weighted variant), each rendered as its
     own top-5 markdown table, computed live against draft_picks/teams.

Idempotent: skips/updates by title match rather than duplicating. This script
seeds the two LAUNCH posts specifically -- it isn't meant to be re-run as a
"regenerate forever" job. Anything after launch goes through the UI like a
normal post.

Usage: venv/bin/python3 seed_forums.py
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from database import DB_PATH  # noqa: E402
from routers.almanac import get_draft_intel  # noqa: E402

FORUMS_ADMIN = "Austin Lamb"


def now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def ensure_table(con: sqlite3.Connection) -> None:
    con.execute("""
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
        )
    """)
    con.execute("CREATE INDEX IF NOT EXISTS idx_forum_posts_created_at ON forum_posts(created_at)")
    con.commit()


def insert_post(con: sqlite3.Connection, title: str, body: str, excerpt: str,
                 cta_url: str | None = None, cta_label: str | None = None) -> None:
    if con.execute("SELECT 1 FROM forum_posts WHERE title = ?", (title,)).fetchone():
        print(f"already exists, skipping: {title!r}")
        return
    now = now_iso()
    con.execute(
        "INSERT INTO forum_posts "
        "(title, body_markdown, excerpt, cover_image_path, cta_url, cta_label, submitted_by, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (title, body, excerpt, None, cta_url, cta_label, FORUMS_ADMIN, now, now),
    )
    con.commit()
    print(f"inserted: {title!r}")


def upsert_post(con: sqlite3.Connection, match_title_prefix: str, title: str, body: str, excerpt: str,
                 cta_url: str | None = None, cta_label: str | None = None) -> None:
    """Like insert_post, but updates an existing post in place (same id/URL) if one whose
    title starts with match_title_prefix already exists -- used when the post's own title
    changes across a content rewrite, so re-seeding fixes the post instead of duplicating it."""
    row = con.execute(
        "SELECT id FROM forum_posts WHERE title LIKE ? ORDER BY id LIMIT 1", (match_title_prefix + "%",)
    ).fetchone()
    now = now_iso()
    if row:
        con.execute(
            "UPDATE forum_posts SET title=?, body_markdown=?, excerpt=?, cta_url=?, cta_label=?, updated_at=? WHERE id=?",
            (title, body, excerpt, cta_url, cta_label, now, row["id"]),
        )
        con.commit()
        print(f"updated existing post id={row['id']}: {title!r}")
    else:
        con.execute(
            "INSERT INTO forum_posts "
            "(title, body_markdown, excerpt, cover_image_path, cta_url, cta_label, submitted_by, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (title, body, excerpt, None, cta_url, cta_label, FORUMS_ADMIN, now, now),
        )
        con.commit()
        print(f"inserted: {title!r}")


# ── Post #1: Draft Intel framing ─────────────────────────────────────────────

def build_draft_intel_post(db: sqlite3.Connection) -> tuple[str, str, str]:
    data = get_draft_intel(db)
    pearson = data["correlations"]["all"]["pearson"]
    n = data["correlations"]["all"]["n"]
    early, mid, late = data["buckets"]

    title = "Draft Intel: Does Draft Position Actually Predict Your Season?"
    excerpt = (
        f"Thirteen years of draft slots vs. final standing, crunched. Short answer: barely. "
        f"Long answer: it depends where you're picking from."
    )
    body = f"""We've all got a theory about draft slot. "Picking early is a curse." "Middle of the
draft is a trap." "Nobody wins from the back half." Thirteen seasons of real draft
order (2013-2025, {n} team-seasons) says: mostly, it doesn't matter as much as you think.

The overall correlation between first-round draft position and final standing is
**{pearson}** — practically flat. A near-zero Pearson coefficient means your draft slot
tells you almost nothing about where you'll finish, on average.

But "on average" is hiding the interesting part. Split into tiers and the story gets
more textured:

| Draft slot | Avg. final finish | Avg. points scored | Sample size |
|---|---|---|---|
| Early (1-3) | {early['avg_finish']} | {early['avg_points']} | {early['n']} |
| Mid (4-7) | {mid['avg_finish']} | {mid['avg_points']} | {mid['n']} |
| Late (8-10) | {late['avg_finish']} | {late['avg_points']} | {late['n']} |

The one place draft slot *does* show up: championships. The full breakdown — pick-by-pick
finish averages, who beats their draft slot most often across their whole tenure in the
league, and the exact championship distribution by tier — is all live and interactive on
the Draft Intel dashboard, updating automatically as each new season's results come in.

This post is really just the trailhead. Go pull the actual charts.
"""
    return title, excerpt, body


# ── Post #2: Best Draft of All Time (league-defined methods) ────────────────
#
# Three methods, as specified directly (not guessed):
#   Method 1 — pure point volume: total season_points across every player drafted.
#   Method 2 — best starting lineup: fill this league's real 9-slot starting shape
#     (1 QB, 2 RB, 2 WR, 1 TE, 1 FLEX[RB/WR/TE], 1 K, 1 D/ST -- confirmed from
#     weekly_rosters' actual per-week position counts) using the draft class's own
#     season_points, highest scorer per slot.
#   Method 3 — "Paco method": same 9-slot lineup, but selection AND scoring use
#     draft_picks.position_finish (the player's rank among every NFL player at
#     that position that season -- lower is better) instead of points, PLUS the
#     next 3 best remaining flex-eligible (RB/WR/TE) bench players, weighted
#     0.75/0.50/0.25. Final score is the sum of all those ranks -- LOWEST total
#     wins (golf-style), confirmed as the intended direction. position_finish
#     only exists 2019+, so this method is scoped to 2019-2025 only.

FLEX_ELIGIBLE = {"RB", "WR", "TE"}
STARTER_SHAPE = [("QB", 1), ("RB", 2), ("WR", 2), ("TE", 1), ("K", 1), ("D/ST", 1)]
BENCH_WEIGHTS = [0.75, 0.50, 0.25]


def _md_table(headers: list[str], rows: list[list]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(str(c) for c in row) + " |")
    return "\n".join(lines)


def _team_years(db: sqlite3.Connection, min_year: int | None = None) -> list[tuple[int, int]]:
    q = "SELECT DISTINCT year, team_id FROM draft_picks"
    params: tuple = ()
    if min_year is not None:
        q += " WHERE year >= ?"
        params = (min_year,)
    q += " ORDER BY year, team_id"
    return [(r["year"], r["team_id"]) for r in db.execute(q, params).fetchall()]


def _picks(db: sqlite3.Connection, year: int, team_id: int) -> list[sqlite3.Row]:
    return db.execute(
        "SELECT player_name, position, season_points, position_finish "
        "FROM draft_picks WHERE year=? AND team_id=?",
        (year, team_id),
    ).fetchall()


def _owner(db: sqlite3.Connection, year: int, team_id: int) -> str:
    row = db.execute("SELECT owner_name FROM teams WHERE year=? AND team_id=?", (year, team_id)).fetchone()
    return row["owner_name"] if row else "?"


def _rank_lookup(full_results, year: int, team_id: int):
    """full_results is a list of (score, year, team_id) already sorted best-first
    (ascending or descending, whichever direction that method uses) -- returns
    (rank, score, total_entries) for the given team-year, or None if absent
    (e.g. Method 3's pre-2019 gap)."""
    for i, entry in enumerate(full_results):
        if (entry[1], entry[2]) == (year, team_id):
            return i + 1, entry[0], len(full_results)
    return None


def _best_lineup_by_points(picks: list[sqlite3.Row]) -> tuple[float, sqlite3.Row]:
    """Returns (total lineup points, the single top-scoring starter used) for
    the league's real 9-slot shape, filled with this draft class's own players."""
    by_pos: dict[str, list] = {}
    for p in picks:
        by_pos.setdefault(p["position"], []).append(p)
    for pos in by_pos:
        by_pos[pos].sort(key=lambda p: p["season_points"], reverse=True)

    used, total = [], 0.0
    for pos, need in STARTER_SHAPE:
        for p in by_pos.get(pos, [])[:need]:
            used.append(p)
            total += p["season_points"]

    used_keys = {(p["player_name"], p["position"]) for p in used}
    flex_pool = sorted(
        [p for p in picks if p["position"] in FLEX_ELIGIBLE and (p["player_name"], p["position"]) not in used_keys],
        key=lambda p: p["season_points"], reverse=True,
    )
    if flex_pool:
        total += flex_pool[0]["season_points"]
        used.append(flex_pool[0])

    top_starter = max(used, key=lambda p: p["season_points"])
    return total, top_starter


def _paco_score(picks: list[sqlite3.Row]) -> tuple[float, sqlite3.Row] | None:
    """Returns (total rank score, best single starter) using position_finish for
    both selection and scoring, plus 3 weighted bench flexes. None if this draft
    class predates position_finish coverage (pre-2019)."""
    if any(p["position_finish"] is None for p in picks):
        return None

    by_pos: dict[str, list] = {}
    for p in picks:
        by_pos.setdefault(p["position"], []).append(p)
    for pos in by_pos:
        by_pos[pos].sort(key=lambda p: p["position_finish"])

    used, total = [], 0.0
    for pos, need in STARTER_SHAPE:
        for p in by_pos.get(pos, [])[:need]:
            used.append(p)
            total += p["position_finish"]

    used_keys = {(p["player_name"], p["position"]) for p in used}
    flex_pool = sorted(
        [p for p in picks if p["position"] in FLEX_ELIGIBLE and (p["player_name"], p["position"]) not in used_keys],
        key=lambda p: p["position_finish"],
    )
    if flex_pool:
        total += flex_pool[0]["position_finish"]
        used.append(flex_pool[0])
        used_keys.add((flex_pool[0]["player_name"], flex_pool[0]["position"]))

    bench_pool = sorted(
        [p for p in picks if p["position"] in FLEX_ELIGIBLE and (p["player_name"], p["position"]) not in used_keys],
        key=lambda p: p["position_finish"],
    )
    for weight, p in zip(BENCH_WEIGHTS, bench_pool[:3]):
        total += weight * p["position_finish"]

    best_starter = min(used, key=lambda p: p["position_finish"])
    return total, best_starter


def method_1_point_volume(db: sqlite3.Connection):
    results = []
    for year, team_id in _team_years(db):
        picks = _picks(db, year, team_id)
        total = sum(p["season_points"] for p in picks)
        top = max(picks, key=lambda p: p["season_points"])
        results.append((total, year, team_id, top["player_name"]))
    results.sort(reverse=True)
    top5 = results[:5]
    table = _md_table(
        ["Rank", "Year", "Owner", "Total draft-class points", "Top scorer"],
        [[i + 1, year, _owner(db, year, tid), round(total, 1), name]
         for i, (total, year, tid, name) in enumerate(top5)],
    )
    full = [(total, year, tid) for total, year, tid, _ in results]
    return table, [(year, tid) for _, year, tid, _ in top5], full


def method_2_best_lineup(db: sqlite3.Connection):
    results = []
    for year, team_id in _team_years(db):
        picks = _picks(db, year, team_id)
        total, top_starter = _best_lineup_by_points(picks)
        results.append((total, year, team_id, top_starter["player_name"]))
    results.sort(reverse=True)
    top5 = results[:5]
    table = _md_table(
        ["Rank", "Year", "Owner", "Best-lineup points (9 starters)", "Best starter"],
        [[i + 1, year, _owner(db, year, tid), round(total, 1), name]
         for i, (total, year, tid, name) in enumerate(top5)],
    )
    full = [(total, year, tid) for total, year, tid, _ in results]
    return table, [(year, tid) for _, year, tid, _ in top5], full


def method_3_paco(db: sqlite3.Connection):
    results = []
    for year, team_id in _team_years(db, min_year=2019):
        picks = _picks(db, year, team_id)
        scored = _paco_score(picks)
        if scored is None:
            continue
        total, best_starter = scored
        pos_label = f"{best_starter['position']}{best_starter['position_finish']}"
        results.append((total, year, team_id, best_starter["player_name"], pos_label))
    results.sort()  # lowest total wins
    top5 = results[:5]
    table = _md_table(
        ["Rank", "Year", "Owner", "Rank score (lower is better)", "Best finisher"],
        [[i + 1, year, _owner(db, year, tid), round(total, 2), f"{name} ({pos_label})"]
         for i, (total, year, tid, name, pos_label) in enumerate(top5)],
    )
    full = [(total, year, tid) for total, year, tid, _, _ in results]
    return table, [(year, tid) for _, year, tid, _, _ in top5], full


def method_4_started_points(db: sqlite3.Connection):
    """Vinny method: cumulative points scored ONLY in weeks you actually
    started a player you drafted (weekly_rosters only ever contains real
    starters, so this join naturally excludes benched weeks and any weeks a
    traded-away player scored for a DIFFERENT team). No 2018 (no weekly box
    score data that year at all for this league).

    REGULAR SEASON ONLY (week <= seasons.reg_season_weeks) -- this league's 2
    playoff weeks each compress a variable number of real NFL weeks per team
    (confirmed: some teams' playoff-week roster snapshots have 12-16 rows
    where a normal week has 9), so including them would both (a) make this
    number exceed standings.points_for, which is itself a regular-season-only
    stat, and (b) not be a fair apples-to-apples comparison across teams,
    since different teams get a different amount of "extra" real football
    compressed into the same 2 fantasy weeks depending on their bracket path."""
    rows = db.execute("""
        SELECT dp.year, dp.team_id, t.owner_name, SUM(wr.points) AS total_started_points
        FROM draft_picks dp
        JOIN weekly_rosters wr ON wr.year=dp.year AND wr.team_id=dp.team_id AND wr.player_id=dp.player_id
        JOIN teams t ON t.year=dp.year AND t.team_id=dp.team_id
        JOIN seasons s ON s.year=dp.year
        WHERE wr.week <= s.reg_season_weeks
        GROUP BY dp.year, dp.team_id
        ORDER BY total_started_points DESC
    """).fetchall()
    top5 = rows[:5]
    table = _md_table(
        ["Rank", "Year", "Owner", "Points from starters you drafted"],
        [[i + 1, r["year"], r["owner_name"], round(r["total_started_points"], 1)] for i, r in enumerate(top5)],
    )
    full = [(r["total_started_points"], r["year"], r["team_id"]) for r in rows]
    return table, [(r["year"], r["team_id"]) for r in top5], full


def method_5_best_ball(db: sqlite3.Connection):
    """Drafted best ball: for each regular-season week, build the best
    possible QB/RB/RB/WR/WR/TE/FLEX lineup out of everyone you drafted using
    REAL per-week points (independent of who was actually started that
    week -- from weekly_player_points, a new backfill built specifically for
    this, since weekly_rosters only ever has actual starters). K/D-ST use
    whatever that team actually started that week (weekly_player_points
    deliberately doesn't cover K/D-ST -- confirmed no public per-game data
    source exists for those two positions at all).

    REGULAR SEASON ONLY -- playoff weeks (14/15) are excluded entirely, not
    just from the best-ball reconstruction (already true) but also from the
    K/D-ST actual-points portion this method used to add on top. Confirmed
    those 2 playoff weeks compress a variable number of real NFL weeks per
    team (some teams' roster snapshots have 12-16 rows where a normal week
    has 9), so adding them wasn't a fair apples-to-apples comparison across
    teams -- matches Method 4's same fix. No 2018 (weekly_rosters, needed for
    the K/D-ST portion, has no data that year)."""
    results = []
    years = [r[0] for r in db.execute(
        "SELECT DISTINCT year FROM draft_picks WHERE year != 2018 ORDER BY year"
    ).fetchall()]

    for year in years:
        season = db.execute("SELECT reg_season_weeks FROM seasons WHERE year=?", (year,)).fetchone()
        if not season:
            continue
        reg_season_weeks = season["reg_season_weeks"]

        points_by_player_week: dict[int, dict[int, float]] = {}
        for r in db.execute("SELECT week, player_id, points FROM weekly_player_points WHERE year=?", (year,)).fetchall():
            points_by_player_week.setdefault(r["player_id"], {})[r["week"]] = r["points"]

        kdst_by_team_week: dict[int, dict[int, float]] = {}
        for r in db.execute(
            "SELECT week, team_id, SUM(points) AS p FROM weekly_rosters "
            "WHERE year=? AND position IN ('K','D/ST') GROUP BY week, team_id", (year,)
        ).fetchall():
            kdst_by_team_week.setdefault(r["team_id"], {})[r["week"]] = r["p"]

        team_ids = [r[0] for r in db.execute("SELECT DISTINCT team_id FROM draft_picks WHERE year=?", (year,)).fetchall()]
        for team_id in team_ids:
            player_positions = {
                r["player_id"]: r["position"] for r in db.execute(
                    "SELECT player_id, position FROM draft_picks WHERE year=? AND team_id=? "
                    "AND position IN ('QB','RB','WR','TE')", (year, team_id)
                ).fetchall()
            }

            total = 0.0
            for week in range(1, reg_season_weeks + 1):
                by_pos: dict[str, list[float]] = {}
                for pid, pos in player_positions.items():
                    pts = points_by_player_week.get(pid, {}).get(week)
                    if pts is not None:
                        by_pos.setdefault(pos, []).append(pts)
                for pos in by_pos:
                    by_pos[pos].sort(reverse=True)

                week_total = 0.0
                for pos, need in (("QB", 1), ("RB", 2), ("WR", 2), ("TE", 1)):
                    week_total += sum(by_pos.get(pos, [])[:need])

                flex_pool: list[float] = []
                for pos, used in (("RB", 2), ("WR", 2), ("TE", 1)):
                    flex_pool.extend(by_pos.get(pos, [])[used:])
                flex_pool.sort(reverse=True)
                if flex_pool:
                    week_total += flex_pool[0]

                week_total += kdst_by_team_week.get(team_id, {}).get(week, 0.0)
                total += week_total

            results.append((total, year, team_id))

    results.sort(reverse=True)
    top5 = results[:5]
    table = _md_table(
        ["Rank", "Year", "Owner", "Best-ball season total"],
        [[i + 1, year, _owner(db, year, tid), round(total, 1)] for i, (total, year, tid) in enumerate(top5)],
    )
    return table, [(year, tid) for _, year, tid in top5], results


def build_best_draft_post(db: sqlite3.Connection) -> tuple[str, str, str]:
    title = "The Best Draft of All Time — By the League's Own Rules"
    excerpt = (
        "Five specific, argued-over methods for judging a draft: point volume, best "
        "lineup, the Paco method, started points, and drafted best ball. Who wins each?"
    )

    m1_table, m1_teams, m1_full = method_1_point_volume(db)
    m2_table, m2_teams, m2_full = method_2_best_lineup(db)
    m3_table, m3_teams, m3_full = method_3_paco(db)
    m4_table, m4_teams, m4_full = method_4_started_points(db)
    m5_table, m5_teams, m5_full = method_5_best_ball(db)

    from collections import Counter
    overlap = Counter()
    for teams in (m1_teams, m2_teams, m3_teams, m4_teams, m5_teams):
        for t in set(teams):
            overlap[t] += 1

    def _fmt_teams(pairs) -> str:
        return "; ".join(f"{_owner(db, y, t)}'s {y} draft" for y, t in sorted(pairs))

    max_count = max(overlap.values()) if overlap else 0
    top_overlap = {t for t, c in overlap.items() if c == max_count}
    remaining_counts = [c for c in overlap.values() if c < max_count]
    second_count = max(remaining_counts) if remaining_counts else 0
    second_overlap = {t for t, c in overlap.items() if c == second_count} if second_count >= 2 else set()

    if max_count >= 2:
        consensus_line = (
            f"**{_fmt_teams(top_overlap)}** shows up in the top 5 of {max_count} of the 5 methods — "
            f"the closest thing to a consensus this data produces."
        )
    else:
        consensus_line = "No single draft cracked the top 5 of more than one method this time — five genuinely different lenses, five different winners."

    near_miss_line = f"Showing up in {second_count} of the 5: {_fmt_teams(second_overlap)}." if second_overlap else ""

    # Vinny's claim, checked: his most recent draft against all 5 rankings.
    vinny_row = db.execute(
        "SELECT MAX(t.year) AS year, t.team_id FROM teams t WHERE t.owner_name='Vincent Zahm'"
    ).fetchone()
    vinny_section = ""
    if vinny_row and vinny_row["year"]:
        vy, vt = vinny_row["year"], vinny_row["team_id"]
        rank_rows = []
        for label, full, higher_better in [
            ("Method 1 — Pure point volume", m1_full, True),
            ("Method 2 — Best starting lineup", m2_full, True),
            ("Method 3 — The Paco method", m3_full, False),
            ("Method 4 — The Vinny method", m4_full, True),
            ("Method 5 — Drafted best ball", m5_full, True),
        ]:
            found = _rank_lookup(full, vy, vt)
            if found:
                rank, score, total = found
                rank_rows.append([label, f"{rank} of {total}", round(score, 2)])
            else:
                rank_rows.append([label, "n/a", "n/a"])
        vinny_table = _md_table(["Method", "Rank", "Score"], rank_rows)
        vinny_section = f"""
## Vinny claims he had the best draft of all time. Let's check.

Vinny's own {vy} draft, ranked against every draft in league history by all 5 methods
above:

{vinny_table}

Middling on raw volume and hypothetical-best-lineup construction, rough by the Paco
method's positional-pedigree standard — but a legitimate top-10-all-time finish on
both methods that measure what actually happened on the field, including a top-3 all
time on his own namesake method. He didn't necessarily draft the most talented team on
paper, but he got real, actual value out of starting the right guys at the right time.
"""

    body = f"""Every league argues about this, and it never gets settled because everyone's using
their own criteria. So here are five specific, agreed-on methods — same underlying
pick-by-pick and weekly data — each with its own top 5.

## Method 1 — Pure point volume

However many points every player you drafted scored that season, added up. No
normalization, no adjustment — just total production from your draft class.

{m1_table}

## Method 2 — Best starting lineup

Take your draft class and build the best possible lineup out of it, using this
league's real starting shape (1 QB, 2 RB, 2 WR, 1 TE, 1 FLEX, 1 K, 1 D/ST) — your
highest scorer at each position, plus whichever of your remaining RB/WR/TEs scored
the most as the flex. Cumulative points from those 9 slots.

{m2_table}

## Method 3 — The Paco method

Same 9-slot lineup as Method 2, but instead of picking (and scoring) by points, it's
based on each player's finishing position that season — RB1 beats RB7, regardless of
raw points. On top of the 9 starters, your best 3 remaining bench flex options (RB/WR/TE)
get folded in too, but discounted: your top bench flex only counts at 75%, the second
at 50%, and the third at 25%. Everything is summed as rank numbers, so **lowest total
wins** — a QB1 + RB1 lineup beats a QB5 + RB9 one. Only computable for 2019 onward,
since positional finish data doesn't exist for earlier drafts.

{m3_table}

## Method 4 — The Vinny method

Cumulative point volume, but *only* counting weeks you actually started a player you
drafted — no credit for production that sat on your bench, and no credit for what a
player did after you traded them away. Real lineup decisions, not hypotheticals.
Regular season only — this league's 2 playoff weeks each compress a different amount
of real NFL football depending on a team's bracket path, so including them wouldn't be
a fair comparison across different teams' playoff runs.

{m4_table}

## Method 5 — Drafted best ball

The best possible lineup you could have started each week, all regular season,
picking whichever of your drafted players actually had the better week — even if you
benched them at the time. If you drafted two WRs and started one for 10 while the
other scored 20 on your bench, this method gives you the 20. K/D-ST use whatever you
actually started (no reliable per-game data exists for reconstructing those two
positions' bench weeks). Regular season only, same reason as Method 4.

{m5_table}
{vinny_section}
## So who's actually the best?

{consensus_line} {near_miss_line}

Five different definitions, five different flavors of "best" — pure volume, real
lineup construction, positional pedigree, actual lineup decisions, and hindsight best
ball. Pick whichever one matches your argument.
"""
    return title, excerpt, body


def main() -> None:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    ensure_table(con)

    title, excerpt, body = build_draft_intel_post(con)
    insert_post(con, title, body, excerpt, cta_url="/draft-intel", cta_label="Open the live Draft Intel dashboard")

    title, excerpt, body = build_best_draft_post(con)
    upsert_post(con, "The Best Draft of All Time", title, body, excerpt)

    con.close()


if __name__ == "__main__":
    main()
