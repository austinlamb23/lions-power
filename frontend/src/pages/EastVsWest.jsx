import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

function StatRow({ label, value }) {
  return (
    <div className="flex items-center justify-between py-3 gap-2">
      <span className="text-gray-400 text-xs sm:text-sm">{label}</span>
      <span className="text-white font-bold text-base sm:text-lg">{value}</span>
    </div>
  )
}

function DivisionsSummaryCard({ divisions, expandedDivision, onToggleExpand }) {
  return (
    <div className="rounded-xl border border-gray-700 bg-gray-900 p-4 sm:p-6">
      <div className="grid grid-cols-2 divide-x divide-gray-800">
        {divisions.map((division, i) => {
          const winPct = division.win_pct != null ? `${(division.win_pct * 100).toFixed(1)}%` : '—'
          const expanded = expandedDivision === division.division
          return (
            <div key={division.division} className={i === 0 ? 'pr-3 sm:pr-6' : 'pl-3 sm:pl-6'}>
              <h2 className="text-lg sm:text-2xl font-bold text-white mb-2" style={{ fontFamily: 'var(--heading)' }}>
                {division.division}
              </h2>
              <div className="flex flex-col divide-y divide-gray-800">
                <button
                  onClick={() => onToggleExpand(division.division)}
                  className="flex items-center justify-between py-3 text-left hover:bg-gray-800/50 -mx-2 px-2 rounded transition-colors gap-2"
                >
                  <span className="text-gray-400 text-xs sm:text-sm">Championships</span>
                  <span className="flex items-center gap-1.5">
                    <span className="text-white font-bold text-base sm:text-lg">{division.championships}</span>
                    <span className={`text-gray-500 text-xs transition-transform ${expanded ? 'rotate-180' : ''}`}>▾</span>
                  </span>
                </button>
                {expanded && (
                  <div className="py-2 pl-1 flex flex-col gap-1">
                    {division.champions_list.length === 0 ? (
                      <p className="text-xs text-gray-600 py-2">No championships in this range.</p>
                    ) : (
                      division.champions_list.map(c => (
                        <div key={c.year} className="flex justify-between text-xs sm:text-sm py-1 gap-2">
                          <span className="text-gray-500 shrink-0">{c.year}</span>
                          <span className="text-gray-200 text-right truncate">{c.owner_name}</span>
                        </div>
                      ))
                    )}
                  </div>
                )}
                <StatRow label="Runner-ups" value={division.runner_ups} />
                <StatRow label="Playoffs Made" value={division.playoff_appearances} />
                <StatRow label="Total Wins" value={division.total_wins} />
                <StatRow label="Total Win %" value={winPct} />
                <StatRow label="Total Points" value={division.total_points?.toLocaleString()} />
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function InterdivisionCard({ m }) {
  const total = m.wins_a + m.wins_b + m.ties
  const pctA = total ? (m.wins_a / total) * 100 : 50
  const pctB = total ? (m.wins_b / total) * 100 : 50
  return (
    <div className="rounded-xl border border-gray-700 bg-gray-900 p-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <div className="text-3xl font-bold text-white">{m.wins_a}</div>
          <div className="text-xs text-gray-400 uppercase tracking-wide mt-1">{m.division_a} wins</div>
        </div>
        {m.ties > 0 && (
          <div className="text-center">
            <div className="text-lg font-bold text-gray-400">{m.ties}</div>
            <div className="text-xs text-gray-600 uppercase tracking-wide mt-1">Ties</div>
          </div>
        )}
        <div className="text-right">
          <div className="text-3xl font-bold text-white">{m.wins_b}</div>
          <div className="text-xs text-gray-400 uppercase tracking-wide mt-1">{m.division_b} wins</div>
        </div>
      </div>
      <div className="h-3 rounded-full overflow-hidden bg-gray-800 flex">
        <div className="h-full bg-green-700" style={{ width: `${pctA}%` }} />
        <div className="h-full bg-gray-600" style={{ width: `${pctB}%` }} />
      </div>
      <div className="flex justify-between mt-2 text-xs text-gray-500">
        <span>{m.division_a}</span>
        <span>{m.games} total games</span>
        <span>{m.division_b}</span>
      </div>
    </div>
  )
}

function RostersCard({ divisions, years, rostersByDivision, navigate }) {
  return (
    <div className="rounded-xl border border-gray-700 bg-gray-900 p-4 sm:p-6">
      <div className="grid grid-cols-2 divide-x divide-gray-800">
        {divisions.map((division, i) => (
          <div key={division.division} className={i === 0 ? 'pr-3 sm:pr-6' : 'pl-3 sm:pl-6'}>
            <p className="text-xs text-gray-500 uppercase tracking-wide mb-3">{division.division}</p>
            <div className="flex flex-col gap-4 max-h-[32rem] overflow-y-auto pr-1">
              {years.map(year => (
                <div key={year}>
                  <p className="text-xs text-gray-600 uppercase tracking-wide mb-1">{year}</p>
                  <div className="flex flex-col gap-1">
                    {(rostersByDivision[division.division]?.[year] || []).map(r => (
                      <button
                        key={r.team_id}
                        onClick={() => navigate(`/owner/${encodeURIComponent(r.owner_name)}`)}
                        className="text-left text-xs sm:text-sm text-gray-200 hover:text-green-400 hover:underline truncate block w-full"
                      >
                        {r.owner_name}
                        <span className="text-gray-600 text-xs ml-1 hidden sm:inline">{r.team_name}</span>
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function EastVsWest() {
  const navigate = useNavigate()
  const [seasons, setSeasons] = useState([])
  const [yearMode, setYearMode] = useState('all') // 'all' | 'single' | 'range'
  const [yearSingle, setYearSingle] = useState('')
  const [yearFrom, setYearFrom] = useState('')
  const [yearTo, setYearTo] = useState('')
  const [data, setData] = useState(null)
  const [expandedDivision, setExpandedDivision] = useState(null)

  useEffect(() => {
    fetch('/api/almanac/seasons')
      .then(r => r.json())
      .then(seasons => {
        setSeasons(seasons)
        if (seasons.length > 0) {
          setYearSingle(String(seasons[0].year))
          setYearTo(String(seasons[0].year))
          setYearFrom(String(seasons[seasons.length - 1].year))
        }
      })
  }, [])

  useEffect(() => {
    const params = new URLSearchParams()
    if (yearMode === 'single' && yearSingle) {
      params.set('year_from', yearSingle)
      params.set('year_to', yearSingle)
    } else if (yearMode === 'range' && yearFrom && yearTo) {
      params.set('year_from', yearFrom)
      params.set('year_to', yearTo)
    }
    fetch(`/api/almanac/divisions?${params}`)
      .then(r => r.json())
      .then(setData)
  }, [yearMode, yearSingle, yearFrom, yearTo])

  if (!data) return <div className="text-gray-500 py-12 text-center">Loading...</div>

  const { divisions, interdivision_h2h, rosters } = data

  const rostersByDivision = {}
  for (const r of rosters) {
    rostersByDivision[r.division] = rostersByDivision[r.division] || {}
    rostersByDivision[r.division][r.year] = rostersByDivision[r.division][r.year] || []
    rostersByDivision[r.division][r.year].push(r)
  }
  const allYears = [...new Set(rosters.map(r => r.year))].sort((a, b) => b - a)

  return (
    <div className="max-w-5xl mx-auto">
      <button onClick={() => navigate(-1)} className="text-gray-400 hover:text-white text-sm mb-6 flex items-center gap-1">
        ← Back
      </button>

      <h1 className="text-3xl font-bold text-white mb-2" style={{ fontFamily: 'var(--heading)' }}>
        East vs West
      </h1>
      <p className="text-gray-400 mb-6">
        Division history and interdivision bragging rights.
      </p>

      {/* Season filter */}
      <div className="flex items-center gap-2 mb-8">
        <select
          value={yearMode}
          onChange={e => setYearMode(e.target.value)}
          className="bg-gray-800 text-gray-200 border border-gray-600 rounded-md px-3 py-1.5 text-sm"
        >
          <option value="all">All Seasons</option>
          <option value="single">Single Season</option>
          <option value="range">Season Range</option>
        </select>
        {yearMode === 'single' && (
          <select
            value={yearSingle}
            onChange={e => setYearSingle(e.target.value)}
            className="bg-gray-800 text-gray-200 border border-gray-600 rounded-md px-3 py-1.5 text-sm"
          >
            {seasons.map(s => (
              <option key={s.year} value={s.year}>{s.year}</option>
            ))}
          </select>
        )}
        {yearMode === 'range' && (
          <>
            <select
              value={yearFrom}
              onChange={e => setYearFrom(e.target.value)}
              className="bg-gray-800 text-gray-200 border border-gray-600 rounded-md px-3 py-1.5 text-sm"
            >
              {seasons.slice().reverse().map(s => (
                <option key={s.year} value={s.year}>{s.year}</option>
              ))}
            </select>
            <span className="text-gray-400 text-sm">–</span>
            <select
              value={yearTo}
              onChange={e => setYearTo(e.target.value)}
              className="bg-gray-800 text-gray-200 border border-gray-600 rounded-md px-3 py-1.5 text-sm"
            >
              {seasons.map(s => (
                <option key={s.year} value={s.year}>{s.year}</option>
              ))}
            </select>
          </>
        )}
      </div>

      {/* Division summary, single card with two sides */}
      <div className="mb-8">
        <DivisionsSummaryCard
          divisions={divisions}
          expandedDivision={expandedDivision}
          onToggleExpand={div => setExpandedDivision(expandedDivision === div ? null : div)}
        />
      </div>

      {/* Interdivision H2H */}
      <h2 className="text-xl font-semibold text-white mb-4">Interdivision Head-to-Head</h2>
      <div className="flex flex-col gap-3 mb-8">
        {interdivision_h2h.length === 0 ? (
          <div className="rounded-xl border border-gray-700 bg-gray-900 py-8 text-center text-gray-500">
            No interdivision games in this range.
          </div>
        ) : (
          interdivision_h2h.map(m => (
            <InterdivisionCard key={`${m.division_a}-${m.division_b}`} m={m} />
          ))
        )}
      </div>

      {/* Division rosters, single card with two sides */}
      <h2 className="text-xl font-semibold text-white mb-1">Division Rosters</h2>
      <p className="text-xs text-gray-500 mb-4">Division membership has changed over the years — most recent first.</p>
      <RostersCard
        divisions={divisions}
        years={allYears}
        rostersByDivision={rostersByDivision}
        navigate={navigate}
      />
    </div>
  )
}
