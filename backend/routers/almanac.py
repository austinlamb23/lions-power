from fastapi import APIRouter, Depends, Query
from typing import Optional
import sqlite3
from database import get_db

router = APIRouter(prefix="/api/almanac", tags=["almanac"])


def _get_legacy_h2h(db: sqlite3.Connection, key_col: str, a, b):
    """Look up an unverified pre-2013 head-to-head record between two owner_names
    (key_col='owner') or two team_ids (key_col='team_id'), oriented from a's perspective."""
    a_col, b_col = f"{key_col}_a", f"{key_col}_b"
    row = db.execute(
        f"SELECT * FROM legacy_h2h WHERE ({a_col} = ? AND {b_col} = ?) OR ({a_col} = ? AND {b_col} = ?)",
        (a, b, b, a)
    ).fetchone()
    if not row:
        return None
    if row[a_col] == a:
        return {"wins": row["wins_a"], "losses": row["wins_b"], "ties": row["ties"], "note": row["note"]}
    return {"wins": row["wins_b"], "losses": row["wins_a"], "ties": row["ties"], "note": row["note"]}


def _reconstruct_trades(db: sqlite3.Connection, year: int = None):
    """One entry per real trade event (not per sibling stub record). ESPN
    splits a single trade into multiple TRADE_ACCEPT rows sharing the same
    related_transaction_id (a literal shared key, not a pointer to another
    row's own id) — usually only one of them carries the actual item data,
    the rest are empty administrative stubs. Items are unioned across the
    whole group so data split across records (rare) is still captured.

    IMPORTANT: full item detail is only actually recoverable for a minority
    of historical trades (~13%, confirmed by direct testing against ESPN's
    API) — most TRADE_ACCEPT groups have zero recoverable items, a genuine
    upstream data gap, not a bug. Every trade is still returned; `complete`
    flags whether real "who got who" detail exists for that one."""
    query = "SELECT * FROM transactions WHERE type='TRADE_ACCEPT'"
    params = []
    if year:
        query += " AND year=?"
        params.append(year)
    rows = [dict(r) for r in db.execute(query, params).fetchall()]

    groups = {}
    for r in rows:
        key = r["related_transaction_id"] or r["id"]
        groups.setdefault(key, []).append(r)

    trades = []
    for key, txns in groups.items():
        ids = [t["id"] for t in txns]
        placeholders = ",".join("?" * len(ids))
        raw_items = [dict(i) for i in db.execute(
            f"SELECT * FROM transaction_items WHERE transaction_id IN ({placeholders})", ids
        ).fetchall()]
        # The same real action (e.g. a roster-cut made as part of the trade)
        # can appear on more than one sibling record — dedupe by the actual
        # move, not the row it happened to be attached to.
        seen = set()
        items = []
        for i in raw_items:
            dedup_key = (i["player_id"], i["from_team_id"], i["to_team_id"])
            if dedup_key not in seen:
                seen.add(dedup_key)
                items.append(i)

        team_ids_involved = sorted(
            ({i["from_team_id"] for i in items} | {i["to_team_id"] for i in items}) - {0}
        )
        sides = []
        for tid in team_ids_involved:
            team_row = db.execute(
                "SELECT owner_name, team_name FROM teams WHERE team_id = ? ORDER BY year DESC LIMIT 1", (tid,)
            ).fetchone()
            sides.append({
                "team_id": tid,
                "owner_name": team_row["owner_name"] if team_row else None,
                "team_name": team_row["team_name"] if team_row else None,
                "received": [i["player_name"] for i in items if i["to_team_id"] == tid],
                "gave_up": [i["player_name"] for i in items if i["from_team_id"] == tid],
            })

        # Prefer the week/date of whichever sibling record actually carried
        # the item data (or failing that, whichever is EXECUTED) — the
        # group's first record by query order is often an empty stub from
        # an earlier proposal step, not the trade's real resolution point.
        item_bearing_ids = {i["transaction_id"] for i in raw_items}
        base = (
            next((t for t in txns if t["id"] in item_bearing_ids), None)
            or next((t for t in txns if t["status"] == "EXECUTED"), None)
            or txns[0]
        )
        trades.append({
            "year": base["year"],
            "week": base["week"],
            "date": base["date"],
            "sides": sides,
            "complete": len(sides) >= 2 and len(items) >= 2,
        })

    return trades


@router.get("/seasons")
def get_seasons(db: sqlite3.Connection = Depends(get_db)):
    rows = db.execute("SELECT * FROM seasons ORDER BY year DESC").fetchall()
    return [dict(r) for r in rows]


@router.get("/owners")
def get_owners(db: sqlite3.Connection = Depends(get_db)):
    rows = db.execute(
        "SELECT DISTINCT owner_name FROM teams ORDER BY owner_name"
    ).fetchall()
    return [r["owner_name"] for r in rows]


@router.get("/standings")
def get_standings(
    year: Optional[int] = None,
    owner: Optional[str] = None,
    game_type: str = Query(default="regular", enum=["regular", "playoff", "all"]),
    db: sqlite3.Connection = Depends(get_db),
):
    query = """
        WITH playoff_pts AS (
            SELECT year, home_team_id AS team_id, SUM(home_score) AS pts FROM matchups WHERE is_playoff = 1 GROUP BY year, home_team_id
            UNION ALL
            SELECT year, away_team_id, SUM(away_score) FROM matchups WHERE is_playoff = 1 GROUP BY year, away_team_id
        ),
        playoff_by_year AS (
            SELECT year, team_id, SUM(pts) AS pts FROM playoff_pts GROUP BY year, team_id
        )
        SELECT
            s.year,
            t.owner_name,
            t.team_name,
            t.team_id,
            s.wins,
            s.losses,
            s.ties,
            s.playoff_wins,
            s.playoff_losses,
            s.points_for AS reg_points,
            COALESCE(pp.pts, 0) AS playoff_points,
            ROUND(s.points_for + COALESCE(pp.pts, 0), 2) AS total_points,
            s.final_standing,
            CASE
                WHEN :game_type = 'regular' THEN
                    ROUND(CAST(s.wins AS FLOAT) / NULLIF(s.wins + s.losses + s.ties, 0), 3)
                WHEN :game_type = 'playoff' THEN
                    ROUND(CAST(COALESCE(s.playoff_wins,0) AS FLOAT) / NULLIF(COALESCE(s.playoff_wins,0) + COALESCE(s.playoff_losses,0), 0), 3)
                ELSE
                    ROUND(CAST(s.wins + COALESCE(s.playoff_wins,0) AS FLOAT) / NULLIF(s.wins + COALESCE(s.playoff_wins,0) + s.losses + COALESCE(s.playoff_losses,0) + s.ties, 0), 3)
            END AS win_pct
        FROM standings s
        JOIN teams t ON s.year = t.year AND s.team_id = t.team_id
        LEFT JOIN playoff_by_year pp ON s.year = pp.year AND s.team_id = pp.team_id
        WHERE 1=1
    """
    params: dict = {"game_type": game_type}

    if year:
        query += " AND s.year = :year"
        params["year"] = year
    if owner:
        query += " AND t.owner_name = :owner"
        params["owner"] = owner

    query += " ORDER BY s.year DESC, s.final_standing ASC"

    rows = db.execute(query, params).fetchall()
    return [dict(r) for r in rows]


