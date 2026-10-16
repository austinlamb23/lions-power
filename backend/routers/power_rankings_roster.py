"""Live current-roster lookup for Power Rankings' journey view.

Separate from power_rankings.py (which owns the posted rank/blurb/image data)
because this hits ESPN live on every cache miss rather than reading from
almanac.db. The actual roster-pulling/caching logic lives in
backend/roster_pool.py (shared with Game Room's All-Star Roster player
pool) — this file is just the thin HTTP-facing wrapper around it.

IMPORTANT: this router shares the /api/power-rankings prefix with
power_rankings.py, and main.py must register this router's include_router()
call BEFORE power_rankings.router's — power_rankings.py's /{year}/{week}
route has no :int path converter, so Starlette treats it as a generic
two-segment match and would swallow /roster/{team_id} first (team_id="roster"
-> fails int coercion -> 422) if that router were registered first. See the
route-ordering comment already at the top of power_rankings.py.
"""
from __future__ import annotations

import requests
from fastapi import APIRouter, HTTPException

import roster_pool

router = APIRouter(prefix="/api/power-rankings", tags=["power-rankings-roster"])


@router.get("/roster/{team_id}")
def get_roster(team_id: int, year: int):
    try:
        rosters = roster_pool.get_rosters(year)
    except requests.RequestException as e:
        raise HTTPException(502, f"Couldn't reach ESPN: {e}")
    if team_id not in rosters:
        raise HTTPException(404, f"No roster found for team {team_id} in {year}")
    return rosters[team_id]
