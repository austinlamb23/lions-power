import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AUTH_KEY, loadAuth, parseError, LoginForm, FlaggedBanner } from '../components/OwnerLogin'
import GameRoomLock from '../components/GameRoomLock'

function TeamButton({ label, ownerName, selected, disabled, onClick }) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={`flex-1 rounded-md border px-3 py-3 text-left transition-colors ${
        selected
          ? 'border-green-500 bg-green-950/50'
          : 'border-gray-700 bg-gray-800 hover:border-gray-500'
      } ${disabled ? 'opacity-60 cursor-not-allowed' : ''}`}
    >
      <p className={`text-sm font-semibold ${selected ? 'text-green-300' : 'text-gray-200'}`}>{label}</p>
      <p className="text-gray-500 text-xs mt-0.5">{ownerName}</p>
    </button>
  )
}

function RosterColumn({ side, detail }) {
  if (!detail) return <p className="text-gray-600 text-xs text-center py-4">Loading roster...</p>
  return (
    <div className="flex-1 min-w-0">
      <div className="flex items-baseline justify-between mb-2">
        <p className="text-gray-300 text-xs font-semibold truncate">{detail.team_name}</p>
        <p className="text-green-400 text-xs font-semibold whitespace-nowrap ml-2">{detail.projected_total} proj</p>
      </div>
      <div className="space-y-1">
        {detail.starters.map(p => (
          <div key={p.player_id} className="flex items-center justify-between text-xs gap-2">
            <span className="text-gray-500 w-7 flex-shrink-0">{p.slot}</span>
            <span className="text-gray-300 truncate flex-1 min-w-0">{p.name}</span>
            <span className="text-gray-600 w-11 flex-shrink-0 text-right">{p.opponent}</span>
            <span className="text-gray-400 w-8 flex-shrink-0 text-right">{p.projected_points ?? '—'}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function pickersFor(allPicks, homeTeamId, teamId) {
  return Object.entries(allPicks)
    .filter(([, picks]) => picks[homeTeamId] === teamId)
    .map(([owner]) => owner)
}

function MatchupRow({ m, year, week, myPick, consensus, allPicks, locked, reallyLocked, onPick }) {
  const [expanded, setExpanded] = useState(false)
  const [detail, setDetail] = useState(null)
  const total = consensus?.total || 0
  const homePct = consensus?.by_team?.[m.home_team_id]?.pct ?? 0
  const awayPct = consensus?.by_team?.[m.away_team_id]?.pct ?? 0

  function toggleExpanded() {
    const next = !expanded
    setExpanded(next)
    if (next && !detail) {
      fetch(`/api/weekly-predictions/${year}/${week}/matchup/${m.home_team_id}`)
        .then(r => r.json())
        .then(setDetail)
    }
  }

  return (
    <div className="rounded-xl border border-gray-700 bg-gray-900 p-4">
      <div className="flex gap-3">
        <TeamButton
          label={m.home_team_name} ownerName={m.home_owner_name}
          selected={myPick === m.home_team_id} disabled={locked}
          onClick={() => onPick(m.home_team_id, m.home_team_id)}
        />
        <span className="text-gray-600 text-xs self-center">vs</span>
        <TeamButton
          label={m.away_team_name} ownerName={m.away_owner_name}
          selected={myPick === m.away_team_id} disabled={locked}
          onClick={() => onPick(m.home_team_id, m.away_team_id)}
        />
      </div>
      {locked && m.decided && (
        <p className="text-gray-400 text-xs mt-2 text-center">
          Final: {m.home_team_name} {m.home_score} – {m.away_score} {m.away_team_name}
          {m.winner_team_id && <span className="text-green-400"> · winner: {m.winner_team_id === m.home_team_id ? m.home_team_name : m.away_team_name}</span>}
        </p>
      )}
      {total > 0 && (
        <div className="mt-3">
          <div className="flex h-1.5 rounded-full overflow-hidden bg-gray-800">
            <div style={{ width: `${homePct}%` }} className="bg-green-600" />
            <div style={{ width: `${awayPct}%` }} className="bg-gray-500" />
          </div>
          <div className="flex justify-between text-[11px] text-gray-500 mt-1">
            <span>{homePct}%</span>
            <span>{total} pick{total === 1 ? '' : 's'} in</span>
            <span>{awayPct}%</span>
          </div>
        </div>
      )}

      {reallyLocked && (
        <div className="mt-3 grid grid-cols-2 gap-3 text-xs border-t border-gray-800 pt-3">
          <div>
            <p className="text-gray-500 mb-1">{m.home_team_name}</p>
            <p className="text-gray-300">{pickersFor(allPicks, m.home_team_id, m.home_team_id).join(', ') || '—'}</p>
          </div>
          <div className="text-right">
            <p className="text-gray-500 mb-1">{m.away_team_name}</p>
            <p className="text-gray-300">{pickersFor(allPicks, m.home_team_id, m.away_team_id).join(', ') || '—'}</p>
          </div>
        </div>
      )}

      <button
        type="button"
        onClick={toggleExpanded}
        className="w-full text-gray-500 hover:text-gray-300 text-xs mt-3 pt-2 border-t border-gray-800 flex items-center justify-center gap-1"
      >
        {expanded ? '▲ Hide rosters & projections' : '▼ Rosters & projections'}
      </button>

      {expanded && (
        <div className="flex flex-col sm:flex-row gap-4 mt-3 divide-y divide-gray-800 sm:divide-y-0">
          <div className="pb-3 sm:pb-0 sm:flex-1 sm:min-w-0">
            <RosterColumn side="home" detail={detail?.home} />
          </div>
          <div className="pt-3 sm:pt-0 sm:flex-1 sm:min-w-0">
            <RosterColumn side="away" detail={detail?.away} />
          </div>
        </div>
      )}
    </div>
  )
}

function LeaderboardTable({ year }) {
  const [standings, setStandings] = useState(null)

  useEffect(() => {
    fetch(`/api/weekly-predictions/leaderboard/${year}`).then(r => r.json()).then(d => setStandings(d.standings))
  }, [year])

  if (!standings) return null
  if (standings.length === 0) {
    return <p className="text-gray-500 text-sm text-center py-4">No decided matchups yet this season.</p>
  }

  return (
    <div className="rounded-xl border border-gray-700 bg-gray-900 p-4">
      <h3 className="text-gray-200 font-semibold mb-3">Season Leaderboard</h3>
      <ol className="space-y-1.5">
        {standings.map((s, i) => (
          <li key={s.owner_name} className="flex items-center justify-between text-sm">
            <span className="text-gray-300"><span className="text-gray-600 mr-2">{i + 1}.</span>{s.owner_name}</span>
            <span className="text-gray-400">{s.correct} / {s.total}</span>
          </li>
        ))}
      </ol>
    </div>
  )
}

export default function WeeklyPredictions() {
  const navigate = useNavigate()
  const [auth, setAuth] = useState(loadAuth)
  const [owners, setOwners] = useState([])
  const [currentWeek, setCurrentWeek] = useState(null)
  const [weekData, setWeekData] = useState(null)
  const [picks, setPicks] = useState({})
  const [error, setError] = useState('')
  const [flagged, setFlagged] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [submitted, setSubmitted] = useState(false)
  const [refreshKey, setRefreshKey] = useState(0)

  const authHeaders = auth ? { Authorization: `Bearer ${auth.token}` } : {}

  useEffect(() => {
    fetch('/api/game-room/current-week?year=2026').then(r => r.json()).then(setCurrentWeek)
    fetch('/api/punishments/owners').then(r => r.json()).then(setOwners)
  }, [])

  function loadWeek() {
    if (!currentWeek) return
    fetch(`/api/weekly-predictions/${currentWeek.year}/${currentWeek.week}`, { headers: authHeaders })
      .then(r => r.json())
      .then(d => { setWeekData(d); setPicks(d.my_picks || {}) })
  }

  useEffect(loadWeek, [currentWeek, auth])

  function handlePick(homeTeamId, pickedTeamId) {
    setPicks(prev => ({ ...prev, [homeTeamId]: pickedTeamId }))
    setSubmitted(false)
  }

  function handleSubmit() {
    const body = {
      picks: weekData.matchups.map(m => ({ home_team_id: m.home_team_id, picked_team_id: picks[m.home_team_id] })),
    }
    if (body.picks.some(p => !p.picked_team_id)) {
      setError('Pick a winner for every matchup before submitting.')
      return
    }
    setSubmitting(true)
    setError('')
    setFlagged('')
    setSubmitted(false)
    fetch(`/api/weekly-predictions/${currentWeek.year}/${currentWeek.week}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders },
      body: JSON.stringify(body),
    })
      .then(async r => {
        if (r.status === 423) { setFlagged(await parseError(r)); return }
        if (!r.ok) throw new Error(await parseError(r))
        setSubmitted(true)
        setRefreshKey(k => k + 1)
        loadWeek()
      })
      .catch(err => setError(err.message))
      .finally(() => setSubmitting(false))
  }

  function handleLogout() {
    localStorage.removeItem(AUTH_KEY)
    setAuth(null)
  }

  if (!currentWeek || !weekData) return <p className="text-gray-500 text-center py-16">Loading...</p>

  const locked = weekData.locked

  return (
    <div className="max-w-2xl mx-auto">
      <button onClick={() => navigate('/game-room')} className="text-gray-500 hover:text-gray-300 text-sm mb-4 inline-block">
        ← Back to Game Room
      </button>
      <h1 className="text-3xl font-bold text-white mb-2" style={{ fontFamily: 'var(--heading)' }}>
        Weekly Predictions
      </h1>
      <p className="text-gray-400 text-sm mb-6">
        Pick the winner of every real matchup, week {currentWeek.week}.
      </p>

      <GameRoomLock year={currentWeek.year} week={currentWeek.week} refreshKey={refreshKey} />

      {auth ? (
        <div className="flex items-center justify-between mb-4">
          <p className="text-gray-500 text-xs">
            Logged in as <span className="text-gray-300 font-medium">{auth.owner_name}</span>
          </p>
          <button onClick={handleLogout} className="text-gray-500 hover:text-gray-300 text-xs underline">Log out</button>
        </div>
      ) : (
        <div className="mb-6">
          <LoginForm owners={owners} onLoggedIn={setAuth} helpText="Log in to submit your predictions." />
        </div>
      )}

      <FlaggedBanner message={flagged} />

      <div className="space-y-3 mb-4">
        {weekData.matchups.map(m => (
          <MatchupRow
            key={m.home_team_id} m={m}
            year={currentWeek.year} week={currentWeek.week}
            myPick={picks[m.home_team_id]}
            consensus={weekData.consensus[m.home_team_id]}
            allPicks={weekData.all_picks}
            locked={locked || !auth}
            reallyLocked={locked}
            onPick={handlePick}
          />
        ))}
      </div>

      {error && <p className="text-red-400 text-sm mb-3">{error}</p>}
      {submitted && !error && (
        <div className="rounded-lg border-2 border-green-500 bg-green-950/70 px-4 py-3 mb-4 text-center">
          <p className="text-green-300 font-bold">✓ Picks submitted!</p>
        </div>
      )}

      {auth && !locked && (
        <button
          onClick={handleSubmit}
          disabled={submitting}
          className="w-full mb-8 bg-green-700 hover:bg-green-600 disabled:opacity-50 text-white rounded-md px-4 py-2.5 text-sm font-semibold transition-colors"
        >
          {submitting ? 'Submitting...' : submitted ? '✓ Submitted — tap to resubmit' : 'Submit picks'}
        </button>
      )}

      <LeaderboardTable year={currentWeek.year} />
    </div>
  )
}
