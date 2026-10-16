import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { DndContext, closestCenter, PointerSensor, TouchSensor, useSensor, useSensors } from '@dnd-kit/core'
import { SortableContext, verticalListSortingStrategy, arrayMove, useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { AUTH_KEY, loadAuth, parseError, LoginForm, FlaggedBanner } from '../components/OwnerLogin'
import PowerRankingsJourney from '../components/PowerRankingsJourney'

const RANKINGS_AUTHOR = 'Austin Lamb'

function imageUrl(imagePath) {
  return imagePath ? `/api/power-rankings/images/${imagePath}` : null
}

function formatRank(r) {
  return Number.isInteger(r) ? `#${r}` : `${r.toFixed(1)} avg`
}

function TeamLink({ teamId, children }) {
  const navigate = useNavigate()
  return (
    <button
      type="button"
      onClick={() => navigate(`/team/${teamId}`)}
      className="text-green-400 hover:underline text-left"
    >
      {children}
    </button>
  )
}

function RankBadge({ rank }) {
  const color = rank === 1 ? 'text-yellow-400' : rank <= 3 ? 'text-green-400' : 'text-gray-400'
  return <span className={`text-2xl font-bold ${color}`} style={{ fontFamily: 'var(--heading)' }}>#{rank}</span>
}

// ── Shared pieces ────────────────────────────────────────────────────────────

function RankingCard({ entry }) {
  const img = imageUrl(entry.image_path)
  return (
    <div className="rounded-xl border border-gray-700 bg-gray-900 overflow-hidden">
      {img && <img src={img} alt={entry.team_name} className="w-full h-48 object-cover" />}
      <div className="p-4">
        <div className="flex items-center justify-between mb-1">
          <RankBadge rank={entry.rank} />
          <TeamLink teamId={entry.team_id}>
            <span className="text-gray-500 text-xs">{entry.owner_name}</span>
          </TeamLink>
        </div>
        <h3 className="text-gray-100 font-semibold mb-2">
          <TeamLink teamId={entry.team_id}>{entry.team_name}</TeamLink>
        </h3>
        {entry.blurb && <p className="text-gray-400 text-sm whitespace-pre-wrap">{entry.blurb}</p>}
      </div>
    </div>
  )
}

function CoachPollSidebar({ poll }) {
  if (!poll) return null

  return (
    <div className="rounded-xl border border-gray-700 bg-gray-900 p-4">
      <h3 className="text-gray-200 font-semibold mb-1">Coach's Poll</h3>
      <p className="text-gray-600 text-xs mb-3">{poll.ballot_count} ballot{poll.ballot_count === 1 ? '' : 's'} cast</p>
      {!poll.revealed ? (
        <p className="text-gray-500 text-sm">
          Results are hidden until this week's Power Rankings are published — they reveal together.
        </p>
      ) : poll.results.length === 0 ? (
        <p className="text-gray-500 text-sm">No coach's poll votes came in this week.</p>
      ) : (
        <ol className="space-y-1.5">
          {poll.results.map((r, i) => (
            <li key={r.team_id} className="flex items-center justify-between text-sm">
              <span className="text-gray-400 flex items-center gap-2">
                <span className="text-gray-600">{i + 1}.</span>
                <TeamLink teamId={r.team_id}>{r.owner_name}</TeamLink>
              </span>
              <span className="text-gray-600 text-xs">
                {r.consensus_rank.toFixed(1)}
                {r.first_place_votes > 0 && (
                  <span className="text-yellow-500 ml-1">({r.first_place_votes})</span>
                )}
              </span>
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}

function SortableTeamRow({ teamId, position, ownerName }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: teamId })
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  }
  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`flex items-center gap-3 bg-gray-800 border rounded-md pl-3 pr-1 py-2 ${
        isDragging ? 'border-green-600 shadow-lg relative z-10' : 'border-gray-700'
      }`}
    >
      <span className="text-gray-500 font-semibold text-sm w-5 flex-shrink-0 text-center">{position}</span>
      <TeamLink teamId={teamId}>
        <span className="text-gray-300 text-sm">{ownerName}</span>
      </TeamLink>
      <button
        type="button"
        {...attributes}
        {...listeners}
        className="ml-auto text-gray-500 hover:text-gray-300 cursor-grab active:cursor-grabbing px-3 py-2 touch-none select-none text-lg leading-none"
        aria-label="Drag to reorder"
      >
        &#8942;&#8942;
      </button>
    </div>
  )
}

function BallotForm({ year, week, teams, authHeaders, myBallot, onSubmitted }) {
  const [order, setOrder] = useState(() => teams.map(t => t.team_id))
  const [hasAppliedBallot, setHasAppliedBallot] = useState(false)
  const [error, setError] = useState('')
  const [flagged, setFlagged] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [submitted, setSubmitted] = useState(false)

  const teamById = {}
  teams.forEach(t => { teamById[t.team_id] = t })

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 200, tolerance: 8 } })
  )

  // myBallot loads asynchronously (fetched after this form already mounted),
  // so the initial `order` state above can't see it yet -- apply it here, once,
  // as soon as it actually arrives. Guarded by hasAppliedBallot so it never
  // clobbers a reorder the person has already started making.
  useEffect(() => {
    if (hasAppliedBallot || !myBallot || Object.keys(myBallot).length === 0) return
    setOrder(
      [...teams]
        .sort((a, b) => (myBallot[a.team_id] ?? 999) - (myBallot[b.team_id] ?? 999))
        .map(t => t.team_id)
    )
    setHasAppliedBallot(true)
  }, [myBallot, teams, hasAppliedBallot])

  function handleDragEnd(event) {
    const { active, over } = event
    if (!over || active.id === over.id) return
    setOrder(prev => arrayMove(prev, prev.indexOf(active.id), prev.indexOf(over.id)))
    setSubmitted(false)
    setHasAppliedBallot(true)
  }

  function handleSubmit(e) {
    e.preventDefault()
    const ballot = order.map((teamId, i) => ({ team_id: teamId, rank_given: i + 1 }))
    setSubmitting(true)
    setError('')
    setFlagged('')
    setSubmitted(false)
    fetch(`/api/coach-poll/${year}/${week}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders },
      body: JSON.stringify({ ballot }),
    })
      .then(async r => {
        if (r.status === 423) { setFlagged(await parseError(r)); return }
        if (!r.ok) throw new Error(await parseError(r))
        setSubmitted(true)
        onSubmitted()
      })
      .catch(err => setError(err.message))
      .finally(() => setSubmitting(false))
  }

  return (
    <form onSubmit={handleSubmit} className="rounded-xl border border-gray-700 bg-gray-900 p-4">
      <FlaggedBanner message={flagged} />
      <h3 className="text-gray-200 font-semibold mb-1">Your ballot — Week {week}</h3>
      <p className="text-gray-600 text-xs mb-3">Drag to reorder — best team on top.</p>
      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
        <SortableContext items={order} strategy={verticalListSortingStrategy}>
          <div className="space-y-2">
            {order.map((teamId, i) => (
              <SortableTeamRow
                key={teamId}
                teamId={teamId}
                position={i + 1}
                ownerName={teamById[teamId]?.owner_name}
              />
            ))}
          </div>
        </SortableContext>
      </DndContext>
      {error && <p className="text-red-400 text-sm mt-3">{error}</p>}
      {submitted && !error && (
        <div className="mt-3 rounded-lg border-2 border-green-500 bg-green-950/70 px-4 py-3 text-center">
          <p className="text-green-300 font-bold text-base">✓ Ballot submitted!</p>
        </div>
      )}
      <button
        type="submit"
        disabled={submitting}
        className={`mt-4 w-full rounded-md px-4 py-2.5 text-sm font-semibold transition-colors disabled:opacity-50 ${
          submitted ? 'bg-green-600 hover:bg-green-500 text-white' : 'bg-green-700 hover:bg-green-600 text-white'
        }`}
      >
        {submitting ? 'Submitting...' : submitted ? '✓ Submitted — tap to resubmit' : 'Submit ballot'}
      </button>
    </form>
  )
}

// ── Current Season ───────────────────────────────────────────────────────────

function CurrentSeasonTab({ currentWeek, auth, setAuth, owners }) {
  const [weeksInfo, setWeeksInfo] = useState(null)
  const [teams, setTeams] = useState([])
  const [liveWeek, setLiveWeek] = useState(null)
  const [selectedWeek, setSelectedWeek] = useState(null)
  const [weekData, setWeekData] = useState(null)
  const [poll, setPoll] = useState(null)
  const [roomGrades, setRoomGrades] = useState(null)
  const [loading, setLoading] = useState(true)

  const authHeaders = auth ? { Authorization: `Bearer ${auth.token}` } : {}

  useEffect(() => {
    if (!currentWeek?.year) { setLoading(false); return }
    setLoading(true)
    Promise.all([
      fetch(`/api/power-rankings/weeks/${currentWeek.year}`).then(r => r.json()),
      fetch(`/api/power-rankings/teams/${currentWeek.year}`).then(r => r.ok ? r.json() : []),
      // Whichever week is currently auto-open for Coach Poll voting (null
      // during a real blackout while a week's games are in progress -- see
      // that endpoint's own docstring) -- separate from currentWeek, which
      // is Power Rankings' own manually-set editorial pointer and won't
      // include a week nobody's posted anything for yet. Without this, a
      // week that just auto-opened for voting has no tab to reach it from
      // at all (found 2026-09-15: real bug, not hypothetical -- a newly
      // auto-opened week with zero data posted was completely unreachable
      // in the UI even though the backend had it open). Deliberately this
      // endpoint, not Game Room's current-week -- that one is forward-
      // looking (which week's games are being played) while Coach Poll's
      // own weeks are retrospective (which week's results are being
      // ranked), and they're off by one from each other except during that
      // same blackout window where they're not related by a fixed offset
      // at all.
      fetch(`/api/coach-poll/current-week?year=${currentWeek.year}`).then(r => r.ok ? r.json() : { week: null }),
      // Room Grades has no week axis (a one-time preseason crew assessment,
      // not a per-week pick) -- fetched once per year alongside everything
      // else, not re-fetched on week switches.
      fetch(`/api/pod-grades/${currentWeek.year}/public`).then(r => r.ok ? r.json() : { grades_by_team: {} }),
    ])
      .then(([weeks, teamsData, live, grades]) => {
        setWeeksInfo(weeks)
        setTeams(teamsData)
        setLiveWeek(live.week)
        // JSON object keys are always strings, but team_id is used as a
        // number everywhere else on this page -- re-key here once so
        // downstream lookups by team.team_id (a number) just work.
        const byNumericId = {}
        Object.entries(grades.grades_by_team || {}).forEach(([teamId, g]) => { byNumericId[Number(teamId)] = g })
        setRoomGrades(byNumericId)
        setSelectedWeek(currentWeek.week)
      })
      .finally(() => setLoading(false))
  }, [currentWeek])

  useEffect(() => {
    if (selectedWeek === null || !currentWeek?.year) return
    fetch(`/api/power-rankings/${currentWeek.year}/${selectedWeek}`).then(r => r.json()).then(setWeekData)
    fetch(`/api/coach-poll/${currentWeek.year}/${selectedWeek}`, { headers: authHeaders }).then(r => r.json()).then(setPoll)
  }, [selectedWeek, currentWeek, auth])

  if (loading) return <p className="text-gray-500 text-center py-16">Loading...</p>
  if (!currentWeek?.year) return <p className="text-gray-500 text-center py-16">No season set up yet.</p>

  const dataWeeks = weeksInfo ? [...weeksInfo.power_rankings_weeks, ...weeksInfo.coach_poll_weeks] : []
  const extraWeeks = liveWeek === null ? [currentWeek.week] : [currentWeek.week, liveWeek]
  const unionWeeks = Array.from(new Set([...dataWeeks, ...extraWeeks])).sort((a, b) => a - b)

  return (
    <div>
      <div className="flex gap-2 mb-6 flex-wrap">
        {unionWeeks.map(w => (
          <button
            key={w}
            type="button"
            onClick={() => setSelectedWeek(w)}
            className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
              selectedWeek === w ? 'bg-green-700 text-white' : 'bg-gray-800 text-gray-400 hover:text-white'
            }`}
          >
            {w === 0 ? 'Preseason' : `Week ${w}`}{w === currentWeek.week ? ' •' : ''}{w === liveWeek ? ' 🗳️' : ''}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          {weekData?.posted ? (
            <PowerRankingsJourney
              rankings={weekData.rankings}
              year={currentWeek.year}
              previousWeek={weekData.previous_week}
              roomGrades={roomGrades}
            />
          ) : (
            <p className="text-gray-500 text-sm py-8 text-center border border-dashed border-gray-700 rounded-xl">
              No power rankings posted for this week yet.
            </p>
          )}
        </div>

        <div className="space-y-4">
          {poll && (
            poll.locked ? (
              <div className="rounded-lg border-2 border-red-500 bg-red-950/70 px-4 py-3 text-center">
                <p className="text-red-300 font-bold">🔒 Voting locked</p>
                <p className="text-red-400 text-xs mt-1">
                  This week's games have already started
                  {poll.lock_at && ` (locked at ${new Date(poll.lock_at).toLocaleString()})`}.
                </p>
              </div>
            ) : !poll.voting_open ? (
              <div className="rounded-lg border border-gray-700 bg-gray-800/50 px-4 py-3 text-center">
                <p className="text-gray-300 text-sm font-medium">Voting isn't open yet</p>
                <p className="text-gray-500 text-xs mt-1">It opens automatically once the previous week wraps up.</p>
              </div>
            ) : auth ? (
              <div>
                <div className="flex items-center justify-between mb-2">
                  <p className="text-gray-500 text-xs">
                    Logged in as <span className="text-gray-300 font-medium">{auth.owner_name}</span>
                  </p>
                  <button
                    onClick={() => { localStorage.removeItem(AUTH_KEY); setAuth(null) }}
                    className="text-gray-500 hover:text-gray-300 text-xs underline"
                  >
                    Log out
                  </button>
                </div>
                <BallotForm
                  year={currentWeek.year}
                  week={selectedWeek}
                  teams={teams}
                  authHeaders={authHeaders}
                  myBallot={poll?.my_ballot}
                  onSubmitted={() => {
                    fetch(`/api/coach-poll/${currentWeek.year}/${selectedWeek}`, { headers: authHeaders })
                      .then(r => r.json()).then(setPoll)
                  }}
                />
              </div>
            ) : (
              <LoginForm owners={owners} onLoggedIn={setAuth} helpText="Log in to submit your coach's poll ballot." />
            )
          )}
          <CoachPollSidebar poll={poll} />
        </div>
      </div>
    </div>
  )
}

