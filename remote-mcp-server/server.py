"""
Remote MCP server for the Lions Power 3 fantasy football almanac.

Exposes the read-only query_almanac tool shared with backend/bot_engine.py
(GroupMe bot) and mcp-server/index.js (local Node MCP server) — all three
read almanac_schema.md as the shared source of truth for schema + business
rules, so a schema change only needs updating in one place. Also exposes
best_ball_lineup, a thin proxy to the main backend's own /api/best-ball
endpoint (see backend/routers/best_ball.py) rather than a second SQL-based
tool -- "optimal lineup under real slot-eligibility constraints" is a genuine
small optimization problem, not something to trust an LLM-composed SQL query
to get right on demand, and the live ESPN roster data (bench included) it
needs isn't in the SQLite file at all -- only the main backend process
(already holding the ESPN session/credentials for roster_pool.py) can reach
it, so this server calls that endpoint over localhost rather than
duplicating that logic.

No authentication — deliberate for now, not an oversight. Both tools are
read-only (can't write/modify anything) and the data isn't sensitive
(fantasy football stats among friends). Revisit if this ever needs to be
locked down further.
"""

import json
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

ROOT = Path(__file__).parent.parent
DB_PATH = ROOT / "almanac.db"
SCHEMA_PATH = ROOT / "almanac_schema.md"
SCHEMA_AND_RULES = SCHEMA_PATH.read_text()

TOOL_DESCRIPTION = f"""Run a read-only SQL query against the Lions Power 3 fantasy football league almanac database. A single SELECT (or WITH ... SELECT) statement only — no writes.

{SCHEMA_AND_RULES}"""

# The main backend already holds the ESPN session and does its own live
# fetch of roster_pool data for this -- reached over localhost, not
# duplicated here (see module docstring).
BACKEND_BASE = "http://127.0.0.1:8000"

BEST_BALL_DESCRIPTION = """For the CURRENT NFL season only (this is live ESPN roster data, not a historical almanac query -- do not use this for any past/completed season, use query_almanac instead), compares what each real fantasy team actually started in a given week against the highest-scoring lineup their full roster (starters + bench) could have produced under the league's real slot rules (QB, RB, RB, WR, WR, TE, FLEX[RB/WR/TE], D/ST, K).

Returns, per team: actual_score, optimal_score, points_left_on_bench (optimal minus actual -- how much they cost themselves with suboptimal starts), and both the actual_lineup and optimal_lineup with each slot's player and points. Sorted by optimal_score descending.

Pass team_id to scope to one team; omit it to get every team for that week, which is the natural way to answer "who set the best/worst possible lineup this week" or "who left the most points on their bench."

Caveat worth surfacing if asked about an EARLIER week this season: the roster data reflects CURRENT ESPN roster membership with that week's scoring attached, not a true historical snapshot -- if a team has made waiver moves since that week, a bench player shown here may not actually have been on their roster back then. This is exact and reliable for the week currently being played; treat it as approximate for earlier weeks and say so."""

# Caddy reverse-proxies the public domain to this local server, so the
# incoming Host/Origin headers are the public domain, not 127.0.0.1 — has
# to be explicitly allowlisted or FastMCP's DNS-rebinding protection
# rejects every request with "Invalid Host header".
mcp = FastMCP(
    "almanac",
    host="127.0.0.1",
    port=8010,
    stateless_http=True,
    transport_security=TransportSecuritySettings(
        allowed_hosts=["lionspower3.duckdns.org", "127.0.0.1:8010", "localhost:8010"],
        allowed_origins=["https://lionspower3.duckdns.org"],
    ),
)


@mcp.tool(name="query_almanac", description=TOOL_DESCRIPTION)
def query_almanac(sql: str) -> str:
    # Raising (not returning an error string) is what makes FastMCP set
    # isError=true on the tool result — a plain returned string is treated
    # as a successful result, even if its text describes a failure.
    stripped = sql.strip().lstrip("(").strip()
    if not stripped[:6].upper().startswith("SELECT") and not stripped[:4].upper().startswith("WITH"):
        raise ValueError("Error: only SELECT / WITH queries are allowed.")

    try:
        # Fresh connection per call, not a persistent handle — almanac.db
        # gets rebuilt/replaced periodically by build_almanac.py, and this
        # server can stay running for a long time. A fresh connection
        # always sees the current file.
        con = sqlite3.connect(f"file:{DB_PATH.resolve()}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        rows = con.execute(sql).fetchmany(200)
        result = [dict(r) for r in rows]
        con.close()
    except sqlite3.Error as e:
        raise ValueError(f"SQL error: {e}") from e

    return json.dumps(result, default=str)


@mcp.tool(name="best_ball_lineup", description=BEST_BALL_DESCRIPTION)
def best_ball_lineup(year: int, week: int, team_id: int | None = None) -> str:
    params = {}
    if team_id is not None:
        params["team_id"] = team_id
    url = f"{BACKEND_BASE}/api/best-ball/{year}/{week}"
    if params:
        url += "?" + urllib.parse.urlencode(params)

    try:
        with urllib.request.urlopen(url, timeout=20) as resp:
            return resp.read().decode()
    except urllib.error.HTTPError as e:
        raise ValueError(f"Error from best-ball endpoint: {e.code} {e.read().decode(errors='replace')}") from e
    except urllib.error.URLError as e:
        raise ValueError(f"Couldn't reach the backend for best-ball data: {e}") from e


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
