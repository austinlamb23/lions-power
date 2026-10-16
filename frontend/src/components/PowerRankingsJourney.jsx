import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'

function imageUrl(imagePath) {
  return imagePath ? `/api/power-rankings/images/${imagePath}` : null
}

function rankColor(rank) {
  return rank === 1 ? 'text-yellow-400' : rank <= 3 ? 'text-green-400' : 'text-gray-400'
}

// rank_change is null either when there's no earlier posted week to compare
// against at all, or (rarer) when this specific team wasn't ranked in that
// earlier week -- previousWeek tells those two apart (see get_week's own
// comment in power_rankings.py) so this never claims "NEW" during a
// season's very first posted ranking, where that'd be true of everyone and
// tells the reader nothing.
function RankChangeBadge({ change, previousWeek }) {
  if (previousWeek === null) return null
  if (change === null) {
    return <span className="text-blue-400 text-xs font-semibold align-middle ml-2">NEW</span>
  }
  if (change === 0) {
    return <span className="text-gray-500 text-xs font-semibold align-middle ml-2">—</span>
  }
  const up = change > 0
  return (
    <span className={`text-xs font-semibold align-middle ml-2 ${up ? 'text-green-400' : 'text-red-400'}`}>
      {up ? '▲' : '▼'} {up ? '+' : ''}{change}
    </span>
  )
}

// Rough letter-grade -> color bucket, ignoring +/- (A-/A/A+ read the same at
// a glance) -- purely a visual cue for a public reveal, not a precise scale.
function gradeColor(grade) {
  const letter = grade[0]
  if (letter === 'A') return 'text-green-400'
  if (letter === 'B') return 'text-teal-300'
  if (letter === 'C') return 'text-yellow-400'
  if (letter === 'D') return 'text-orange-400'
  return 'text-red-400'
}

const GRADE_CATEGORY_ORDER = ['QB', 'RB', 'WR', 'TE', 'BENCH']

