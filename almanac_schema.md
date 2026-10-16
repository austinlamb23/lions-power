Schema:

seasons(year PK, league_name, team_count, reg_season_weeks, playoff_teams,
        scoring_format)
teams(year, team_id, team_name, team_abbrev, owner_name, division)  PK(year, team_id)
standings(year, team_id, wins, losses, ties, points_for, points_against,
          final_standing, playoff_wins, playoff_losses)  PK(year, team_id)
matchups(year, week, home_team_id, away_team_id, home_score, away_score,
         is_playoff, matchup_type)  PK(year, week, home_team_id)
draft_picks(year, round_num, round_pick, overall_pick, team_id, player_name,
            player_id, keeper, pro_team, position, season_points,
            position_finish)  PK(year, overall_pick)
legacy_champions(year PK, owner_name, note)
legacy_h2h(owner_a, owner_b, team_id_a, team_id_b, wins_a, wins_b, ties, note)
          PK(owner_a, owner_b)
transactions(id PK, year, week, team_id, type, status, related_transaction_id,
             bid_amount, date)
transaction_items(transaction_id, item_seq, item_type, player_id, player_name,
             from_team_id, to_team_id)  PK(transaction_id, item_seq)
league_rules(id PK, category, title, text, sort_order, created_at, updated_at)
pending_rule_changes(id PK, text, proposed_by, status, note, created_at,
             updated_at)
shitlist(id PK, owner_name, reason, rank, created_at, updated_at)
coach_poll_votes(year, week, voter_owner, team_id, rank_given, created_at)
          PK(year, week, voter_owner, team_id)
power_rankings(year, week, team_id, rank, blurb, image_path, created_at,
          updated_at)  PK(year, week, team_id)
power_rankings_drafts(year, week, team_id, rank, blurb, image_path,
          created_at, updated_at)  PK(year, week, team_id)
weekly_rosters(year, week, team_id, player_id, player_name, position,
          pro_team, points)  PK(year, week, team_id, player_id)
weekly_player_points(year, week, player_id, position, points)
          PK(year, week, player_id)
forum_posts(id PK, title, body_markdown, excerpt, cover_image_path, cta_url,
          cta_label, submitted_by, created_at, updated_at)
weekly_predictions(year, week, home_team_id, voter_owner, picked_team_id,
          created_at, updated_at)  PK(year, week, home_team_id, voter_owner)
all_star_roster_picks(year, week, voter_owner, slot, player_id, player_name,
          position, real_team_id, kickoff_at, created_at, updated_at)
          PK(year, week, voter_owner, slot)
week_lock_overrides(year, week, lock_at, set_by, created_at, updated_at)
          PK(year, week)
punishment_accounts(owner_name PK, salt, password_hash, created_at)
punishment_ideas(id PK, text, submitted_by, created_at, status, lock_rank,
          eliminated_week, eliminated_by, eliminated_at)
punishment_votes(idea_id, owner_name, weight, created_at)
          PK(idea_id, owner_name)
punishment_eliminations(year, week, owner_name, score, status, idea_id,
          asked_at, resolved_at)  PK(year, week)
side_bets(id PK, description, side_a, side_b, stakes, submitted_by,
          resolution_query, resolution_note, status, winner, resolved_by,
          resolution_error, created_at, updated_at, resolved_at)

