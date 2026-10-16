import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AUTH_KEY, loadAuth, parseError, LoginForm, FlaggedBanner } from '../components/OwnerLogin'

const SLOTS = ['QB', 'RB1', 'RB2', 'WR1', 'WR2', 'TE', 'FLEX', 'DST', 'K']
// Which slot a newly-picked player auto-fills, in priority order, per position.
const SLOT_PRIORITY_BY_POSITION = {
  QB: ['QB'],
  RB: ['RB1', 'RB2', 'FLEX'],
  WR: ['WR1', 'WR2', 'FLEX'],
  TE: ['TE', 'FLEX'],
  'D/ST': ['DST'],
  K: ['K'],
}
const POSITION_SORT_ORDER = ['QB', 'RB', 'WR', 'TE', 'K', 'D/ST']

function RosterSummaryBar({ picks, onRemove }) {
  return (
    <div className="grid grid-cols-3 sm:grid-cols-9 gap-2 mb-4">
      {SLOTS.map(slot => {
        const p = picks[slot]
        const locked = p?.locked
        return (
          <button
            key={slot}
            type="button"
            disabled={!p || locked}
            onClick={() => p && !locked && onRemove(slot)}
            className={`min-w-0 rounded-md border px-2 py-2 text-left transition-colors ${
              p ? 'border-green-600 bg-green-950/40 hover:bg-green-950/70' : 'border-gray-700 bg-gray-800'
            } ${locked ? 'cursor-default' : ''}`}
          >
            <p className="text-gray-500 text-[10px] uppercase tracking-wide">{slot}{locked && ' 🔒'}</p>
            <p className={`text-xs font-medium truncate ${p ? 'text-green-300' : 'text-gray-600'}`}>
              {p ? p.player_name : '—'}
            </p>
          </button>
        )
      })}
    </div>
  )
}

function PlayerRow({ player, isPicked, isDisabled, onToggle }) {
  return (
    <button
      type="button"
      disabled={isDisabled}
      onClick={() => onToggle(player)}
      className={`w-full flex items-center justify-between gap-2 text-sm rounded-md px-3 py-2 border transition-colors ${
        isPicked
          ? 'border-green-500 bg-green-950/50'
          : isDisabled
            ? 'border-gray-800 bg-gray-900 opacity-40 cursor-not-allowed'
            : 'border-gray-700 bg-gray-800 hover:border-gray-500'
      }`}
    >
      <span className="flex items-center gap-2 min-w-0">
        <span className="text-gray-500 text-xs w-9 flex-shrink-0">{player.position}</span>
        <span className={`truncate ${isPicked ? 'text-green-300 font-semibold' : 'text-gray-200'}`}>{player.player_name}</span>
      </span>
      <span className="flex items-center gap-3 flex-shrink-0 text-xs">
        <span className="text-gray-600 w-12 text-right">{player.opponent}{player.locked && ' 🔒'}</span>
        <span className="text-gray-400 w-10 text-right">{player.projected_points ?? '—'}</span>
        {isPicked && <span className="text-green-400 w-4 text-right">✓</span>}
      </span>
    </button>
  )
}