// Room Grades has no week dimension (it's a one-time preseason assessment,
// not a weekly pick) -- roomGrades is keyed only by team_id, same object
// shown regardless of which week's rankings are on screen. A category with
// nobody's grade in yet is left out entirely rather than shown as blank --
// this is a public reveal of the crew's grading, not the crew's own
// in-progress tool (that one shows "—" placeholders; see PodRoomGrades.jsx).
function RoomGradesPanel({ grades }) {
  if (!grades) return null
  const categories = GRADE_CATEGORY_ORDER.filter(c => grades[c] && Object.keys(grades[c]).length > 0)
  if (categories.length === 0) return null

  return (
    <div>
      <p className="text-gray-500 text-xs uppercase tracking-wider mb-2">The Pod's Room Grades</p>
      <div className="space-y-1.5">
        {categories.map(category => (
          <div key={category} className="flex items-baseline gap-2 text-sm flex-wrap">
            <span className="text-gray-600 text-xs w-14 flex-shrink-0">{category}</span>
            <span className="flex flex-wrap gap-x-3 gap-y-0.5">
              {Object.entries(grades[category]).map(([grader, grade]) => (
                <span key={grader} className="text-gray-400">
                  {grader.split(' ')[0]}: <span className={`font-semibold ${gradeColor(grade)}`}>{grade}</span>
                </span>
              ))}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

const SLOT_ORDER = ['QB', 'RB', 'WR', 'TE', 'FLEX', 'D/ST', 'K']

function groupBySlot(players) {
  const bySlot = {}
  players.forEach(p => {
    const key = p.slot || p.position
    if (!bySlot[key]) bySlot[key] = []
    bySlot[key].push(p)
  })
  return SLOT_ORDER.filter(s => bySlot[s]).map(s => [s, bySlot[s]])
}

function RosterPanel({ roster, status }) {
  if (status === 'loading') {
    return <p className="text-gray-600 text-sm italic">Loading current roster...</p>
  }
  if (status === 'error') {
    return <p className="text-gray-600 text-sm italic">Roster unavailable right now.</p>
  }
  if (!roster) return null

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-3">
      <div>
        <p className="text-gray-500 text-xs uppercase tracking-wider mb-1.5">Starters</p>
        <div className="space-y-1">
          {groupBySlot(roster.starters).map(([slot, players]) => (
            players.map((p, i) => (
              <div key={slot + i} className="flex items-baseline gap-2 text-sm">
                <span className="text-gray-600 text-xs w-10 flex-shrink-0">{slot}</span>
                <span className="text-gray-300">{p.name}</span>
              </div>
            ))
          ))}
        </div>
      </div>
      {roster.bench.length > 0 && (
        <div>
          <p className="text-gray-500 text-xs uppercase tracking-wider mb-1.5">Bench</p>
          <div className="space-y-1">
            {roster.bench.map((p, i) => (
              <div key={i} className="flex items-baseline gap-2 text-sm">
                <span className="text-gray-600 text-xs w-10 flex-shrink-0">{p.position}</span>
                <span className="text-gray-500">{p.name}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default function PowerRankingsJourney({ rankings, year, previousWeek = null, roomGrades = null }) {
  const navigate = useNavigate()
  // Countdown order: worst rank first, building toward #1.
  const ordered = [...rankings].sort((a, b) => b.rank - a.rank)
  const [activeIndex, setActiveIndex] = useState(0)
  const [rosters, setRosters] = useState({}) // team_id -> { status: 'loading'|'ready'|'error', data }
  const touchStartX = useRef(null)

  const clampedIndex = Math.min(activeIndex, ordered.length - 1)
  const team = ordered[clampedIndex]

  function goTo(i) {
    setActiveIndex(Math.max(0, Math.min(ordered.length - 1, i)))
  }
  const goNext = () => goTo(clampedIndex + 1)
  const goPrev = () => goTo(clampedIndex - 1)

  useEffect(() => {
    function onKeyDown(e) {
      if (e.key === 'ArrowRight') goNext()
      if (e.key === 'ArrowLeft') goPrev()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [clampedIndex, ordered.length])

  useEffect(() => {
    if (!team) return
    if (rosters[team.team_id]) return
    setRosters(prev => ({ ...prev, [team.team_id]: { status: 'loading' } }))
    fetch(`/api/power-rankings/roster/${team.team_id}?year=${year}`)
      .then(r => { if (!r.ok) throw new Error('roster fetch failed'); return r.json() })
      .then(data => setRosters(prev => ({ ...prev, [team.team_id]: { status: 'ready', data } })))
      .catch(() => setRosters(prev => ({ ...prev, [team.team_id]: { status: 'error' } })))
  }, [team, year])

  // Fetch the current slide's own image before it's needed, then warm the
  // browser cache for both neighbors -- the images endpoint sends an
  // immutable Cache-Control header, so once fetched here a slide switch
  // just reads it back out of cache instead of hitting the network again.
  useEffect(() => {
    for (const t of [ordered[clampedIndex - 1], ordered[clampedIndex + 1]]) {
      const src = imageUrl(t?.image_path)
      if (src) new window.Image().src = src
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clampedIndex])

  if (!team) return null

  const img = imageUrl(team.image_path)
  const rosterState = rosters[team.team_id] || { status: 'loading' }

  function onTouchStart(e) { touchStartX.current = e.touches[0].clientX }
  function onTouchEnd(e) {
    if (touchStartX.current === null) return
    const delta = e.changedTouches[0].clientX - touchStartX.current
    touchStartX.current = null
    if (delta < -50) goNext()
    if (delta > 50) goPrev()
  }

  return (
    <div className="rounded-xl border border-gray-700 bg-gray-900 overflow-hidden">
      <style>{`
        @keyframes prj-fade-up { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
        .prj-stage { opacity: 0; animation: prj-fade-up 0.45s ease-out forwards; }
      `}</style>

      {/* Progress bar */}
      <div className="flex gap-1 p-3 pb-0">
        {ordered.map((t, i) => (
          <button
            key={t.team_id}
            type="button"
            onClick={() => goTo(i)}
            aria-label={`Jump to ${t.team_name}`}
            className={`h-1 flex-1 rounded-full transition-colors ${
              i <= clampedIndex ? 'bg-green-500' : 'bg-gray-700'
            }`}
          />
        ))}
      </div>

      <div onTouchStart={onTouchStart} onTouchEnd={onTouchEnd}>
        {/* Stage 1: image, full width, never cropped — source images vary in
            aspect ratio (square logos, portrait AI art, etc.), so object-contain
            inside a flexible-height frame instead of forcing a fixed square crop. */}
        {img && (
          <div
            key={team.team_id + '-hero'}
            className="prj-stage relative bg-black flex items-center justify-center"
            style={{ maxHeight: '22rem' }}
          >
            <img
              src={img}
              alt={team.team_name}
              className="w-full object-contain"
              style={{ maxHeight: '22rem' }}
            />
            <span
              className={`absolute top-3 left-3 text-3xl sm:text-4xl font-bold ${rankColor(team.rank)} drop-shadow-[0_2px_4px_rgba(0,0,0,0.9)]`}
              style={{ fontFamily: 'var(--heading)' }}
            >
              #{team.rank}
              <RankChangeBadge change={team.rank_change} previousWeek={previousWeek} />
            </span>
          </div>
        )}

        <div className="p-5 sm:p-8">
        {!img && (
          <div key={team.team_id + '-hero'} className="prj-stage mb-5">
            <span
              className={`text-5xl sm:text-6xl font-bold ${rankColor(team.rank)}`}
              style={{ fontFamily: 'var(--heading)' }}
            >
              #{team.rank}
            </span>
            <RankChangeBadge change={team.rank_change} previousWeek={previousWeek} />
          </div>
        )}

        {/* Stage 2: name */}
        <div
          key={team.team_id + '-name'}
          className="prj-stage mb-5"
          style={{ animationDelay: '0.12s' }}
        >
          <button
            type="button"
            onClick={() => navigate(`/team/${team.team_id}`)}
            className="text-2xl sm:text-3xl font-bold text-white hover:text-green-400 text-left"
            style={{ fontFamily: 'var(--heading)' }}
          >
            {team.team_name}
          </button>
          <p className="text-gray-500 text-sm mt-0.5">{team.owner_name}</p>
        </div>

        {/* Stage 3: roster */}
        <div
          key={team.team_id + '-roster'}
          className="prj-stage mb-5 pb-5 border-b border-gray-800"
          style={{ animationDelay: '0.24s' }}
        >
          <RosterPanel roster={rosterState.data} status={rosterState.status} />
        </div>

        {/* Stage 3.5: room grades, only when the crew has actually graded
            this team -- roomGrades is keyed by team_id with no week axis */}
        {roomGrades?.[team.team_id] && (
          <div
            key={team.team_id + '-grades'}
            className="prj-stage mb-5 pb-5 border-b border-gray-800"
            style={{ animationDelay: '0.3s' }}
          >
            <RoomGradesPanel grades={roomGrades[team.team_id]} />
          </div>
        )}

        {/* Stage 4: write-up */}
        <div key={team.team_id + '-blurb'} className="prj-stage" style={{ animationDelay: '0.36s' }}>
          {team.blurb ? (
            <p className="text-gray-300 text-sm sm:text-base whitespace-pre-wrap leading-relaxed">{team.blurb}</p>
          ) : (
            <p className="text-gray-600 text-sm italic">No write-up yet.</p>
          )}
        </div>
        </div>
      </div>

      {/* Navigation */}
      <div className="flex items-center justify-between border-t border-gray-800 p-3">
        <button
          type="button"
          onClick={goPrev}
          disabled={clampedIndex === 0}
          className="text-gray-400 hover:text-white disabled:opacity-30 disabled:hover:text-gray-400 text-sm font-medium px-3 py-1.5"
        >
          &larr; Prev
        </button>
        <span className="text-gray-600 text-xs">{clampedIndex + 1} / {ordered.length}</span>
        <button
          type="button"
          onClick={goNext}
          disabled={clampedIndex === ordered.length - 1}
          className="text-gray-400 hover:text-white disabled:opacity-30 disabled:hover:text-gray-400 text-sm font-medium px-3 py-1.5"
        >
          Next &rarr;
        </button>
      </div>
    </div>
  )
}