@router.get("/standings/summary")
def get_standings_summary(
    game_type: str = Query(default="regular", enum=["regular", "playoff", "all"]),
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
    db: sqlite3.Connection = Depends(get_db),
):
    """Aggregate career stats per manager, ranked by wins."""
    rows = db.execute("""
        WITH last_place_teams AS (
            SELECT year, team_id FROM (
                SELECT year, team_id,
                       ROW_NUMBER() OVER (PARTITION BY year ORDER BY wins ASC, points_for ASC) AS rk
                FROM standings
            ) WHERE rk = 1
        ),
        playoff_pts AS (
            SELECT t.owner_name,
                   ROUND(SUM(CASE WHEN m.home_team_id = t.team_id THEN m.home_score ELSE m.away_score END), 2) AS pts,
                   COUNT(*) AS games
            FROM matchups m
            JOIN teams t ON m.year = t.year AND (m.home_team_id = t.team_id OR m.away_team_id = t.team_id)
            WHERE m.is_playoff = 1
              AND (:year_from IS NULL OR m.year >= :year_from)
              AND (:year_to IS NULL OR m.year <= :year_to)
            GROUP BY t.owner_name
        )
        SELECT
            t.owner_name,
            COUNT(*) as seasons,
            SUM(s.wins) as reg_wins,
            SUM(s.losses) as reg_losses,
            SUM(s.ties) as reg_ties,
            SUM(COALESCE(s.playoff_wins, 0)) as playoff_wins,
            SUM(COALESCE(s.playoff_losses, 0)) as playoff_losses,
            SUM(s.wins + COALESCE(s.playoff_wins, 0)) as total_wins,
            SUM(s.losses + COALESCE(s.playoff_losses, 0)) as total_losses,
            SUM(s.ties) as total_ties,
            ROUND(SUM(s.points_for), 2) as reg_points,
            COALESCE(MAX(pp.pts), 0) as playoff_points,
            COALESCE(MAX(pp.games), 0) as playoff_games,
            ROUND(SUM(s.points_for) + COALESCE(MAX(pp.pts), 0), 2) as total_points,
            SUM(CASE WHEN s.final_standing = 1 THEN 1 ELSE 0 END)
                + COALESCE((
                    SELECT COUNT(*) FROM legacy_champions lc
                    WHERE lc.owner_name = t.owner_name
                      AND (:year_from IS NULL OR lc.year >= :year_from)
                      AND (:year_to IS NULL OR lc.year <= :year_to)
                  ), 0) as championships,
            COALESCE((
                SELECT COUNT(*) FROM legacy_champions lc
                WHERE lc.owner_name = t.owner_name
                  AND (:year_from IS NULL OR lc.year >= :year_from)
                  AND (:year_to IS NULL OR lc.year <= :year_to)
              ), 0) as legacy_championships,
            SUM(CASE WHEN lpt.team_id IS NOT NULL THEN 1 ELSE 0 END) as last_place,
            SUM(CASE WHEN s.playoff_wins IS NOT NULL THEN 1 ELSE 0 END) as playoff_appearances
        FROM standings s
        JOIN teams t ON s.year = t.year AND s.team_id = t.team_id
        LEFT JOIN playoff_pts pp ON t.owner_name = pp.owner_name
        LEFT JOIN last_place_teams lpt ON s.year = lpt.year AND s.team_id = lpt.team_id
        WHERE (:year_from IS NULL OR s.year >= :year_from)
          AND (:year_to IS NULL OR s.year <= :year_to)
        GROUP BY t.owner_name
        ORDER BY total_wins DESC
    """, {"year_from": year_from, "year_to": year_to}).fetchall()
    return [dict(r) for r in rows]


@router.get("/matchups")
def get_matchups(
    year: Optional[int] = None,
    week: Optional[int] = None,
    playoff_only: bool = False,
    db: sqlite3.Connection = Depends(get_db),
):
    query = """
        SELECT
            m.year, m.week, m.matchup_type, m.is_playoff,
            m.home_score, m.away_score,
            ht.owner_name as home_owner, ht.team_name as home_team,
            at.owner_name as away_owner, at.team_name as away_team
        FROM matchups m
        JOIN teams ht ON m.year = ht.year AND m.home_team_id = ht.team_id
        JOIN teams at ON m.year = at.year AND m.away_team_id = at.team_id
        WHERE 1=1
    """
    params: dict = {}

    if year:
        query += " AND m.year = :year"
        params["year"] = year
    if week:
        query += " AND m.week = :week"
        params["week"] = week
    if playoff_only:
        query += " AND m.is_playoff = 1"

    query += " ORDER BY m.year DESC, m.week ASC"

    rows = db.execute(query, params).fetchall()
    return [dict(r) for r in rows]