Business rules:
- The champion for a year is the team with standings.final_standing = 1.
- legacy_champions holds the league's two pre-history seasons (2011, 2012),
  from before verified record-keeping began in 2013 — only the champion's
  name is known, no stats exist. These are legitimate, honored championships
  and MUST be included in career championship counts and "most championships"
  style questions (they add to a manager's total the same as any other title).
  BUT every time you mention one of these two years, you must explicitly flag
  that it's unverified — based only on league legend, folklore, and oral
  history, not statistically confirmed like 2013+. Never present a 2011/2012
  championship as equivalent-with-no-caveat to a verified one.
- legacy_h2h holds unverified pre-2013 head-to-head records between specific
  pairs of managers, from before verified game-by-game data began — only an
  aggregate win/loss/tie count is known, no individual games. Each row is
  stored once with an arbitrary owner_a/owner_b (and team_id_a/team_id_b)
  orientation, so when looking up a pair check both directions:
  WHERE (owner_a=? AND owner_b=?) OR (owner_a=? AND owner_b=?), and flip
  wins_a/wins_b accordingly if the row's owner_a is the OTHER person. These
  are legitimate, honored results and MUST be added into any career or
  head-to-head win/loss total for that pair, the same as verified 2013+
  matchups. BUT you must explicitly flag that portion as unverified — based
  only on league legend and oral history, no game-by-game record exists —
  whenever you mention it. Never fold it in silently with no caveat.
- standings.final_standing reflects TWO different things depending on the
  range: for teams that made the playoffs (ranks 1..seasons.playoff_teams,
  identifiable via standings.playoff_wins IS NOT NULL), it's the real
  playoff bracket result. For teams that missed the playoffs (playoff_wins
  IS NULL), it's their regular-season order: wins DESC, points_for DESC as
  the tiebreak — NOT whatever a consolation/toilet-bowl bracket produced.
  Both portions are correct and reliable as stored — final_standing can be
  used directly for "who finished Nth" and "last place" questions (MAX
  final_standing per year = last place) without recomputing it.
- For the CURRENT in-progress season (added 2026-09-16, via
  ingest_standings_live.py, part of live_ingest.py's regular 3-hour sync):
  standings.wins/losses/ties/points_for/points_against are live and
  reliable, computed straight from decided matchups so far this season --
  but final_standing/playoff_wins/playoff_losses stay NULL the whole season,
  by design, since those genuinely aren't knowable until the season
  (including playoffs) is actually over. Never treat a NULL final_standing
  as "data missing/not synced" for the current year -- it's the correct,
  expected state; use wins/losses/points_for directly for any "current
  standings" question instead, and don't attempt to answer "who's in Nth
  place" or "who's in last" for the live season from final_standing.
- draft_picks and transactions/transaction_items are also live-synced for
  the current season now (ingest_draft.py, one-time right after the draft
  since those facts never change afterward; ingest_transactions_live.py,
  every 3 hours since new waiver/trade activity happens continuously).
  transactions.status is whatever ESPN reports verbatim, including
  non-final outcomes like 'CANCELED' or 'FAILED_PLAYERALREADYDROPPED' --
  don't assume every row represents a real, executed move; check status.
  draft_picks.season_points/position_finish stay NULL for the current
  year's picks until the season is complete, same reasoning as
  final_standing above.
- seasons.scoring_format records the league's PPR rule for that year: 'standard'
  (2013-2017), 'half_ppr' (2018 only), or 'ppr' (2019-2025, current rule). Use
  it to filter/group any stats question scoped to a scoring era, e.g. "the PPR
  era" -> join to seasons and filter scoring_format = 'ppr'; "since the switch
  to PPR" -> year >= 2019. All three eras are equally legitimate parts of
  league history — this column is for filtering when someone explicitly asks
  about an era or scoring rule, not a reason to caveat or downweight
  standard/half-PPR seasons in general stats questions.
- team_id identifies a franchise and persists across years even when the
  manager (owner_name) changes hands. Use owner_name for a manager's personal
  stats/head-to-head; use team_id for franchise-continuity questions.
- IMPORTANT: a team_id's owner_name can differ by year (franchises change
  hands). Never pick an arbitrary year's owner_name for "who owns/manages
  this team" style questions. To get the CURRENT/most recent manager of a
  team_id, always order by year DESC and take the first row, e.g.:
  SELECT owner_name FROM teams WHERE team_id = ? ORDER BY year DESC LIMIT 1
- Manager nicknames: people in the group chat rarely use exact owner_name
  values — resolve any of the following (case-insensitive) to the canonical
  owner_name before querying:
    Vincent Zahm  <- Vince, Vinny, Commissioner, "Mark's son"
    Mark Safranek <- Mark, "Vince's dad", "Vince's father", "Vinny's dad",
                      "Vinny's father", "Vince's daddy", "Vinny's daddy",
                      Jeremy Lin (his old ESPN profile name, same person/team_id)
    Paul T Knickelbein <- Pickle, "the Pickle", Paul Knickelbein,
                      Paul Thomas Knickelbein (his old ESPN profile name, same person/team_id)
    Bubbleface Bob <- Paul Florczak, Paco
    Austin Lamb   <- Tin
    Stephen Marshall <- Steve, steve, Stephen
    Josh Frey     <- Josh, Asian, "the Asian"
    Luke Rabideau <- Luke, Lukey
    John Yocum    <- Johnny, John
    Dan Watza     <- Dan, Danny
  This list isn't exhaustive — if a name/nickname isn't covered above, match
  it to the closest owner_name in the teams table rather than giving up or
  asking for clarification.
- Head-to-head matchup data is reliable from year 2013 onward (real
  game-by-game records exist in matchups for every season 2013-2025).
- matchups.matchup_type has 4 values: 'NONE' (a real regular-season game),
  'WINNERS_BRACKET' (a real championship-bracket playoff game, always has
  is_playoff=1), 'LOSERS_CONSOLATION_LADDER' (a "toilet bowl" game between
  teams that already missed the playoffs), and 'WINNERS_CONSOLATION_LADDER'
  (a 3rd-place-style consolation game between teams that already lost their
  playoff-round-1 game). The league does NOT care about consolation bracket
  games — they don't count for anything. is_playoff=0 is NOT a safe filter
  for "regular season" because both consolation types also have is_playoff=0.
  ANY query involving matchups — head-to-head, records, point totals, "who
  has beaten who", etc. — MUST filter
  matchup_type IN ('NONE', 'WINNERS_BRACKET') to exclude both consolation
  types, unless the user explicitly asks about consolation/toilet-bowl games.
- A team's "opponent win rate" / "easiest opponent" type questions should be
  computed from the matchups table joined to teams, comparing head-to-head
  records against each distinct opponent (owner_name), 2013+, respecting the
  matchup_type filter above.
- teams.division holds each team's real ESPN division ("East" or "West") for
  that season, present for every year 2013+. Division membership is NOT
  static across years — a team/owner can be in a different division in
  different seasons — so always join on (year, team_id) to get the correct
  division for a specific season, never assume a manager's division is
  fixed. For interdivision questions ("East vs West record", "who's in
  which division this year/all-time"), join matchups to teams TWICE (once
  for home_team_id's division, once for away_team_id's division) to
  determine each side of a given game, and apply the same matchup_type
  filter above. Legacy pre-2013 data (legacy_champions, legacy_h2h) has no
  division on record — division-based questions only cover 2013+.
- draft_picks has real per-player enrichment for every pick, 2013+: pro_team
  (the player's actual NFL team that season), position (QB/RB/WR/TE/K/D-ST),
  season_points (that player's real fantasy points scored that season —
  NOT the drafting manager's own team score, which lives in standings/
  matchups instead), and position_finish. position_finish is that player's
  rank among EVERY NFL player at their position that season (e.g.
  position_finish=1 for a RB means the #1 scoring running back in the
  entire NFL that year, not just the best RB drafted in this league) — it
  is ONLY populated for 2019+ (NULL for 2013-2018 picks, since ESPN's
  historical positional-rank data isn't reliably available before then).
  Use this data for questions like "who had the best rookie/sleeper pick",
  "what position does X like to draft", "who drafted the best RB finish",
  best-value-pick questions (high season_points or good position_finish
- weekly_rosters has that team's STARTING LINEUP for a given week (not the
  full roster/bench — ESPN's box score data for this league only ever
  includes players who were actually started that week, confirmed by entry
  count matching the league's starting-lineup size exactly), with points
  being that player's real fantasy points scored that specific week (not
  season points). Covers every week 2013-2017 and 2019-2025; 2018 has NO
  box score data at all for this league (confirmed empty across every week
  that year — a real ESPN data gap, not a bug), so weekly_rosters simply
  has no 2018 rows. Use this for questions like "who was X's best/worst
  starter in week N of year Y", "how many points did team X get from their
  QB slot in week N" (join position='QB'), or "who started someone who
  scored 0" — do NOT use it for season-long totals (join/sum against
  draft_picks.season_points or standings instead, which are already
  season-scoped) or for bench/roster-construction questions (bench players
  aren't in this table at all, so their absence doesn't mean anything).
  relative to how late they were picked), etc.
- weekly_player_points holds every tracked QB/RB/WR/TE's REAL fantasy points
  for a given week, independent of whether that player was actually started
  by anyone that week (unlike weekly_rosters, which only ever has actual
  starters) -- built to answer "what would this player have scored if
  started" questions (best-ball/bench-value analysis) and to grade the
  QB/RB/WR/TE/FLEX portion of Game Room's Weekly All-Star Roster (its D/ST
  and K portion is graded from a separate live source — see
  all_star_roster_picks below). The tracked player set is a union of that
  year's draft_picks, whoever's currently rostered live in the league
  (roster_pool.py), and whatever's already in this table -- for the CURRENT
  season this table is kept live via a systemd timer (lp3-live-ingest.timer,
  ~every 3 hours) re-running ingest_weekly_player_points.py --live, not just
  a one-time historical backfill; don't assume it's static for the season
  in progress. REGULAR SEASON ONLY (week <= seasons.reg_season_weeks) -- playoff weeks
  were investigated and found to not follow one consistent real-NFL-week
  alignment rule across different bracket types, so they're deliberately
  left out rather than guessed; use weekly_rosters/matchups for playoff-week
  questions instead. K and D/ST are NOT covered at all -- no reliable public
  per-game data source exists for those two positions (kickers have no
  gamelog data, defenses aren't individual players) -- never join this table
  expecting K/D/ST rows, their absence isn't a data gap to flag, it's by
  design. Points are computed from real per-game NFL stats using this
  league's own scoring rules, calibrated per year against weekly_rosters'
  known-correct started-player points (roughly 86-94% exact match, ~90%+
  within $1 every year tested) -- small remaining gaps are almost entirely
  from 2-point conversions, which have no available data source and are
  simply not counted (rare, usually only 2 points per occurrence). No 2018
  coverage (this table depends on weekly_rosters existing for calibration
  and the K/D-ST portion of downstream analysis, and weekly_rosters has no
  2018 data at all for this league).
- forum_posts holds standalone long-form write-ups submitted by any logged-in
  owner via the Forums section (body_markdown is real Markdown, rendered
  client-side — no comments/replies exist for this table, posts are
  standalone articles only). Reads are open to everyone; writes require an
  active owner login (blocked for any owner in auth.py's FLAGGED_OWNERS).
  cta_url/cta_label are an optional matched pair (both set or both NULL) used
  for a post that links out to another page on the site or elsewhere — e.g.
  the seeded "Draft Intel" post links to the live /draft-intel dashboard
  rather than reproducing its interactive charts as static text. submitted_by
  is the author's owner_name; an author (or the FORUMS_ADMIN commissioner
  account, "Austin Lamb" by default) can edit or delete their own post, but
  there's no moderation queue — anything submitted is immediately public.
- power_rankings_drafts is the private work-in-progress twin of power_rankings
  — same shape, but never shown publicly and never read by anything except
  the Power Rankings author's own admin screen (author-gated read AND write).
  Unlike power_rankings, a draft can be incomplete (fewer than all teams,
  duplicate/gapped ranks) since it's just saved-in-progress work, not
  something meant to satisfy the "every team, ranks 1-N, no gaps" rule that
  publishing enforces. Publishing (POST to power_rankings itself) does NOT
  read from or clear this table — they're independent; a row can sit here
  indefinitely across sessions until the author publishes.
- transactions/transaction_items hold real waiver claims, free-agent adds,
  and trades. 2019+ ONLY — ESPN's raw API has no transaction data for
  earlier seasons at all; never say "no moves happened" for 2013-2018, say
  the data isn't available for those years. `type` is only ever WAIVER,
  FREEAGENT, or TRADE_ACCEPT (every other raw ESPN transaction state —
  proposals, vetoes, declines, pending/failed attempts — is intentionally
  excluded, only real completed moves are stored). `status` is 'EXECUTED'
  for WAIVER/FREEAGENT rows. TRADE_ACCEPT rows have `status = NULL` — that
  NULL means "this trade happened," the opposite convention from every
  other row in this table, never filter TRADE_ACCEPT rows expecting a
  non-null status. `bid_amount` is the FAAB/waiver bid, relevant mainly for
  WAIVER rows (this league doesn't appear to use FAAB bidding — expect 0).
  Join `transactions.team_id` to teams on (year, team_id) for team_name/
  owner_name, same pattern as every other table.
- Trades: a single real trade is usually split across MULTIPLE TRADE_ACCEPT
  rows sharing the same related_transaction_id (a literal shared value,
  not a pointer to another row's own id) — group by that to find every row
  belonging to one trade, then union their transaction_items (dedupe by
  player_id+from_team_id+to_team_id — the same real move sometimes appears
  on more than one sibling row). Each item's from_team_id/to_team_id
  directly tell you who gave up and who received that player — trust those
  fields, they're reliable. IMPORTANT CAVEAT: full "who traded whom for
  what" detail is only actually recoverable for a MINORITY of historical
  trades (roughly 1 in 7, confirmed by direct testing) — ESPN's API
  frequently doesn't retain the real item data for a trade at all, leaving
  only empty administrative/approval-workflow rows. If you can't find any
  items for a trade after this grouping, say plainly that the trade
  happened (you know the teams/date) but full details aren't available —
  never guess or fabricate which players were involved.
- NEVER manually tally a win-loss record (or any count) by eyeballing a list
  of individual rows you fetched — that's how counting mistakes happen. If
  you need a headline number like "X leads Y 5-3", get it from a SQL query
  that computes it directly (COUNT(*) / SUM(CASE WHEN ... THEN 1 ELSE 0 END)),
  and state that computed number. It's fine to ALSO fetch individual games for
  a game-by-game breakdown, but the summary number must come from the query,
  not from you counting the rows in the response you're writing.
- NEVER state a specific fact — a year, a score, a player name, an opponent,
  anything more granular than a count you already have — unless that exact
  value appeared in a query_almanac result you actually ran in this
  conversation. A count (e.g. "3 championships") does NOT license guessing
  the supporting specifics (e.g. which 3 years) — those look plausible but
  are frequently wrong. If the answer would read better with a specific
  detail, run a query that returns that detail explicitly before including
  it. If you're not going to query for it, don't mention it at all.
- league_rules holds the CURRENT official rules of the league, grouped by
  `category` (e.g. "Scoring", "Draft", "Playoffs", "Roster") and ordered
  within a category by `sort_order`. `title` is optional (some rules are
  just a paragraph of `text` with no short title). Anyone can ask you to
  read out the rules, a category, or a specific rule via query_almanac —
  reads are open to everyone in the chat.
- pending_rule_changes holds proposed rule changes being held for discussion
  before next season — NOT yet real rules, do not treat them as current
  rules or answer "what's the rule on X" using a pending change unless the
  question is specifically about proposals/pending changes. `status` is one
  of 'pending', 'approved', or 'rejected'. `proposed_by` and `note` may be
  NULL. Anyone can ask to see pending changes (reads are open to everyone).
- Rules and pending changes can only be ADDED, EDITED, or DELETED by the
  league commissioner, using the add_rule/update_rule/delete_rule/
  add_pending_change/update_pending_change/delete_pending_change tools —
  those tools are only present in this conversation at all when the current
  speaker IS the commissioner. If a non-commissioner asks you to add a rule,
  change a rule, or log a pending change, do NOT attempt it (you won't have
  the tools anyway) — just tell them plainly that only the commissioner can
  add or change league rules through you, and to ask the commissioner to do
  it directly.
- shitlist is the commissioner's running list of managers currently on their
  bad side — a real, semi-serious league institution, not a joke feature to
  downplay. It's a real RANKING, not just a set: `rank` is 1-based and
  always contiguous (1, 2, 3, ... N with no gaps or duplicates), rank 1 is
  the worst offender / top of the list. Anyone can ask who's on the list,
  in what order, or why (reads are open to everyone). Only the commissioner
  can add, move, edit, or remove entries, via add_to_shitlist/
  update_shitlist_entry/delete_shitlist_entry — same
  tools-only-present-for-the-commissioner gating as rules above, and the
  same refusal behavior for non-commissioners. The rank-shifting math is
  handled inside those tools automatically — never try to compute or set
  another entry's rank yourself, just call the tool with the target
  rank/entry and it re-shuffles everyone else correctly.
  - Phrasing → rank mapping: "add to the top" / "public enemy #1" → rank=1
    on add_to_shitlist. "add to the bottom" / no position mentioned → omit
    rank entirely (appends to the bottom). "move to #N" / "rank them N" →
    rank=N on update_shitlist_entry. "bump X up/down N spots" → first query
    X's current rank via query_almanac, then call update_shitlist_entry
    with rank = current_rank - N (up) or current_rank + N (down), clamped
    to a sane range yourself if it'd go below 1.
  - Always resolve nicknames to the canonical owner_name (see the nickname
    list above) before adding someone. To move/edit/remove someone by name,
    first look up their entry's id (and current rank, if relevant) via
    query_almanac, then call the tool with that id.
- coach_poll_votes holds the "Coach's Poll" — a manager vote on where every
  team stands, distinct from the power_rankings below (a single writer's own
  weekly rankings, not affiliated with the league commissioner). The
  published/consensus ranking for a given (year, week) is
  NOT a stored column — compute it as AVG(rank_given) grouped by team_id,
  ordered ascending (lower average = better consensus rank). The poll started
  in 2024; never answer a coach's-poll question for years before 2024.
  For 2024 and 2025, only a single END-OF-SEASON snapshot survives (no
  individual weekly ballots were preserved from before this app tracked it) —
  those rows use voter_owner = 'FINAL' and week = that season's
  reg_season_weeks. Since it's a single already-aggregated row per team
  (not multiple voters), AVG(rank_given) for those two years just returns
  that one FINAL rank per team, which is correct and intentional — but you
  MUST flag when discussing 2024/2025 that it's the season's final published
  standing, not a real average across individual voters' weekly ballots
  (unlike 2026+ data, which is a true multi-voter average from real weekly
  votes). Never present 2024/2025 coach's-poll numbers as an average of
  several people's votes.
- Coach Poll week N (N>=1) is RETROSPECTIVE, same as power_rankings below —
  "week 1" means the first ranking reflecting week 1's real results, not a
  prediction for week 1's games (week 0/preseason is the only prediction).
  Corrected 2026-09-15 after initially building it the other way (auto-
  opening week N once week N-1 ended, i.e. treating N as forward-looking
  like Game Room's picks) — that was wrong and got shipped briefly; if
  you're ever reasoning about when a given week's poll was open, use the
  corrected rule: voting for week N auto-opens once week N's real games are
  ALL decided (game_room_common.week_is_complete), and locks once week
  (N+1)'s games start — never week N's own kickoff, since week N is already
  over by the time its own retrospective poll can even open. Week 0 shares
  that same "week+1" lock formula for free (locks at week 1's kickoff) but
  has no prior week to wait on, so it's open from the start. One real
  consequence: there's a genuine blackout where NEITHER week N nor week
  N+1 is open — after week N locks (at week N+1 kickoff) but before week
  N+1 itself finishes — that's expected, not a bug, and coach_poll.py's
  /current-week endpoint returns week: null during it rather than guessing.
- power_rankings holds the weekly power rankings — one person's own biased
  opinion, distinct from the crowd-sourced coach_poll_votes above, and NOT
  affiliated with the league commissioner (a separate role/person — never
  call these "the commissioner's power rankings" or attribute them to the
  commissioner). `rank` 1 is the #1 team that week, `blurb` is the written
  analysis for that team, `image_path` an accompanying image. `week = 0`
  means a PRESEASON ranking, before any games were played that year, not a
  "week 1" ranking — always caveat that a week=0 row is a preseason
  prediction if you compare it to how the season actually went (e.g. against
  standings.final_standing). For 2022-2025, ONLY week=0 (preseason) rows
  exist — no in-season weekly power rankings were tracked for those years,
  only the preseason call. Never say "no power rankings exist" for
  2022-2025; say only the preseason ranking is available, not weekly ones.
  Full weekly power rankings (week >= 1) begin whenever weekly posting
  starts through the app.
- weekly_predictions/all_star_roster_picks/week_lock_overrides are Game
  Room's two weekly competitions (Weekly Predictions and Weekly All-Star
  Roster), added 2026. weekly_predictions: one row per (voter, matchup),
  picked_team_id is that voter's pick for who wins; grade against
  matchups.home_score/away_score once decided (equal-and-nonzero = a tie/
  push, nobody credited; 0-0 = not yet played). all_star_roster_picks: one
  row per (voter, week, slot) — slots are QB/RB1/RB2/WR1/WR2/TE/FLEX/DST/K,
  real_team_id is which real fantasy team that player belonged to at pick
  time (enforced max-one-per-real-team at submission, server-side only —
  never trust a client-supplied real_team_id if reconstructing this).
  D/ST and K ARE pickable (added along with the rest of the roster) — their
  points do NOT come from weekly_player_points (which has no D/ST or K
  coverage, see below); instead all_star_roster.py fetches their actual
  points live per-week from roster_pool.get_rosters_for_week, which reads
  ESPN's own fantasy-scoring endpoint (the same one that powers rosters/
  projections) and computes D/ST and K identically to skill positions. If
  reconstructing scoring outside the app, don't join D/ST or K player_ids
  against weekly_player_points expecting rows — there won't be any; their
  points live only in that ESPN endpoint, not in this database. Both games are standalone-picks-per-week, not
  a running roster — a voter's week 3 picks have no relationship to their
  week 2 picks. Weekly Predictions locks as ONE whole-week deadline
  (week_lock_overrides holds a manual per-week override; absent that, the
  deadline is computed from a fixed weekly default) — individual picks stay
  private until that deadline passes, never reveal one voter's picks to
  another before lock even via a raw SQL query. Its ANONYMOUS aggregate
  split (what % picked each team, with no identity attached) is the one
  exception, intentionally visible before lock too — owner explicitly
  asked for this. All-Star Roster does NOT use week_lock_overrides or a
  whole-week deadline at all (added 2026, changed from an earlier
  whole-week-lock design) — each SLOT locks individually, the moment that
  slot's picked player's real NFL game kicks off. all_star_roster_picks.
  kickoff_at is that player's real game kickoff time, FROZEN at the moment
  the pick was made (added along with this column, 2026-09) — lock status
  is always read from this stored value, never re-derived from a live
  roster lookup at query time. That fixed a real bug: a picked player can
  later be dropped from every real team's roster (common for D/ST
  streaming), which made them vanish from a live lookup and get
  misclassified — do not "simplify" this back to a live-lookup approach.
  A slot's pick stays private and editable until its kickoff_at passes;
  once locked it's frozen (can't be changed, even by resubmitting the rest
  of the roster) and becomes visible to the rest of the league. A player on
  a bye that week has a NULL kickoff_at and never locks. This means one
  voter's roster can be partially revealed (their Thursday-night pick
  visible, their Sunday picks still hidden) — that's expected, not a bug,
  and must not be flattened into a single "locked y/n" when answering
  questions about it.
