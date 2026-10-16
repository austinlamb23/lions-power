"""Backfill real weekly fantasy points for every drafted QB/RB/WR/TE, REGARDLESS
of whether that player was actually started that week -- independent of any
team's roster/lineup decisions. This is the missing piece weekly_rosters can't
provide (it only ever contains actual starters), needed for the "drafted best
ball" forum post method (Method 5: what's the best possible lineup you could
have started each week, using only players you drafted).

Data source: ESPN's PUBLIC per-athlete gamelog (site.web.api.espn.com), which
returns real per-game raw stats for any NFL player in any season, completely
independent of fantasy rostering. Turned into fantasy points using this
league's own scoring rules (yardage rates/TD values pulled directly from the
ESPN fantasy mSettings API and validated -- see below -- rather than guessed;
only the reception bonus varies by era, keyed off seasons.scoring_format).

K/DST are deliberately NOT covered here: confirmed by direct testing that
ESPN's public gamelog returns empty categories for kickers, and defenses
aren't individual "athletes" at all, so there is no equivalent public
per-game data source for those two positions. Method 5's build uses each
team's ACTUAL started K/DST for those two slots instead.

Week alignment: only computed for REGULAR SEASON weeks (1..seasons.
reg_season_weeks), where real NFL week maps 1:1 to fantasy week -- verified
to match weekly_rosters' known-correct points almost exactly across many
players/years. Playoff weeks (fantasy week > reg_season_weeks) were
investigated and found to NOT follow one consistent rule: some teams'
playoff weeks span two real NFL weeks summed together, others don't, and
it does NOT correlate cleanly with matchup bracket type (WINNERS_BRACKET
vs LOSERS_CONSOLATION_LADDER) -- confirmed empirically with two different
consolation-bracket teams needing opposite treatment in the same year, so
there's no reliable rule to apply here. Rather than guess, playoff weeks
are simply left out of this table; Method 5's build uses each team's real
actual weekly_rosters total for those 1-2 weeks instead of a reconstructed
best-ball total.

Validated formula (matches real, trusted weekly_rosters.points exactly for
the large majority of started-player-weeks tested): passingYards*0.04 +
passingTouchdowns*4 + interceptions*-2 + rushingYards*0.1 +
rushingTouchdowns*6 + receivingYards*0.1 + receivingTouchdowns*6 +
receptions*(0, 0.5, or 1 depending on era) + fumblesLost*-2. Known
limitation: 2-point conversions aren't present in the gamelog's stat
categories at all, so any player who scored one will be undercounted by 2
points for that week -- rare, small, and left undocumented-but-flagged
rather than chased further (no reliable source found for it).

Usage:
  venv/bin/python3 ingest_weekly_player_points.py 2013 2025       (historical backfill)
  venv/bin/python3 ingest_weekly_player_points.py --live 2026     (current season, ongoing)
"""
from __future__ import annotations

import sqlite3
import sys
import time
from pathlib import Path

import requests

import roster_pool

DB_PATH = Path(__file__).parent.parent / "almanac.db"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
}
GAMELOG_URL = "https://site.web.api.espn.com/apis/common/v3/sports/football/nfl/athletes/{player_id}/gamelog"

SKILL_POSITIONS = {"QB", "RB", "WR", "TE"}
RECEPTION_POINTS = {"standard": 0.0, "half_ppr": 0.5, "ppr": 1.0}




def fetch_gamelog(player_id: int, year: int) -> dict | None:
    try:
        r = requests.get(GAMELOG_URL.format(player_id=player_id), headers=HEADERS,
                          params={"season": year}, timeout=20)
        if r.status_code != 200:
            return None
        return r.json()
    except requests.RequestException:
        return None