@router.get("/standings/teams")
def get_team_standings_summary(
    game_type: str = Query(default="regular", enum=["regular", "playoff", "all"]),
    db: sqlite3.Connection = Depends(get_db),
):
    """Aggregate career stats per franchise (team_id), ranked by wins."""
    rows = db.execute("""
        WITH last_place_teams AS (
            SELECT year, team_id FROM (
                SELECT year, team_id,
                       ROW_NUMBER() OVER (PARTITION BY year ORDER BY wins ASC, points_for ASC) AS rk
                FROM standings
            ) WHERE rk = 1
        ),
        playoff_pts AS (
            SELECT t.team_id,
                   ROUND(SUM(CASE WHEN m.home_team_id = t.team_id THEN m.home_score ELSE m.away_score END), 2) AS pts,
                   COUNT(*) AS games
            FROM matchups m
            JOIN teams t ON m.year = t.year AND (m.home_team_id = t.team_id OR m.away_team_id = t.team_id)
            WHERE m.is_playoff = 1
            GROUP BY t.team_id
        )
        SELECT
            s.team_id,
            (SELECT owner_name FROM teams WHERE team_id = s.team_id ORDER BY year DESC LIMIT 1) as current_manager,
            GROUP_CONCAT(DISTINCT t.owner_name) as all_managers,
            COUNT(*) as seasons,
            SUM(s.wins) as reg_wins,
            SUM(s.losses) as reg_losses,
            SUM(s.ties) as reg_ties,
            SUM(COALESCE(s.playoff_wins, 0)) as playoff_wins,
            SUM(COALESCE(s.playoff_losses, 0)) as playoff_losses,
            SUM(s.wins + COALESCE(s.playoff_wins, 0)) as total_wins,
            SUM(s.losses + COALESCE(s.playoff_losses, 0)) as total_losses,
            SUM(s.ties) as total_ties,
            ROUND(SUM(s.points_for), 2) as reg_points,
            COALESCE(MAX(pp.pts), 0) as playoff_points,
            COALESCE(MAX(pp.games), 0) as playoff_games,
            ROUND(SUM(s.points_for) + COALESCE(MAX(pp.pts), 0), 2) as total_points,
            SUM(CASE WHEN s.final_standing = 1 THEN 1 ELSE 0 END)
                + COALESCE((SELECT COUNT(*) FROM legacy_champions lc WHERE lc.team_id = s.team_id), 0) as championships,
            COALESCE((SELECT COUNT(*) FROM legacy_champions lc WHERE lc.team_id = s.team_id), 0) as legacy_championships,
            SUM(CASE WHEN lpt.team_id IS NOT NULL THEN 1 ELSE 0 END) as last_place,
            SUM(CASE WHEN s.playoff_wins IS NOT NULL THEN 1 ELSE 0 END) as playoff_appearances
        FROM standings s
        JOIN teams t ON s.year = t.year AND s.team_id = t.team_id
        LEFT JOIN playoff_pts pp ON s.team_id = pp.team_id
        LEFT JOIN last_place_teams lpt ON s.year = lpt.year AND s.team_id = lpt.team_id
        GROUP BY s.team_id
        ORDER BY total_wins DESC
    """).fetchall()
    return [dict(r) for r in rows]


@router.get("/team/{team_id}")
def get_team_profile(team_id: int, db: sqlite3.Connection = Depends(get_db)):
    """Full profile for a franchise — career stats + year-by-year with manager info."""
    career = db.execute("""
        SELECT
            s.team_id,
            COUNT(*) as seasons,
            SUM(s.wins) as reg_wins,
            SUM(s.losses) as reg_losses,
            SUM(s.ties) as reg_ties,
            SUM(COALESCE(s.playoff_wins,0)) as playoff_wins,
            SUM(COALESCE(s.playoff_losses,0)) as playoff_losses,
            ROUND(SUM(s.points_for), 2) as total_points,
            SUM(CASE WHEN s.final_standing = 1 THEN 1 ELSE 0 END)
                + COALESCE((SELECT COUNT(*) FROM legacy_champions lc WHERE lc.team_id = s.team_id), 0) as championships,
            COALESCE((SELECT COUNT(*) FROM legacy_champions lc WHERE lc.team_id = s.team_id), 0) as legacy_championships,
            SUM(CASE WHEN s.final_standing <= 2 THEN 1 ELSE 0 END) as podium_finishes
        FROM standings s
        WHERE s.team_id = ?
    """, (team_id,)).fetchone()

    seasons = db.execute("""
        WITH non_playoff_ranks AS (
            SELECT year, team_id,
                   4 + ROW_NUMBER() OVER (PARTITION BY year ORDER BY wins DESC, points_for DESC) AS rank
            FROM standings
            WHERE playoff_wins IS NULL
        )
        SELECT s.year, t.owner_name, t.team_name, s.wins, s.losses, s.ties,
               s.playoff_wins, s.playoff_losses, s.points_for,
               CASE WHEN s.playoff_wins IS NOT NULL THEN s.final_standing ELSE npr.rank END as final_standing
        FROM standings s
        JOIN teams t ON s.year = t.year AND s.team_id = t.team_id
        LEFT JOIN non_playoff_ranks npr ON s.year = npr.year AND s.team_id = npr.team_id
        WHERE s.team_id = ?
        ORDER BY s.year DESC
    """, (team_id,)).fetchall()

    current = db.execute(
        "SELECT owner_name FROM teams WHERE team_id = ? ORDER BY year DESC LIMIT 1",
        (team_id,)
    ).fetchone()

    return {
        "team_id": team_id,
        "current_manager": current["owner_name"] if current else None,
        "career": dict(career),
        "seasons": [dict(r) for r in seasons]
    }