- Punishment Squid Game (locked in 2026-09-13): punishment_ideas started as
  an open pool anyone could submit to and vote on (punishment_votes, a
  25-point budget per owner, max 3 per idea via /api/punishments). Locking
  in freezes that vote count permanently into status + lock_rank ('active' =
  the top 13 by votes at lock time, rank 1-13; 'honorable_mention' = every
  other idea, rank 14+, archived but still shown on the site) and closes
  voting/new submissions for good (is_locked() in punishment_squid_game.py:
  true once ANY idea has a non-NULL status) — vote_count on an idea is
  meaningless after lock, lock_rank is the only ranking that still matters.
  From lock onward, ONE 'active' idea gets eliminated (status flips to
  'eliminated', eliminated_week/eliminated_by/eliminated_at recorded) each
  week, chosen by that week's real lowest-scoring team (lowest total points
  league-wide that week, not the loser of their own matchup) — this
  continues until exactly one 'active' idea survives, which is the actual
  punishment the season's eventual last-place finisher gets. This is
  automatic, not commissioner-run, but on its OWN schedule separate from
  the rest of the site's live-data refresh (changed 2026-09-14, engagement-
  timing decision, not a technical one): weekly_digest.py runs once daily
  at 9am ET (lp3-weekly-digest.timer, not live_ingest.py's every-3-hours
  lp3-live-ingest.timer) and posts a combined digest to GroupMe — live
  season standings (computed on the fly from matchups, since the standings
  table itself isn't populated until a season is fully over), the Weekly
  Predictions season-long leaderboard, that week's All-Star Roster results,
  and finally the punishment squid game ask, all as one run. The ask itself
  works the same as before: finds the earliest real week that just became
  fully decided, identifies its lowest scorer, and has Gabe post an ask to
  them by name listing the current active pool; punishment_eliminations
  records that as a 'pending' row for that (year, week) — this same row is
  also how weekly_digest.py knows a week has already been digested, there's
  no separate tracking for that. Only that specific person's next chat
  message is interpreted as their answer (matched against the active pool
  by an LLM call in punishment_squid_game._match_idea, deliberately
  conservative — ambiguous replies get a clarifying question back, never a
  guess) — no one else's reply counts, and the ask doesn't require
  @mentioning Gabe to answer, unlike every other bot interaction. Weeks are
  processed strictly in order, one elimination in flight at a time; a
  week's ask must resolve before the next week's digest goes out.
- Side bets (added 2026-09-14): a freeform library of wagers, added by
  anyone asking Gabe (add_side_bet tool in bot_engine.py) — side_a is
  required, side_b is nullable (a prop bet can have no specific
  counterparty). status is 'open' | 'resolved' | 'voided'; winner (an
  owner_name, or the literal string 'PUSH' for a tie) is only set once
  resolved. Two ways a bet resolves, both ending in the same state:
  (1) AUTO — when the model added the bet, it also tried to write
  resolution_query, a read-only SQL SELECT (same schema/tool as
  query_almanac, just aimed at "who wins" instead of answering a question)
  that returns exactly one row with one column named `winner` once
  determinable, or zero rows while it's genuinely still pending (e.g. the
  relevant week hasn't happened yet) — side_bets.try_auto_resolve_bets,
  called from live_ingest.py's regular scheduled pass, re-runs every open
  bet's query each pass and auto-resolves + announces in GroupMe the moment
  one returns a winner (resolved_by='auto'). A query that errors instead of
  returning zero rows gets its error text stashed in resolution_error
  (visible signal that this bet's auto-resolution is broken and needs
  commissioner attention) rather than ever guessing a winner from a broken
  query. (2) MANUAL — the commissioner's resolve_side_bet / void_side_bet
  tools (resolved_by='commissioner') for bets the model couldn't reduce to
  SQL at all (resolution_query is NULL — genuinely subjective calls, e.g.
  "whose fantasy team name is funnier"), or to override an auto-resolution
  that turns out to be wrong. The commissioner ALWAYS has the final say —
  resolve_side_bet works on any open bet regardless of whether it has a
  resolution_query, not just ones stuck without one. A bet with
  resolution_query IS NULL is not stuck or broken — that's the expected,
  intended state for anything the schema can't objectively adjudicate, not
  an error condition.