function TeamBrowser({ pool, picks, onToggle }) {
  const teams = useMemo(() => {
    const byId = new Map()
    for (const p of pool) {
      if (!byId.has(p.real_team_id)) {
        byId.set(p.real_team_id, { team_id: p.real_team_id, team_name: p.real_team_name, owner_name: p.real_owner_name, players: [] })
      }
      byId.get(p.real_team_id).players.push(p)
    }
    const list = [...byId.values()]
    list.sort((a, b) => a.team_name.localeCompare(b.team_name))
    for (const t of list) {
      t.players.sort((a, b) => {
        const posDiff = POSITION_SORT_ORDER.indexOf(a.position) - POSITION_SORT_ORDER.indexOf(b.position)
        if (posDiff !== 0) return posDiff
        return (b.projected_points ?? -1) - (a.projected_points ?? -1)
      })
    }
    return list
  }, [pool])

  const [index, setIndex] = useState(0)
  const team = teams[index]

  const pickedPlayerIds = useMemo(
    () => new Set(Object.values(picks).filter(Boolean).map(p => p.player_id)),
    [picks],
  )
  const pickByTeamId = useMemo(() => {
    const map = new Map()
    for (const pick of Object.values(picks)) {
      if (pick) map.set(pick.real_team_id, pick)
    }
    return map
  }, [picks])
  const usedTeamId = pickByTeamId.has(team?.team_id)
  const openSlotsBySlotName = slot => !picks[slot]

  if (!team) return null

  return (
    <div className="rounded-xl border border-gray-700 bg-gray-900 p-4 mb-4">
      <div className="flex items-center justify-between gap-2 mb-3">
        <button
          type="button"
          onClick={() => setIndex(i => Math.max(0, i - 1))}
          disabled={index === 0}
          className="text-gray-500 hover:text-gray-300 disabled:opacity-30 disabled:cursor-not-allowed px-2 py-1"
        >
          ← Prev
        </button>
        <div className="text-center min-w-0">
          <select
            value={index}
            onChange={e => setIndex(Number(e.target.value))}
            className="bg-transparent text-white font-semibold text-sm text-center border-none focus:outline-none"
          >
            {teams.map((t, i) => {
              const used = pickByTeamId.get(t.team_id)
              return (
                <option key={t.team_id} value={i} className="bg-gray-800">
                  {used ? `✓ ${t.team_name} — ${used.player_name}` : t.team_name}
                </option>
              )
            })}
          </select>
          <p className="text-gray-500 text-xs">{team.owner_name} · team {index + 1} of {teams.length}</p>
        </div>
        <button
          type="button"
          onClick={() => setIndex(i => Math.min(teams.length - 1, i + 1))}
          disabled={index === teams.length - 1}
          className="text-gray-500 hover:text-gray-300 disabled:opacity-30 disabled:cursor-not-allowed px-2 py-1"
        >
          Next →
        </button>
      </div>

      {usedTeamId && (
        <p className="text-green-500 text-xs text-center mb-2">
          ✓ You already picked from this team — tap your pick to remove them
        </p>
      )}

      <div className="space-y-1">
        {team.players.map(p => {
          const isPicked = pickedPlayerIds.has(p.player_id)
          const isDisabled = isPicked
            ? p.locked
            : (usedTeamId || p.locked || SLOT_PRIORITY_BY_POSITION[p.position].every(s => !openSlotsBySlotName(s)))
          return (
            <PlayerRow key={p.player_id} player={p} isPicked={isPicked} isDisabled={isDisabled} onToggle={onToggle} />
          )
        })}
      </div>
    </div>
  )
}