@router.get("/team/{team_id}/h2h")
def get_team_h2h(team_id: int, db: sqlite3.Connection = Depends(get_db)):
    """Head-to-head record for a franchise vs every other franchise (2013+, plus
    any unverified pre-2013 legacy record)."""
    rows = db.execute("""
        WITH my_games AS (
            SELECT away_team_id AS opp_team_id, home_score AS my_score, away_score AS opp_score
            FROM matchups WHERE home_team_id = ?
              AND matchup_type IN ('NONE', 'WINNERS_BRACKET')
            UNION ALL
            SELECT home_team_id, away_score, home_score
            FROM matchups WHERE away_team_id = ?
              AND matchup_type IN ('NONE', 'WINNERS_BRACKET')
        )
        SELECT
            g.opp_team_id,
            (SELECT owner_name FROM teams WHERE team_id = g.opp_team_id ORDER BY year DESC LIMIT 1) AS opponent,
            COUNT(*) AS games,
            SUM(CASE WHEN g.my_score > g.opp_score THEN 1 ELSE 0 END) AS wins,
            SUM(CASE WHEN g.my_score < g.opp_score THEN 1 ELSE 0 END) AS losses,
            SUM(CASE WHEN g.my_score = g.opp_score THEN 1 ELSE 0 END) AS ties,
            ROUND(AVG(g.my_score), 1) AS avg_pts_for,
            ROUND(AVG(g.opp_score), 1) AS avg_pts_against
        FROM my_games g
        GROUP BY g.opp_team_id
        ORDER BY wins DESC, games DESC
    """, (team_id, team_id)).fetchall()

    result = {r["opp_team_id"]: {**dict(r), "has_legacy_h2h": False} for r in rows}

    legacy_rows = db.execute(
        "SELECT * FROM legacy_h2h WHERE team_id_a = ? OR team_id_b = ?", (team_id, team_id)
    ).fetchall()
    for lr in legacy_rows:
        if lr["team_id_a"] == team_id:
            opp_id, l_wins, l_losses = lr["team_id_b"], lr["wins_a"], lr["wins_b"]
        else:
            opp_id, l_wins, l_losses = lr["team_id_a"], lr["wins_b"], lr["wins_a"]
        l_ties = lr["ties"]
        if opp_id in result:
            row = result[opp_id]
            row["wins"] += l_wins
            row["losses"] += l_losses
            row["ties"] += l_ties
            row["games"] += l_wins + l_losses + l_ties
        else:
            opponent = db.execute(
                "SELECT owner_name FROM teams WHERE team_id = ? ORDER BY year DESC LIMIT 1", (opp_id,)
            ).fetchone()
            result[opp_id] = {
                "opp_team_id": opp_id,
                "opponent": opponent["owner_name"] if opponent else None,
                "games": l_wins + l_losses + l_ties,
                "wins": l_wins, "losses": l_losses, "ties": l_ties,
                "avg_pts_for": None, "avg_pts_against": None,
            }
        result[opp_id]["has_legacy_h2h"] = True

    return sorted(result.values(), key=lambda r: (-r["wins"], -r["games"]))


@router.get("/team/{team_id}/h2h/{opponent_id}")
def get_team_h2h_series(team_id: int, opponent_id: int, db: sqlite3.Connection = Depends(get_db)):
    """Full game-by-game series between two franchises (2013+, real games only)."""
    games = db.execute("""
        SELECT
            m.year, m.week, m.is_playoff, m.matchup_type,
            CASE WHEN m.home_team_id = :team_id THEN m.home_score ELSE m.away_score END AS my_score,
            CASE WHEN m.home_team_id = :team_id THEN m.away_score ELSE m.home_score END AS opp_score,
            CASE WHEN m.home_team_id = :team_id THEN ht.team_name ELSE at.team_name END AS my_team_name,
            CASE WHEN m.home_team_id = :team_id THEN at.team_name ELSE ht.team_name END AS opp_team_name
        FROM matchups m
        JOIN teams ht ON m.year = ht.year AND m.home_team_id = ht.team_id
        JOIN teams at ON m.year = at.year AND m.away_team_id = at.team_id
        WHERE ((m.home_team_id = :team_id AND m.away_team_id = :opponent_id)
            OR (m.home_team_id = :opponent_id AND m.away_team_id = :team_id))
          AND m.matchup_type IN ('NONE', 'WINNERS_BRACKET')
        ORDER BY m.year, m.week
    """, {"team_id": team_id, "opponent_id": opponent_id}).fetchall()

    me = db.execute(
        "SELECT owner_name FROM teams WHERE team_id = ? ORDER BY year DESC LIMIT 1", (team_id,)
    ).fetchone()
    opp = db.execute(
        "SELECT owner_name FROM teams WHERE team_id = ? ORDER BY year DESC LIMIT 1", (opponent_id,)
    ).fetchone()

    return {
        "me": {"team_id": team_id, "owner_name": me["owner_name"] if me else None},
        "opponent": {"team_id": opponent_id, "owner_name": opp["owner_name"] if opp else None},
        "games": [dict(r) for r in games],
        "legacy": _get_legacy_h2h(db, "team_id", team_id, opponent_id),
    }


@router.get("/owner/{owner_name}/h2h")
def get_owner_h2h(owner_name: str, db: sqlite3.Connection = Depends(get_db)):
    """Head-to-head record for a manager vs every other manager (2013+, plus
    any unverified pre-2013 legacy record)."""
    rows = db.execute("""
        WITH my_games AS (
            SELECT
                CASE WHEN ht.owner_name = ? THEN at.owner_name ELSE ht.owner_name END AS opp_owner,
                CASE WHEN ht.owner_name = ? THEN m.home_score ELSE m.away_score END AS my_score,
                CASE WHEN ht.owner_name = ? THEN m.away_score ELSE m.home_score END AS opp_score
            FROM matchups m
            JOIN teams ht ON m.year = ht.year AND m.home_team_id = ht.team_id
            JOIN teams at ON m.year = at.year AND m.away_team_id = at.team_id
            WHERE (ht.owner_name = ? OR at.owner_name = ?)
              AND m.matchup_type IN ('NONE', 'WINNERS_BRACKET')
        )
        SELECT
            opp_owner,
            COUNT(*) AS games,
            SUM(CASE WHEN my_score > opp_score THEN 1 ELSE 0 END) AS wins,
            SUM(CASE WHEN my_score < opp_score THEN 1 ELSE 0 END) AS losses,
            SUM(CASE WHEN my_score = opp_score THEN 1 ELSE 0 END) AS ties,
            ROUND(AVG(my_score), 1) AS avg_pts_for,
            ROUND(AVG(opp_score), 1) AS avg_pts_against
        FROM my_games
        GROUP BY opp_owner
        ORDER BY wins DESC, games DESC
    """, (owner_name, owner_name, owner_name, owner_name, owner_name)).fetchall()

    result = {r["opp_owner"]: {**dict(r), "has_legacy_h2h": False} for r in rows}

    legacy_rows = db.execute(
        "SELECT * FROM legacy_h2h WHERE owner_a = ? OR owner_b = ?", (owner_name, owner_name)
    ).fetchall()
    for lr in legacy_rows:
        if lr["owner_a"] == owner_name:
            opp, l_wins, l_losses = lr["owner_b"], lr["wins_a"], lr["wins_b"]
        else:
            opp, l_wins, l_losses = lr["owner_a"], lr["wins_b"], lr["wins_a"]
        l_ties = lr["ties"]
        if opp in result:
            row = result[opp]
            row["wins"] += l_wins
            row["losses"] += l_losses
            row["ties"] += l_ties
            row["games"] += l_wins + l_losses + l_ties
        else:
            result[opp] = {
                "opp_owner": opp,
                "games": l_wins + l_losses + l_ties,
                "wins": l_wins, "losses": l_losses, "ties": l_ties,
                "avg_pts_for": None, "avg_pts_against": None,
            }
        result[opp]["has_legacy_h2h"] = True

    return sorted(result.values(), key=lambda r: (-r["wins"], -r["games"]))