// ── Historical Rankings ──────────────────────────────────────────────────────

function AccuracySummaryCard({ title, stats, note }) {
  if (!stats || stats.years_covered === 0) {
    return (
      <div className="rounded-xl border border-gray-700 bg-gray-900 p-4">
        <h3 className="text-gray-200 font-semibold mb-1">{title}</h3>
        <p className="text-gray-600 text-sm">No years tracked yet.</p>
      </div>
    )
  }
  return (
    <div className="rounded-xl border border-gray-700 bg-gray-900 p-4">
      <h3 className="text-gray-200 font-semibold mb-3">{title}</h3>
      <div className="grid grid-cols-3 gap-3 text-center">
        <div>
          <p className="text-2xl font-bold text-green-400" style={{ fontFamily: 'var(--heading)' }}>
            {stats.avg_rank_error ?? '—'}
          </p>
          <p className="text-gray-600 text-xs mt-1">avg spots off</p>
        </div>
        <div>
          <p className="text-2xl font-bold text-green-400" style={{ fontFamily: 'var(--heading)' }}>
            {stats.champion_hits}/{stats.champion_total}
          </p>
          <p className="text-gray-600 text-xs mt-1">called the champ</p>
        </div>
        <div>
          <p className="text-2xl font-bold text-green-400" style={{ fontFamily: 'var(--heading)' }}>
            {stats.last_place_hits}/{stats.last_place_total}
          </p>
          <p className="text-gray-600 text-xs mt-1">called last place</p>
        </div>
      </div>
      {note && <p className="text-gray-600 text-xs mt-3">{note}</p>}
    </div>
  )
}