def stats_by_real_week(gamelog: dict) -> dict[int, dict[str, float]]:
    """real NFL week -> {stat name: value}, merged across whatever categories
    ESPN includes for this player (passing/rushing/receiving/fumbles -- varies
    per player, e.g. a QB who never fumbled has no "fumbles" category at all)."""
    names = gamelog.get("names", [])
    events_meta = gamelog.get("events", {})
    reg_season = next((st for st in gamelog.get("seasonTypes", []) if "Regular" in st.get("displayName", "")), None)
    if not reg_season:
        return {}

    out: dict[int, dict[str, float]] = {}
    for cat in reg_season.get("categories", []):
        for e in cat.get("events", []):
            eid = e["eventId"]
            week = events_meta.get(eid, {}).get("week")
            if week is None:
                continue
            named = dict(zip(names, e["stats"]))
            bucket = out.setdefault(week, {})
            for k, v in named.items():
                try:
                    bucket[k] = bucket.get(k, 0.0) + float(v)
                except (TypeError, ValueError):
                    continue
    return out


def fantasy_points(stat_bucket: dict[str, float], reception_points: float, truncated: bool) -> float:
    """Two eras of yardage scoring found in this league's history, confirmed
    empirically (not guessed): modern seasons pay a continuous per-yard rate
    (e.g. 338 passing yards -> 338*0.04); older seasons truncate to whole
    bonus units first (e.g. 338 passing yards -> floor(338/25)*1 = 13, not
    13.52) -- verified exactly against weekly_rosters' known-correct points
    for multiple players in both eras. Rather than hardcode a year cutoff,
    ingest_year() tests both against real ground truth per year and keeps
    whichever one actually matches (see calibrate_truncation)."""
    def g(name: str) -> float:
        return stat_bucket.get(name, 0.0) or 0.0

    if truncated:
        passing_pts = float(int(g("passingYards") // 25))
        rushing_pts = float(int(g("rushingYards") // 10))
        receiving_pts = float(int(g("receivingYards") // 10))
    else:
        passing_pts = g("passingYards") * 0.04
        rushing_pts = g("rushingYards") * 0.1
        receiving_pts = g("receivingYards") * 0.1

    return (
        passing_pts
        + g("passingTouchdowns") * 4
        + g("interceptions") * -2
        + rushing_pts
        + g("rushingTouchdowns") * 6
        + receiving_pts
        + g("receivingTouchdowns") * 6
        + g("receptions") * reception_points
        + g("fumblesLost") * -2
    )


def ensure_table(con: sqlite3.Connection) -> None:
    con.execute("""
        CREATE TABLE IF NOT EXISTS weekly_player_points (
            year INTEGER, week INTEGER, player_id INTEGER,
            position TEXT, points REAL,
            PRIMARY KEY (year, week, player_id)
        )
    """)
    con.commit()


def ingest_year(con: sqlite3.Connection, year: int, default_truncated: bool):
    season_row = con.execute("SELECT reg_season_weeks, scoring_format FROM seasons WHERE year=?", (year,)).fetchone()
    if not season_row:
        print(f"--- {year}: no season row, skipping ---")
        return default_truncated
    reg_season_weeks, scoring_format = season_row
    reception_points = RECEPTION_POINTS.get(scoring_format, 1.0)

    players = con.execute(
        "SELECT DISTINCT player_id, player_name, position FROM draft_picks "
        "WHERE year=? AND position IN ('QB','RB','WR','TE') AND player_id IS NOT NULL",
        (year,),
    ).fetchall()

    print(f"--- {year} ({len(players)} skill-position players, regular season weeks 1-{reg_season_weeks}) ---")

    # Fetch every player's gamelog once, keep in memory -- needed twice below
    # (once per candidate formula during calibration, once to write final rows).
    gamelogs: dict[int, dict[int, dict[str, float]]] = {}
    misses = 0
    for player_id, player_name, position in players:
        gamelog = fetch_gamelog(player_id, year)
        time.sleep(0.05)
        if not gamelog:
            misses += 1
            continue
        gamelogs[player_id] = stats_by_real_week(gamelog)

    # Calibrate: this era's yardage scoring is either continuous or truncated
    # (see fantasy_points' docstring) -- pick whichever matches real,
    # known-correct weekly_rosters points better for THIS year specifically,
    # rather than assume a fixed year cutoff.
    ground_truth = con.execute(
        "SELECT week, player_id, points FROM weekly_rosters WHERE year=? AND week<=?",
        (year, reg_season_weeks),
    ).fetchall()
    if ground_truth:
        errors = {True: 0.0, False: 0.0}
        compared = 0
        for week, player_id, actual in ground_truth:
            bucket = gamelogs.get(player_id, {}).get(week)
            if not bucket:
                continue
            compared += 1
            for truncated in (True, False):
                computed = fantasy_points(bucket, reception_points, truncated)
                errors[truncated] += abs(computed - actual)
        use_truncated = errors[True] < errors[False] if compared else default_truncated
        print(f"  calibration: {compared} started-weeks compared, "
              f"truncated total error={errors[True]:.1f}, continuous total error={errors[False]:.1f} "
              f"-> using {'truncated' if use_truncated else 'continuous'}")
    else:
        use_truncated = default_truncated
        print(f"  no ground truth available this year, defaulting to {'truncated' if use_truncated else 'continuous'}")

    con.execute("DELETE FROM weekly_player_points WHERE year=?", (year,))
    rows_written = 0
    for player_id, player_name, position in players:
        by_real_week = gamelogs.get(player_id)
        if not by_real_week:
            continue
        for week in range(1, reg_season_weeks + 1):
            bucket = by_real_week.get(week)
            if not bucket:
                continue
            points = round(fantasy_points(bucket, reception_points, use_truncated), 2)
            con.execute(
                "INSERT OR REPLACE INTO weekly_player_points (year, week, player_id, position, points) "
                "VALUES (?,?,?,?,?)",
                (year, week, player_id, position, points),
            )
            rows_written += 1

    con.commit()
    print(f"  {rows_written} player-weeks written, {misses} players with no gamelog found")
    return use_truncated


def live_player_universe(con: sqlite3.Connection, year: int) -> list[tuple[int, str]]:
    """(player_id, position) for QB/RB/WR/TE, unioned from draft_picks (empty
    for a season with no draft data ingested yet -- confirmed the case for
    2026), the live league-wide roster pool (roster_pool.get_rosters, so
    anyone currently rostered gets tracked even with no draft_picks at all),
    and whatever's already in weekly_player_points for this year. The union
    only ever grows during a live season -- unlike ingest_year()'s blanket
    per-year DELETE (safe for a closed, complete historical season), a
    player dropped mid-season here must stay tracked, or their already-
    graded earlier weeks would silently vanish the next time this runs."""
    from_draft = con.execute(
        "SELECT DISTINCT player_id, position FROM draft_picks "
        "WHERE year=? AND position IN ('QB','RB','WR','TE') AND player_id IS NOT NULL",
        (year,),
    ).fetchall()
    try:
        rosters = roster_pool.get_rosters(year)
    except requests.RequestException:
        rosters = {}
    from_roster = [
        (p["player_id"], p["position"])
        for team in rosters.values()
        for p in team["starters"] + team["bench"]
        if p["position"] in SKILL_POSITIONS and p.get("player_id")
    ]
    from_tracked = con.execute(
        "SELECT DISTINCT player_id, position FROM weekly_player_points WHERE year=?", (year,)
    ).fetchall()
    return list({(pid, pos) for pid, pos in [*from_draft, *from_roster, *from_tracked]})


def ingest_year_live(con: sqlite3.Connection, year: int, default_truncated: bool) -> bool:
    """Same gamelog-fetch + fantasy_points() logic as ingest_year(), but for
    a season still in progress: player universe comes from
    live_player_universe (not a draft_picks-only query, which would find
    nothing for a season with no draft ingested yet), calibrates against
    weekly_rosters if any exists (usually none for a brand-new live season,
    falls back to default_truncated -- pass False, since every season since
    2019 has used the continuous formula, confirmed across 2019-2025), and
    writes with INSERT OR REPLACE per (year, week, player_id) WITHOUT the
    upfront per-year DELETE ingest_year() does, since the tracked universe
    is open-ended here rather than a closed historical list."""
    season_row = con.execute("SELECT reg_season_weeks, scoring_format FROM seasons WHERE year=?", (year,)).fetchone()
    if not season_row:
        print(f"--- {year}: no season row, skipping ---")
        return default_truncated
    reg_season_weeks, scoring_format = season_row
    reception_points = RECEPTION_POINTS.get(scoring_format, 1.0)

    players = live_player_universe(con, year)
    print(f"--- {year} LIVE ({len(players)} skill-position players, regular season weeks 1-{reg_season_weeks}) ---")

    gamelogs: dict[int, dict[int, dict[str, float]]] = {}
    misses = 0
    for player_id, position in players:
        gamelog = fetch_gamelog(player_id, year)
        time.sleep(0.05)
        if not gamelog:
            misses += 1
            continue
        gamelogs[player_id] = stats_by_real_week(gamelog)

    ground_truth = con.execute(
        "SELECT week, player_id, points FROM weekly_rosters WHERE year=? AND week<=?",
        (year, reg_season_weeks),
    ).fetchall()
    if ground_truth:
        errors = {True: 0.0, False: 0.0}
        compared = 0
        for week, player_id, actual in ground_truth:
            bucket = gamelogs.get(player_id, {}).get(week)
            if not bucket:
                continue
            compared += 1
            for truncated in (True, False):
                computed = fantasy_points(bucket, reception_points, truncated)
                errors[truncated] += abs(computed - actual)
        use_truncated = errors[True] < errors[False] if compared else default_truncated
        print(f"  calibration: {compared} started-weeks compared, "
              f"truncated total error={errors[True]:.1f}, continuous total error={errors[False]:.1f} "
              f"-> using {'truncated' if use_truncated else 'continuous'}")
    else:
        use_truncated = default_truncated
        print(f"  no ground truth available this year, defaulting to {'truncated' if use_truncated else 'continuous'}")

    rows_written = 0
    for player_id, position in players:
        by_real_week = gamelogs.get(player_id)
        if not by_real_week:
            continue
        for week in range(1, reg_season_weeks + 1):
            bucket = by_real_week.get(week)
            if not bucket:
                continue
            points = round(fantasy_points(bucket, reception_points, use_truncated), 2)
            con.execute(
                "INSERT OR REPLACE INTO weekly_player_points (year, week, player_id, position, points) "
                "VALUES (?,?,?,?,?)",
                (year, week, player_id, position, points),
            )
            rows_written += 1

    con.commit()
    print(f"  {rows_written} player-weeks written, {misses} players with no gamelog found")
    return use_truncated


def validate_against_weekly_rosters(con: sqlite3.Connection, year: int):
    """Cross-check computed points against weekly_rosters.points for every
    player-week where both exist (i.e. every week that player was actually
    started) -- weekly_rosters is independently derived and already trusted,
    so agreement here is the real signal that the formula/week-alignment is
    correct, not just a hope."""
    rows = con.execute("""
        SELECT wpp.week, wpp.points AS computed, wr.points AS actual
        FROM weekly_player_points wpp
        JOIN weekly_rosters wr ON wr.year=wpp.year AND wr.player_id=wpp.player_id AND wr.week=wpp.week
        WHERE wpp.year=?
    """, (year,)).fetchall()
    if not rows:
        print(f"  {year}: no overlapping started-weeks to validate against (weekly_rosters has none this year)")
        return
    diffs = [abs(r[0] and (r[1] - r[2]) or (r[1] - r[2])) for r in rows]
    exact = sum(1 for d in diffs if d < 0.05)
    close = sum(1 for d in diffs if d < 1.0)
    print(f"  {year} validation: {len(rows)} started-weeks compared, "
          f"{exact} exact ({100*exact/len(rows):.0f}%), {close} within $1 ({100*close/len(rows):.0f}%), "
          f"max diff {max(diffs):.2f}")


def main():
    con = sqlite3.connect(DB_PATH)
    ensure_table(con)

    if sys.argv[1] == "--live":
        year = int(sys.argv[2])
        ingest_year_live(con, year, default_truncated=False)
        validate_against_weekly_rosters(con, year)
    else:
        start, end = int(sys.argv[1]), int(sys.argv[2])
        truncated = False  # default for the very first year processed if it has no ground truth
        for year in range(start, end + 1):
            truncated = ingest_year(con, year, truncated)
            validate_against_weekly_rosters(con, year)

    con.close()


if __name__ == "__main__":
    main()