@router.get("/owner/{owner_name}/h2h/{opponent_name}")
def get_owner_h2h_series(owner_name: str, opponent_name: str, db: sqlite3.Connection = Depends(get_db)):
    """Full game-by-game series between two managers (2013+, real games only)."""
    games = db.execute("""
        SELECT
            m.year, m.week, m.is_playoff, m.matchup_type,
            CASE WHEN ht.owner_name = :owner THEN m.home_score ELSE m.away_score END AS my_score,
            CASE WHEN ht.owner_name = :owner THEN m.away_score ELSE m.home_score END AS opp_score,
            CASE WHEN ht.owner_name = :owner THEN ht.team_name ELSE at.team_name END AS my_team_name,
            CASE WHEN ht.owner_name = :owner THEN at.team_name ELSE ht.team_name END AS opp_team_name
        FROM matchups m
        JOIN teams ht ON m.year = ht.year AND m.home_team_id = ht.team_id
        JOIN teams at ON m.year = at.year AND m.away_team_id = at.team_id
        WHERE ((ht.owner_name = :owner AND at.owner_name = :opponent)
            OR (ht.owner_name = :opponent AND at.owner_name = :owner))
          AND m.matchup_type IN ('NONE', 'WINNERS_BRACKET')
        ORDER BY m.year, m.week
    """, {"owner": owner_name, "opponent": opponent_name}).fetchall()

    return {
        "me": {"owner_name": owner_name},
        "opponent": {"owner_name": opponent_name},
        "games": [dict(r) for r in games],
        "legacy": _get_legacy_h2h(db, "owner", owner_name, opponent_name),
    }


@router.get("/owner/{owner_name}/draft-history")
def get_owner_draft_history(owner_name: str, db: sqlite3.Connection = Depends(get_db)):
    """Every draft pick a manager's franchise has ever made, plus light
    analytics. Enriched with each player's real NFL team, position, and
    that season's fantasy points (all years) and true NFL-wide position
    finish (2019+ only — ESPN's historical positional-rank data isn't
    reliably available before then, so it's NULL for 2013-2018 picks)."""
    rows = db.execute("""
        SELECT dp.year, dp.round_num, dp.round_pick, dp.overall_pick,
               dp.player_name, dp.player_id, dp.keeper, t.team_name,
               dp.pro_team, dp.position, dp.season_points, dp.position_finish
        FROM draft_picks dp
        JOIN teams t ON dp.year = t.year AND dp.team_id = t.team_id
        WHERE t.owner_name = ?
        ORDER BY dp.year DESC, dp.round_num ASC, dp.round_pick ASC
    """, (owner_name,)).fetchall()
    picks = [dict(r) for r in rows]

    by_year = {}
    for p in picks:
        by_year.setdefault(p["year"], {"year": p["year"], "team_name": p["team_name"], "picks": []})
        by_year[p["year"]]["picks"].append(p)
    picks_by_year = sorted(by_year.values(), key=lambda y: -y["year"])

    keeper_picks = [p for p in picks if p["keeper"]]
    first_round = sorted([p for p in picks if p["round_num"] == 1], key=lambda p: p["year"])
    best_slot = min(first_round, key=lambda p: p["round_pick"], default=None)
    worst_slot = max(first_round, key=lambda p: p["round_pick"], default=None)

    position_counts = {}
    for p in picks:
        if p["position"]:
            position_counts[p["position"]] = position_counts.get(p["position"], 0) + 1
    favorite_position = max(position_counts.items(), key=lambda kv: kv[1], default=(None, 0))

    picks_with_finish = [p for p in picks if p["position_finish"] is not None]
    best_finish = min(picks_with_finish, key=lambda p: p["position_finish"], default=None)

    return {
        "owner_name": owner_name,
        "picks_by_year": picks_by_year,
        "analytics": {
            "years_drafted": len(by_year),
            "total_picks": len(picks),
            "keeper_count": len(keeper_picks),
            "keeper_picks": keeper_picks,
            "first_round_picks": first_round,
            "best_slot": best_slot,
            "worst_slot": worst_slot,
            "favorite_position": {"position": favorite_position[0], "count": favorite_position[1]},
            "best_finish": best_finish,
        },
    }