function RevealedPicks({ allPicks }) {
  const owners = Object.keys(allPicks)
  if (owners.length === 0) return null
  return (
    <div className="rounded-xl border border-gray-700 bg-gray-900 p-4 mb-4">
      <h3 className="text-gray-200 font-semibold mb-1">Revealed So Far</h3>
      <p className="text-gray-600 text-xs mb-3">A pick shows up here the moment that player's real game kicks off.</p>
      <div className="space-y-3">
        {owners.map(owner => (
          <div key={owner}>
            <p className="text-gray-300 text-sm font-medium mb-1">{owner}</p>
            <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-gray-500">
              {SLOTS.filter(s => allPicks[owner][s]).map(s => (
                <span key={s}>{s}: <span className="text-gray-300">{allPicks[owner][s].player_name}</span></span>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function ResultsSection({ year, week, refreshKey }) {
  const [results, setResults] = useState(null)

  useEffect(() => {
    fetch(`/api/all-star-roster/${year}/${week}/results`).then(r => r.json()).then(setResults)
  }, [year, week, refreshKey])

  if (!results) return null

  if (!results.graded) {
    return (
      <p className="text-gray-500 text-sm text-center py-4 border border-dashed border-gray-700 rounded-xl">
        Check back after this week's games finish for results.
      </p>
    )
  }

  return (
    <div className="rounded-xl border border-gray-700 bg-gray-900 p-4">
      <h3 className="text-gray-200 font-semibold mb-3">Week {week} Results</h3>
      <ol className="space-y-3">
        {results.standings.map((s, i) => (
          <li key={s.owner_name}>
            <div className="flex items-center justify-between text-sm mb-1">
              <span className="text-gray-300"><span className="text-gray-600 mr-2">{i + 1}.</span>{s.owner_name}</span>
              <span className="text-green-400 font-semibold">{s.total} pts</span>
            </div>
            <div className="pl-6 text-xs text-gray-600 space-y-0.5">
              {s.players.map(p => (
                <div key={p.slot} className="flex justify-between">
                  <span>{p.slot}: {p.player_name}</span>
                  <span>{p.points}</span>
                </div>
              ))}
            </div>
          </li>
        ))}
      </ol>
    </div>
  )
}

export default function AllStarRoster() {
  const navigate = useNavigate()
  const [auth, setAuth] = useState(loadAuth)
  const [owners, setOwners] = useState([])
  const [currentWeek, setCurrentWeek] = useState(null)
  const [pool, setPool] = useState([])
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

  useEffect(() => {
    if (!currentWeek) return
    fetch(`/api/all-star-roster/pool/${currentWeek.year}/${currentWeek.week}`).then(r => r.json()).then(d => setPool(d.players))
  }, [currentWeek])

  function loadWeek() {
    if (!currentWeek) return
    fetch(`/api/all-star-roster/${currentWeek.year}/${currentWeek.week}`, { headers: authHeaders })
      .then(r => r.json())
      .then(d => { setWeekData(d); setPicks(d.my_picks || {}) })
  }

  useEffect(loadWeek, [currentWeek, auth])

  function handleToggle(player) {
    setSubmitted(false)
    setPicks(prev => {
      const existingSlot = Object.keys(prev).find(s => prev[s]?.player_id === player.player_id)
      if (existingSlot) {
        const next = { ...prev }
        delete next[existingSlot]
        return next
      }
      const openSlot = SLOT_PRIORITY_BY_POSITION[player.position].find(s => !prev[s])
      if (!openSlot) return prev
      return { ...prev, [openSlot]: player }
    })
  }

  function handleRemove(slot) {
    setSubmitted(false)
    setPicks(prev => {
      const next = { ...prev }
      delete next[slot]
      return next
    })
  }

  function handleSubmit() {
    if (SLOTS.some(s => !picks[s])) {
      setError('Fill every slot before submitting.')
      return
    }
    setSubmitting(true)
    setError('')
    setFlagged('')
    setSubmitted(false)
    fetch(`/api/all-star-roster/${currentWeek.year}/${currentWeek.week}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders },
      body: JSON.stringify({ picks: SLOTS.map(slot => ({ slot, player_id: picks[slot].player_id })) }),
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

  if (!currentWeek || pool.length === 0) return <p className="text-gray-500 text-center py-16">Loading...</p>

  return (
    <div className="max-w-2xl mx-auto">
      <button onClick={() => navigate('/game-room')} className="text-gray-500 hover:text-gray-300 text-sm mb-4 inline-block">
        ← Back to Game Room
      </button>
      <h1 className="text-3xl font-bold text-white mb-2" style={{ fontFamily: 'var(--heading)' }}>
        Weekly All-Star Roster
      </h1>
      <p className="text-gray-400 text-sm mb-2">
        Browse each real team, pick up to one player from each — max one player per real team. Week {currentWeek.week}.
      </p>
      <p className="text-gray-600 text-xs mb-6">
        Each pick locks on its own — once that player's real game kicks off, the slot is locked in and visible to the rest of the league.
      </p>

      {auth ? (
        <div className="flex items-center justify-between mb-4">
          <p className="text-gray-500 text-xs">
            Logged in as <span className="text-gray-300 font-medium">{auth.owner_name}</span>
          </p>
          <button onClick={handleLogout} className="text-gray-500 hover:text-gray-300 text-xs underline">Log out</button>
        </div>
      ) : (
        <div className="mb-6">
          <LoginForm owners={owners} onLoggedIn={setAuth} helpText="Log in to build your roster." />
        </div>
      )}

      <FlaggedBanner message={flagged} />

      {auth && weekData && (
        <>
          <RosterSummaryBar picks={picks} onRemove={handleRemove} />
          <TeamBrowser pool={pool} picks={picks} onToggle={handleToggle} />
        </>
      )}

      {error && <p className="text-red-400 text-sm mb-3">{error}</p>}
      {submitted && !error && (
        <div className="rounded-lg border-2 border-green-500 bg-green-950/70 px-4 py-3 mb-4 text-center">
          <p className="text-green-300 font-bold">✓ Roster submitted!</p>
        </div>
      )}

      {auth && weekData && (
        <button
          onClick={handleSubmit}
          disabled={submitting}
          className="w-full mb-4 bg-green-700 hover:bg-green-600 disabled:opacity-50 text-white rounded-md px-4 py-2.5 text-sm font-semibold transition-colors"
        >
          {submitting ? 'Submitting...' : submitted ? '✓ Submitted — tap to resubmit' : 'Submit roster'}
        </button>
      )}

      {weekData && (
        <p className="text-gray-600 text-xs text-center mb-6">
          {weekData.submitted_count} owner{weekData.submitted_count === 1 ? '' : 's'} submitted so far
        </p>
      )}

      {weekData && <RevealedPicks allPicks={weekData.all_picks} />}

      <ResultsSection year={currentWeek.year} week={currentWeek.week} refreshKey={refreshKey} />
    </div>
  )
}