function YearComparisonTable({ title, entries }) {
  return (
    <div>
      <h4 className="text-gray-300 text-sm font-semibold mb-2">{title}</h4>
      {!entries ? (
        <p className="text-gray-600 text-xs">Not tracked this year.</p>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-gray-700">
          <table className="w-full text-sm">
            <thead className="bg-gray-800 text-gray-400 uppercase text-xs tracking-wider">
              <tr>
                <th className="px-3 py-2 text-left">Predicted</th>
                <th className="px-3 py-2 text-left">Owner</th>
                <th className="px-3 py-2 text-left">Final</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800">
              {entries.map(e => (
                <tr key={e.team_id} className="bg-gray-900">
                  <td className="px-3 py-2 text-gray-200 font-medium">{formatRank(e.predicted_rank)}</td>
                  <td className="px-3 py-2"><TeamLink teamId={e.team_id}>{e.owner_name}</TeamLink></td>
                  <td className="px-3 py-2 text-gray-400">{e.final_standing ? `#${e.final_standing}` : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function HistoricalRankingsTab() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch('/api/power-rankings/history').then(r => r.json()).then(setData).finally(() => setLoading(false))
  }, [])

  if (loading) return <p className="text-gray-500 text-center py-16">Loading...</p>
  if (!data || data.years.length === 0) {
    return <p className="text-gray-500 text-center py-16">No historical data yet.</p>
  }

  return (
    <div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-10">
        <AccuracySummaryCard
          title="Power Rankings accuracy"
          stats={data.summary.power_rankings}
          note="Based on each year's preseason call vs. how the season actually finished."
        />
        <AccuracySummaryCard
          title="Coach's Poll accuracy"
          stats={data.summary.coach_poll}
          note="2024-2025 reflect that season's final published poll, not a full weekly-averaged prediction."
        />
      </div>

      <div className="space-y-10">
        {data.years.map(y => (
          <div key={y.year}>
            <h3 className="text-lg font-semibold text-white mb-3">{y.year}</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <YearComparisonTable title="Power Rankings (Preseason)" entries={y.power_rankings?.entries} />
              <YearComparisonTable
                title={`Coach's Poll${y.coach_poll?.is_final_snapshot ? ' (season-final snapshot)' : ''}`}
                entries={y.coach_poll?.entries}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Admin ────────────────────────────────────────────────────────────────────

function AdminTeamCard({ teamId, position, ownerName, teamName, entry, uploading, onBlurbChange, onImageUpload }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: teamId })
  const style = { transform: CSS.Transform.toString(transform), transition }
  const img = imageUrl(entry.image_path)

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`rounded-xl border bg-gray-900 p-4 ${isDragging ? 'border-green-600 shadow-lg relative z-10' : 'border-gray-700'}`}
    >
      <div className="flex items-center gap-3 mb-3">
        <span className="text-gray-500 font-semibold text-sm w-6 flex-shrink-0 text-center">{position}</span>
        <span className="text-gray-200 font-medium">{ownerName}</span>
        <span className="text-gray-600 text-xs">{teamName}</span>
        <button
          type="button"
          {...attributes}
          {...listeners}
          className="ml-auto text-gray-500 hover:text-gray-300 cursor-grab active:cursor-grabbing px-3 py-2 touch-none select-none text-lg leading-none"
          aria-label="Drag to reorder"
        >
          &#8942;&#8942;
        </button>
      </div>
      <textarea
        value={entry.blurb || ''}
        onChange={e => onBlurbChange(e.target.value)}
        placeholder="Write-up..."
        rows={3}
        className="w-full bg-gray-800 text-gray-200 border border-gray-600 rounded-md px-3 py-2 text-sm mb-2"
      />
      <div className="flex items-center gap-3">
        <input
          type="file"
          accept="image/jpeg,image/png,image/gif,image/webp"
          onChange={e => e.target.files[0] && onImageUpload(e.target.files[0])}
          className="text-gray-400 text-xs"
        />
        {uploading && <span className="text-gray-500 text-xs">Uploading...</span>}
        {img && <img src={img} alt="" className="h-12 w-12 object-cover rounded-md" />}
      </div>
    </div>
  )
}

function AdminTab({ currentWeek, authHeaders, onCurrentWeekChanged }) {
  const [teams, setTeams] = useState([])
  const [order, setOrder] = useState([])
  const [entries, setEntries] = useState({})
  const [yearInput, setYearInput] = useState(currentWeek?.year || '')
  const [weekInput, setWeekInput] = useState(currentWeek?.week ?? 0)
  const [status, setStatus] = useState('')
  const [error, setError] = useState('')
  const [uploading, setUploading] = useState(null)

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 200, tolerance: 8 } })
  )

  useEffect(() => {
    if (currentWeek?.year && yearInput === '') {
      setYearInput(currentWeek.year)
      setWeekInput(currentWeek.week)
    }
  }, [currentWeek])

  useEffect(() => {
    if (!yearInput) return
    fetch(`/api/power-rankings/teams/${yearInput}`)
      .then(r => r.json())
      .then(teamsData => setTeams(teamsData))
  }, [yearInput])

  // Load this (year, week)'s saved work whenever either changes, in
  // priority order: an existing draft (most recent work-in-progress) >
  // already-published data for this exact week > the most recently
  // PUBLISHED earlier week this season, carried over as a starting point
  // (rank order + images -- but NOT blurbs, those are week-specific
  // commentary that should start blank) > blank, natural team_id order, if
  // nothing exists yet at all.
  useEffect(() => {
    if (!yearInput || weekInput === '' || teams.length === 0) return
    const naturalOrder = teams.map(t => t.team_id)
    const blankEntries = {}
    teams.forEach(t => { blankEntries[t.team_id] = { blurb: '', image_path: null } })

    function applyRankings(rankings, { keepBlurb }) {
      const sorted = [...rankings].sort((a, b) => a.rank - b.rank)
      const nextEntries = { ...blankEntries }
      sorted.forEach(r => {
        nextEntries[r.team_id] = {
          blurb: keepBlurb ? (r.blurb || '') : '',
          image_path: r.image_path || null,
        }
      })
      setOrder(sorted.map(r => r.team_id))
      setEntries(nextEntries)
    }

    function useBlank() {
      setOrder(naturalOrder)
      setEntries(blankEntries)
    }

    fetch(`/api/power-rankings/${yearInput}/${weekInput}/draft`, { headers: authHeaders })
      .then(r => r.ok ? r.json() : { has_draft: false })
      .then(draft => {
        if (draft.has_draft) { applyRankings(draft.rankings, { keepBlurb: true }); return }
        return fetch(`/api/power-rankings/${yearInput}/${weekInput}`)
          .then(r => r.json())
          .then(published => {
            if (published.posted) { applyRankings(published.rankings, { keepBlurb: true }); return }
            return fetch(`/api/power-rankings/weeks/${yearInput}`)
              .then(r => r.json())
              .then(weeksInfo => {
                const priorWeeks = weeksInfo.power_rankings_weeks.filter(w => w < Number(weekInput))
                if (priorWeeks.length === 0) { useBlank(); return }
                const priorWeek = Math.max(...priorWeeks)
                return fetch(`/api/power-rankings/${yearInput}/${priorWeek}`)
                  .then(r => r.json())
                  .then(prior => applyRankings(prior.rankings, { keepBlurb: false }))
              })
          })
      })
      .catch(useBlank)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [yearInput, weekInput, teams])

  function updateBlurb(teamId, value) {
    setEntries(prev => ({ ...prev, [teamId]: { ...prev[teamId], blurb: value } }))
  }

  function handleDragEnd(event) {
    const { active, over } = event
    if (!over || active.id === over.id) return
    setOrder(prev => arrayMove(prev, prev.indexOf(active.id), prev.indexOf(over.id)))
    setStatus('')
  }

  function handleImageUpload(teamId, file) {
    setUploading(teamId)
    const formData = new FormData()
    formData.append('file', file)
    fetch('/api/power-rankings/images', { method: 'POST', headers: authHeaders, body: formData })
      .then(async r => {
        if (!r.ok) throw new Error(await parseError(r))
        return r.json()
      })
      .then(data => setEntries(prev => ({ ...prev, [teamId]: { ...prev[teamId], image_path: data.image_path } })))
      .catch(err => setError(err.message))
      .finally(() => setUploading(null))
  }

  function currentRankings() {
    return order.map((teamId, i) => ({
      team_id: teamId,
      rank: i + 1,
      blurb: entries[teamId]?.blurb || null,
      image_path: entries[teamId]?.image_path || null,
    }))
  }

  function handleSaveDraft() {
    setError('')
    setStatus('Saving draft...')
    fetch(`/api/power-rankings/${yearInput}/${weekInput}/draft`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders },
      body: JSON.stringify({ rankings: currentRankings() }),
    })
      .then(async r => {
        if (!r.ok) throw new Error(await parseError(r))
        setStatus('Draft saved!')
      })
      .catch(err => { setError(err.message); setStatus('') })
  }

  function handlePublish() {
    const rankings = currentRankings()
    if (order.length !== teams.length) {
      setError('Rankings are out of sync with the current team list — reload and try again.')
      return
    }
    setError('')
    setStatus('Publishing...')
    fetch(`/api/power-rankings/${yearInput}/${weekInput}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders },
      body: JSON.stringify({ rankings }),
    })
      .then(async r => {
        if (!r.ok) throw new Error(await parseError(r))
        setStatus('Published!')
      })
      .catch(err => { setError(err.message); setStatus('') })
  }

  function handleSetCurrentWeek() {
    fetch('/api/power-rankings/current-week', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders },
      body: JSON.stringify({ year: Number(yearInput), week: Number(weekInput) }),
    })
      .then(async r => {
        if (!r.ok) throw new Error(await parseError(r))
        onCurrentWeekChanged()
      })
      .catch(err => setError(err.message))
  }

  return (
    <div>
      <div className="flex flex-wrap items-end gap-3 mb-6 rounded-xl border border-gray-700 bg-gray-900 p-4">
        <div>
          <label className="block text-gray-400 text-xs mb-1">Year</label>
          <input
            type="number"
            value={yearInput}
            onChange={e => setYearInput(e.target.value)}
            className="bg-gray-800 text-gray-200 border border-gray-600 rounded-md px-3 py-1.5 text-sm w-24"
          />
        </div>
        <div>
          <label className="block text-gray-400 text-xs mb-1">Week (0 = preseason)</label>
          <input
            type="number"
            value={weekInput}
            onChange={e => setWeekInput(e.target.value)}
            className="bg-gray-800 text-gray-200 border border-gray-600 rounded-md px-3 py-1.5 text-sm w-24"
          />
        </div>
        <button
          onClick={handleSetCurrentWeek}
          className="bg-gray-700 hover:bg-gray-600 text-white rounded-md px-4 py-2 text-sm font-medium transition-colors"
        >
          Set as current week
        </button>
        {currentWeek?.year && (
          <span className="text-gray-500 text-xs">
            Current: {currentWeek.year} / {currentWeek.week === 0 ? 'Preseason' : `Wk ${currentWeek.week}`}
          </span>
        )}
      </div>

      <p className="text-gray-600 text-xs mb-3">Drag to reorder — best team on top.</p>
      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
        <SortableContext items={order} strategy={verticalListSortingStrategy}>
          <div className="space-y-4">
            {order.map((teamId, i) => {
              const t = teams.find(t => t.team_id === teamId)
              if (!t) return null
              return (
                <AdminTeamCard
                  key={teamId}
                  teamId={teamId}
                  position={i + 1}
                  ownerName={t.owner_name}
                  teamName={t.team_name}
                  entry={entries[teamId] || {}}
                  uploading={uploading === teamId}
                  onBlurbChange={value => updateBlurb(teamId, value)}
                  onImageUpload={file => handleImageUpload(teamId, file)}
                />
              )
            })}
          </div>
        </SortableContext>
      </DndContext>

      {error && <p className="text-red-400 text-sm mt-4">{error}</p>}
      {status && <p className="text-green-400 text-sm mt-4">{status}</p>}

      {teams.length > 0 && (
        <div className="mt-4 flex gap-3">
          <button
            onClick={handleSaveDraft}
            className="bg-gray-700 hover:bg-gray-600 text-white rounded-md px-6 py-2.5 text-sm font-semibold transition-colors"
          >
            Save draft
          </button>
          <button
            onClick={handlePublish}
            className="bg-green-700 hover:bg-green-600 text-white rounded-md px-6 py-2.5 text-sm font-semibold transition-colors"
          >
            Publish
          </button>
        </div>
      )}
    </div>
  )
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function PowerRankings() {
  const [tab, setTab] = useState('current')
  const [auth, setAuth] = useState(loadAuth)
  const [owners, setOwners] = useState([])
  const [currentWeek, setCurrentWeek] = useState(null)

  const authHeaders = auth ? { Authorization: `Bearer ${auth.token}` } : {}
  const isAuthor = auth?.owner_name === RANKINGS_AUTHOR

  function loadCurrentWeek() {
    fetch('/api/power-rankings/current-week').then(r => r.json()).then(setCurrentWeek)
  }

  useEffect(() => {
    loadCurrentWeek()
    fetch('/api/punishments/owners').then(r => r.json()).then(setOwners)
  }, [])

  const tabs = [
    { key: 'current', label: 'Current Season' },
    { key: 'historical', label: 'Historical Rankings' },
    ...(isAuthor ? [{ key: 'admin', label: 'Admin' }] : []),
  ]

  return (
    <div>
      <h1 className="text-3xl font-bold text-white mb-2" style={{ fontFamily: 'var(--heading)' }}>
        Power Rankings
      </h1>
      <p className="text-gray-400 mb-6">
        One person's completely biased weekly opinion on where every team stands — plus the coach's poll,
        where everyone else gets a vote.
      </p>

      <div className="flex gap-2 border-b border-gray-700 mb-6">
        {tabs.map(({ key, label }) => (
          <button
            key={key}
            type="button"
            onClick={() => setTab(key)}
            className={`px-4 py-2 text-sm font-medium rounded-t-md transition-colors ${
              tab === key
                ? 'bg-gray-900 text-green-400 border border-b-0 border-gray-700'
                : 'text-gray-400 hover:text-white'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === 'current' && (
        <CurrentSeasonTab currentWeek={currentWeek} auth={auth} setAuth={setAuth} owners={owners} />
      )}
      {tab === 'historical' && <HistoricalRankingsTab />}
      {tab === 'admin' && isAuthor && (
        <AdminTab currentWeek={currentWeek} authHeaders={authHeaders} onCurrentWeekChanged={loadCurrentWeek} />
      )}
    </div>
  )
}