@router.get("/divisions")
def get_divisions(
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
    db: sqlite3.Connection = Depends(get_db),
):
    """East vs West: rosters, interdivision head-to-head, and per-division
    summary stats (championships w/ full list, runner-ups, playoff
    appearances, total record). Division membership is derived per-(year,
    team_id) throughout, never assumed static across years. Optional
    year_from/year_to filters every section to a season range (both null =
    all seasons). Legacy pre-2013 champions have no division on record and
    are excluded here (they're still counted in the main Hall of Fame)."""
    params = {"year_from": year_from, "year_to": year_to}

    roster_rows = db.execute("""
        SELECT year, division, owner_name, team_name, team_id
        FROM teams
        WHERE division IS NOT NULL AND division != ''
          AND (:year_from IS NULL OR year >= :year_from)
          AND (:year_to IS NULL OR year <= :year_to)
        ORDER BY year DESC, division, owner_name
    """, params).fetchall()
    rosters = [dict(r) for r in roster_rows]

    game_rows = db.execute("""
        WITH team_division AS (
            SELECT year, team_id, division FROM teams
            WHERE division IS NOT NULL AND division != ''
        )
        SELECT m.home_score, m.away_score,
               hd.division AS home_division, ad.division AS away_division
        FROM matchups m
        JOIN team_division hd ON m.year = hd.year AND m.home_team_id = hd.team_id
        JOIN team_division ad ON m.year = ad.year AND m.away_team_id = ad.team_id
        WHERE m.matchup_type IN ('NONE', 'WINNERS_BRACKET')
          AND hd.division != ad.division
          AND (:year_from IS NULL OR m.year >= :year_from)
          AND (:year_to IS NULL OR m.year <= :year_to)
    """, params).fetchall()

    h2h = {}
    for g in game_rows:
        div_a, div_b = sorted([g["home_division"], g["away_division"]])
        key = (div_a, div_b)
        entry = h2h.setdefault(key, {
            "division_a": div_a, "division_b": div_b,
            "games": 0, "wins_a": 0, "wins_b": 0, "ties": 0,
        })
        entry["games"] += 1
        if g["home_score"] == g["away_score"]:
            entry["ties"] += 1
        else:
            winning_division = g["home_division"] if g["home_score"] > g["away_score"] else g["away_division"]
            entry["wins_a" if winning_division == div_a else "wins_b"] += 1
    interdivision_h2h = list(h2h.values())

    summary_rows = db.execute("""
        WITH playoff_pts AS (
            SELECT t.division,
                   SUM(CASE WHEN m.home_team_id = t.team_id THEN m.home_score ELSE m.away_score END) AS pts
            FROM matchups m
            JOIN teams t ON m.year = t.year AND (m.home_team_id = t.team_id OR m.away_team_id = t.team_id)
            WHERE m.is_playoff = 1
              AND t.division IS NOT NULL AND t.division != ''
              AND (:year_from IS NULL OR m.year >= :year_from)
              AND (:year_to IS NULL OR m.year <= :year_to)
            GROUP BY t.division
        )
        SELECT
            t.division,
            SUM(CASE WHEN s.final_standing = 1 THEN 1 ELSE 0 END) as championships,
            SUM(CASE WHEN s.final_standing = 2 THEN 1 ELSE 0 END) as runner_ups,
            SUM(CASE WHEN s.playoff_wins IS NOT NULL THEN 1 ELSE 0 END) as playoff_appearances,
            SUM(s.wins + COALESCE(s.playoff_wins,0)) as total_wins,
            SUM(s.losses + COALESCE(s.playoff_losses,0)) as total_losses,
            SUM(s.ties) as total_ties,
            ROUND(SUM(s.points_for) + COALESCE(MAX(pp.pts), 0), 2) as total_points
        FROM standings s
        JOIN teams t ON s.year = t.year AND s.team_id = t.team_id
        LEFT JOIN playoff_pts pp ON t.division = pp.division
        WHERE t.division IS NOT NULL AND t.division != ''
          AND (:year_from IS NULL OR s.year >= :year_from)
          AND (:year_to IS NULL OR s.year <= :year_to)
        GROUP BY t.division
        ORDER BY t.division
    """, params).fetchall()

    champ_rows = db.execute("""
        SELECT t.division, s.year, t.owner_name, t.team_name
        FROM standings s
        JOIN teams t ON s.year = t.year AND s.team_id = t.team_id
        WHERE s.final_standing = 1 AND t.division IS NOT NULL AND t.division != ''
          AND (:year_from IS NULL OR s.year >= :year_from)
          AND (:year_to IS NULL OR s.year <= :year_to)
        ORDER BY t.division, s.year DESC
    """, params).fetchall()
    champions_by_division = {}
    for r in champ_rows:
        champions_by_division.setdefault(r["division"], []).append(
            {"year": r["year"], "owner_name": r["owner_name"], "team_name": r["team_name"]}
        )

    divisions = []
    for r in summary_rows:
        d = dict(r)
        total_games = d["total_wins"] + d["total_losses"] + d["total_ties"]
        d["win_pct"] = round(d["total_wins"] / total_games, 3) if total_games else None
        d["champions_list"] = champions_by_division.get(d["division"], [])
        divisions.append(d)

    return {
        "divisions": divisions,
        "interdivision_h2h": interdivision_h2h,
        "rosters": rosters,
    }


@router.get("/hall-of-fame")
def get_hall_of_fame(db: sqlite3.Connection = Depends(get_db)):
    """League champions, most recent year first. Includes pre-2013 legacy
    champions (2011-2012) known only by legend/oral history — no verified
    stats exist for those, flagged via verified=False."""
    rows = db.execute("""
        SELECT
            s.year, t.owner_name, t.team_name,
            s.wins, s.losses, s.ties,
            ROUND(s.points_for, 2) AS points_for,
            COALESCE(s.playoff_wins, 0) AS playoff_wins,
            COALESCE(s.playoff_losses, 0) AS playoff_losses,
            1 AS verified,
            NULL AS note
        FROM standings s
        JOIN teams t ON s.year = t.year AND s.team_id = t.team_id
        WHERE s.final_standing = 1

        UNION ALL

        SELECT
            year, owner_name, NULL AS team_name,
            NULL AS wins, NULL AS losses, NULL AS ties,
            NULL AS points_for,
            NULL AS playoff_wins, NULL AS playoff_losses,
            0 AS verified,
            note
        FROM legacy_champions

        ORDER BY year DESC
    """).fetchall()
    return [dict(r) for r in rows]


@router.get("/wall-of-shame")
def get_wall_of_shame(db: sqlite3.Connection = Depends(get_db)):
    """League last-place finishers, most recent year first."""
    rows = db.execute("""
        WITH last_place_teams AS (
            SELECT year, team_id FROM (
                SELECT year, team_id,
                       ROW_NUMBER() OVER (PARTITION BY year ORDER BY wins ASC, points_for ASC) AS rk
                FROM standings
            ) WHERE rk = 1
        )
        SELECT
            s.year, t.owner_name, t.team_name,
            s.wins, s.losses, s.ties,
            ROUND(s.points_for, 2) AS points_for
        FROM standings s
        JOIN teams t ON s.year = t.year AND s.team_id = t.team_id
        JOIN last_place_teams lpt ON s.year = lpt.year AND s.team_id = lpt.team_id
        ORDER BY s.year DESC
    """).fetchall()
    return [dict(r) for r in rows]


