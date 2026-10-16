# espn-api-master (dev clone)

This directory (`~/espn-api-master-dev`) is a **working copy**, not the live site. The
real production deployment — the one Caddy and systemd actually serve at
`https://lionspower3.duckdns.org` — lives in a separate directory on this same VM:
`~/espn-api-master`. Editing files here has **zero effect on the live site** until you
deliberately deploy, per the steps below.

**Only deploy when explicitly asked** (e.g. "deploy this", "push to production", "ship
it"). Don't push changes to `~/espn-api-master` automatically just because an edit here
is finished — the whole point of the dev/live split is a deliberate review step before
anything goes live.

## Layout of the live directory (`~/espn-api-master`)

- `backend/` — real source files, own venv (Python 3.12), run as systemd service
  `espn-bot.service` (`sudo systemctl restart espn-bot.service` after any backend change).
- `frontend/dist/` — a **build artifact only**. There is no `frontend/src` in the live
  directory at all — never try to rsync source there. Caddy serves this directory
  directly as static files; changes are live immediately on file write, no restart needed.
- `almanac.db` — **the single live source of truth** for all user-generated data (game
  sessions/scores, punishment accounts/votes, league rules, pending changes, shit list
  rankings, etc).

## Deploy steps

**Backend change:**
1. Copy the specific changed file(s) from here to the same relative path under
   `~/espn-api-master/backend/...` — copy files individually with explicit destination
   paths, never a broad multi-file copy that could land something in the wrong directory
   (this has happened twice before — a router file ending up in the wrong folder because
   it was batched with an unrelated file in one command).
2. **`bot_engine.py` must always be copied on its own**, never bundled with router files
   or `main.py` in the same operation — same reasoning, it's bitten this project more
   than once.
3. If the schema changed (new/changed table), also copy `almanac_schema.md` (project
   root, one level above `backend/`) — it's shared with the GroupMe bot and the MCP
   servers, and needs to stay in sync or the bot starts giving wrong/stale answers.
4. `sudo systemctl restart espn-bot.service`, then verify with a curl against
   `https://lionspower3.duckdns.org/api/...` for whatever changed.

**Frontend change:**
1. `cd ~/espn-api-master-dev/frontend && npm run build`
2. Copy the built `dist/` output to `~/espn-api-master/frontend/dist/` (delete-sync, so
   stale old assets don't linger — e.g. `rsync -a --delete dist/ ~/espn-api-master/frontend/dist/`).
3. No service restart needed. Verify by checking the served JS asset hash matches the
   new build.

**Database changes are the highest-risk operation — read this before touching `almanac.db`:**
- **Never overwrite the live `almanac.db` wholesale** (no full-file copy/rsync from the
  dev clone or anywhere else) — it holds live user data that only exists there. A
  wholesale overwrite has caused real data loss before (wiped game sessions that existed
  live but not in a locally-modified copy).
- Always take a timestamped backup first: `cp almanac.db almanac.db.bak-<what>-<timestamp>`.
- Schema changes: a guarded `ALTER TABLE ... ADD COLUMN ...` (check
  `PRAGMA table_info(...)` first to confirm the column doesn't already exist) run
  directly against the live db via SSH — never `CREATE TABLE IF NOT EXISTS` alone if the
  table might already exist without the new column (it won't retrofit columns).
- Data changes: targeted `UPDATE`/`INSERT`/`DELETE` statements run directly against the
  live db, never a bulk file replace.
- Check current row counts / relevant state on the **live** db before assuming
  something is empty or safe to change — the dev clone's data (if any) is not
  authoritative, the live db is.

## General

- This project has no git — there is no `git diff`/`git log` to lean on; deploys are
  manual file copies, so be precise about exactly what changed and what's being pushed.
- After any deploy, verify against the real public domain
  (`https://lionspower3.duckdns.org`), not just that the copy command succeeded.