@router.get("/owner/{owner_name}")
def get_owner_profile(owner_name: str, db: sqlite3.Connection = Depends(get_db)):
    """Full profile for a single manager — career stats + year-by-year."""
    career = db.execute("""
        SELECT
            t.owner_name,
            COUNT(*) as seasons,
            SUM(s.wins) as reg_wins,
            SUM(s.losses) as reg_losses,
            SUM(s.ties) as reg_ties,
            SUM(COALESCE(s.playoff_wins,0)) as playoff_wins,
            SUM(COALESCE(s.playoff_losses,0)) as playoff_losses,
            ROUND(SUM(s.points_for), 2) as total_points,
            SUM(CASE WHEN s.final_standing = 1 THEN 1 ELSE 0 END)
                + COALESCE((SELECT COUNT(*) FROM legacy_champions lc WHERE lc.owner_name = t.owner_name), 0) as championships,
            COALESCE((SELECT COUNT(*) FROM legacy_champions lc WHERE lc.owner_name = t.owner_name), 0) as legacy_championships,
            SUM(CASE WHEN s.final_standing <= 2 THEN 1 ELSE 0 END) as podium_finishes
        FROM standings s
        JOIN teams t ON s.year = t.year AND s.team_id = t.team_id
        WHERE t.owner_name = ?
    """, (owner_name,)).fetchone()

    seasons = db.execute("""
        WITH non_playoff_ranks AS (
            SELECT year, team_id,
                   4 + ROW_NUMBER() OVER (PARTITION BY year ORDER BY wins DESC, points_for DESC) AS rank
            FROM standings
            WHERE playoff_wins IS NULL
        )
        SELECT s.year, t.team_name, s.wins, s.losses, s.ties,
               s.playoff_wins, s.playoff_losses, s.points_for,
               CASE WHEN s.playoff_wins IS NOT NULL THEN s.final_standing ELSE npr.rank END as final_standing
        FROM standings s
        JOIN teams t ON s.year = t.year AND s.team_id = t.team_id
        LEFT JOIN non_playoff_ranks npr ON s.year = npr.year AND s.team_id = npr.team_id
        WHERE t.owner_name = ?
        ORDER BY s.year DESC
    """, (owner_name,)).fetchall()

    return {
        "career": dict(career),
        "seasons": [dict(r) for r in seasons]
    }


def _pearson(xs, ys):
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sx = sum((x - mx) ** 2 for x in xs) ** 0.5
    sy = sum((y - my) ** 2 for y in ys) ** 0.5
    return cov / (sx * sy) if sx and sy else 0.0


@router.get("/draft-intel")
def get_draft_intel(db: sqlite3.Connection = Depends(get_db)):
    """Does draft position predict season outcome? 2013-2025.

    Real draft order now exists for every season (draft_picks) since the
    2013-2018 backfill — previously 2014-2018 was reconstructed from the
    PRIOR season's corrected standing (an approximation, not exact) and 2013
    was excluded entirely for lack of 2012 standings to reconstruct from.
    """
    from routers.draft_match import get_corrected_standing

    rows = []
    for year in range(2013, 2026):
        team_ids = [r["team_id"] for r in db.execute(
            "SELECT team_id FROM standings WHERE year=?", (year,)
        ).fetchall()]

        picks = {r["team_id"]: r["round_pick"] for r in db.execute(
            "SELECT team_id, round_pick FROM draft_picks WHERE year=? AND round_num=1", (year,)
        ).fetchall()}
        source = "real"

        for tid in team_ids:
            draft_pos = picks.get(tid)
            if draft_pos is None:
                continue
            outcome = get_corrected_standing(db, year, tid)
            pf_row = db.execute(
                "SELECT points_for FROM standings WHERE year=? AND team_id=?", (year, tid)
            ).fetchone()
            owner_row = db.execute(
                "SELECT owner_name FROM teams WHERE year=? AND team_id=?", (year, tid)
            ).fetchone()
            rows.append({
                "year": year, "team_id": tid,
                "owner_name": owner_row["owner_name"] if owner_row else None,
                "draft_pos": draft_pos, "outcome": outcome,
                "points_for": pf_row["points_for"] if pf_row else None,
                "source": source,
            })

    all_pos = [r["draft_pos"] for r in rows]
    all_outcome = [r["outcome"] for r in rows]

    correlations = {
        "all": {"pearson": round(_pearson(all_pos, all_outcome), 3), "n": len(rows)},
    }

    buckets = []
    for label, lo, hi in [("Early (1-3)", 1, 3), ("Mid (4-7)", 4, 7), ("Late (8-10)", 8, 10)]:
        subset = [r for r in rows if lo <= r["draft_pos"] <= hi]
        buckets.append({
            "label": label,
            "avg_finish": round(sum(r["outcome"] for r in subset) / len(subset), 2),
            "avg_points": round(sum(r["points_for"] for r in subset) / len(subset), 1),
            "n": len(subset),
        })

    by_pick = []
    for pick in range(1, 11):
        subset = [r for r in rows if r["draft_pos"] == pick]
        by_pick.append({
            "pick": pick,
            "avg_finish": round(sum(r["outcome"] for r in subset) / len(subset), 2) if subset else None,
            "championships": sum(1 for r in subset if r["outcome"] == 1),
            "last_places": sum(1 for r in subset if r["outcome"] == 10),
            "n": len(subset),
        })

    champs = sorted([r for r in rows if r["outcome"] == 1], key=lambda r: r["year"])
    champ_positions = [r["draft_pos"] for r in champs]
    champ_tiers = []
    for label, lo, hi in [("Early (1-3)", 1, 3), ("Mid (4-7)", 4, 7), ("Late (8-10)", 8, 10)]:
        count = sum(1 for p in champ_positions if lo <= p <= hi)
        champ_tiers.append({
            "label": label,
            "count": count,
            "expected_pct": round((hi - lo + 1) / 10 * 100),
        })

    by_team = {}
    for r in rows:
        by_team.setdefault(r["team_id"], []).append(r)
    franchises = []
    for tid, recs in by_team.items():
        avg_pos = sum(r["draft_pos"] for r in recs) / len(recs)
        avg_finish = sum(r["outcome"] for r in recs) / len(recs)
        current = db.execute(
            "SELECT owner_name FROM teams WHERE team_id=? ORDER BY year DESC LIMIT 1", (tid,)
        ).fetchone()
        franchises.append({
            "team_id": tid,
            "owner_name": current["owner_name"] if current else None,
            "avg_draft_pos": round(avg_pos, 2),
            "avg_finish": round(avg_finish, 2),
            "delta": round(avg_finish - avg_pos, 2),
        })
    franchises.sort(key=lambda f: f["delta"])

    return {
        "n": len(rows),
        "correlations": correlations,
        "buckets": buckets,
        "by_pick": by_pick,
        "championships": {
            "avg_draft_pos": round(sum(champ_positions) / len(champ_positions), 2),
            "expected_avg": 5.5,
            "list": champs,
            "tiers": champ_tiers,
        },
        "franchises": franchises,
    }


@router.get("/transactions")
def get_transactions(
    year: Optional[int] = None,
    owner: Optional[str] = None,
    move_type: str = Query(default="all", enum=["all", "waiver", "freeagent", "trade"]),
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    db: sqlite3.Connection = Depends(get_db),
):
    """League-wide feed of real completed roster moves: waiver claims,
    free-agent adds, and trades. 2019+ only — ESPN's raw API has no
    transaction data before then. Trades are grouped into one entry per
    real trade event (see _reconstruct_trades) — full "who got who" detail
    is only recoverable for a minority of historical trades, a genuine
    ESPN data gap; incomplete trades are still included with `complete: false`
    rather than silently dropped."""
    results = []

    if move_type in ("all", "waiver", "freeagent"):
        query = """
            SELECT tr.id, tr.year, tr.week, tr.type, tr.bid_amount, tr.date,
                   t.team_id, t.owner_name, t.team_name
            FROM transactions tr
            JOIN teams t ON tr.year = t.year AND tr.team_id = t.team_id
            WHERE tr.type IN ('WAIVER', 'FREEAGENT')
        """
        params = {}
        if year:
            query += " AND tr.year = :year"
            params["year"] = year
        if owner:
            query += " AND t.owner_name = :owner"
            params["owner"] = owner
        if move_type == "waiver":
            query += " AND tr.type = 'WAIVER'"
        elif move_type == "freeagent":
            query += " AND tr.type = 'FREEAGENT'"
        rows = db.execute(query, params).fetchall()
        for r in rows:
            items = db.execute(
                "SELECT item_type, player_name FROM transaction_items WHERE transaction_id = ? ORDER BY item_seq",
                (r["id"],)
            ).fetchall()
            results.append({
                "kind": "move",
                "year": r["year"], "week": r["week"], "type": r["type"],
                "team_id": r["team_id"], "owner_name": r["owner_name"], "team_name": r["team_name"],
                "bid_amount": r["bid_amount"], "date": r["date"],
                "added": [i["player_name"] for i in items if i["item_type"] == "ADD"],
                "dropped": [i["player_name"] for i in items if i["item_type"] == "DROP"],
            })

    if move_type in ("all", "trade"):
        trades = _reconstruct_trades(db, year=year)
        if owner:
            trades = [t for t in trades if any(s["owner_name"] == owner for s in t["sides"])]
        for t in trades:
            results.append({"kind": "trade", **t})

    results.sort(key=lambda r: r["date"] or 0, reverse=True)
    return {"total": len(results), "results": results[offset:offset + limit]}


@router.get("/owner/{owner_name}/transactions")
def get_owner_transactions(owner_name: str, db: sqlite3.Connection = Depends(get_db)):
    """A manager's full transaction history (2019+ only) — waiver claims,
    free-agent adds, and trades — plus light analytics."""
    rows = db.execute("""
        SELECT tr.id, tr.year, tr.week, tr.type, tr.bid_amount, tr.date, t.team_name
        FROM transactions tr
        JOIN teams t ON tr.year = t.year AND tr.team_id = t.team_id
        WHERE t.owner_name = ? AND tr.type IN ('WAIVER', 'FREEAGENT')
        ORDER BY tr.year DESC, tr.date DESC
    """, (owner_name,)).fetchall()

    moves = []
    for r in rows:
        items = db.execute(
            "SELECT item_type, player_name FROM transaction_items WHERE transaction_id = ? ORDER BY item_seq",
            (r["id"],)
        ).fetchall()
        moves.append({
            "kind": "move",
            "year": r["year"], "week": r["week"], "type": r["type"], "team_name": r["team_name"],
            "bid_amount": r["bid_amount"], "date": r["date"],
            "added": [i["player_name"] for i in items if i["item_type"] == "ADD"],
            "dropped": [i["player_name"] for i in items if i["item_type"] == "DROP"],
        })

    owner_trades = [
        {"kind": "trade", **t} for t in _reconstruct_trades(db)
        if any(s["owner_name"] == owner_name for s in t["sides"])
    ]

    by_year = {}
    for entry in moves + owner_trades:
        by_year.setdefault(entry["year"], []).append(entry)
    moves_by_year = [
        {"year": yr, "moves": sorted(by_year[yr], key=lambda e: e["date"] or 0, reverse=True)}
        for yr in sorted(by_year.keys(), reverse=True)
    ]

    waiver_adds = sum(1 for m in moves if m["type"] == "WAIVER")
    freeagent_adds = sum(1 for m in moves if m["type"] == "FREEAGENT")
    total_faab = sum(m["bid_amount"] or 0 for m in moves if m["type"] == "WAIVER")
    busiest_year = max(by_year.items(), key=lambda kv: len(kv[1]), default=(None, []))

    return {
        "owner_name": owner_name,
        "moves_by_year": moves_by_year,
        "analytics": {
            "total_moves": len(moves) + len(owner_trades),
            "waiver_adds": waiver_adds,
            "freeagent_adds": freeagent_adds,
            "trades_made": len(owner_trades),
            "total_faab_spent": round(total_faab, 2),
            "busiest_year": {"year": busiest_year[0], "count": len(busiest_year[1])} if busiest_year[0] else None,
        },
    }
