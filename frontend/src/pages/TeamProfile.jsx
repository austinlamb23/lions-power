import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'

function StatCard({ label, value, asterisk }) {
  return (
    <div className="bg-gray-800 rounded-xl p-4 text-center">
      <div className="text-2xl font-bold text-white">
        {value ?? '—'}{asterisk && <span className="text-gray-500">*</span>}
      </div>
      <div className="text-xs text-gray-400 mt-1 uppercase tracking-wide">{label}</div>
    </div>
  )
}

export default function TeamProfile() {
  const { teamId } = useParams()
  const navigate = useNavigate()
  const [profile, setProfile] = useState(null)
  const [h2h, setH2h] = useState([])

  useEffect(() => {
    fetch(`/api/almanac/team/${teamId}`)
      .then(r => r.json())
      .then(setProfile)
    fetch(`/api/almanac/team/${teamId}/h2h`)
      .then(r => r.json())
      .then(setH2h)
  }, [teamId])

  if (!profile) return <div className="text-gray-500 py-12 text-center">Loading...</div>

  const { career, seasons, current_manager } = profile
  const totalW = career.reg_wins + career.playoff_wins
  const totalL = career.reg_losses + career.playoff_losses
  const winPct = ((totalW / (totalW + totalL + career.reg_ties)) * 100).toFixed(1)

  // Collect unique managers in chronological order
  const managers = [...new Set(seasons.slice().reverse().map(s => s.owner_name))]

  return (
    <div>
      <button onClick={() => navigate(-1)} className="text-gray-400 hover:text-white text-sm mb-6 flex items-center gap-1">
        ← Back
      </button>

      <h1 className="text-3xl font-bold text-white mb-1">Team {profile.team_id} Franchise</h1>
      <p className="text-gray-400 mb-1">Current manager: <span className="text-green-400">{current_manager}</span></p>
      {managers.length > 1 && (
        <p className="text-gray-500 text-sm mb-8">
          All managers: {managers.join(' → ')}
        </p>
      )}
      {managers.length === 1 && <div className="mb-8" />}

      <div className="mb-10">
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3 mb-2">
          <StatCard label="Championships" value={career.championships} asterisk={career.legacy_championships > 0} />
          <StatCard label="Finals Appearances" value={career.podium_finishes} />
          <StatCard label="Total Wins" value={totalW} />
          <StatCard label="Total Losses" value={totalL} />
          <StatCard label="Win %" value={`${winPct}%`} />
          <StatCard label="Points Scored" value={career.total_points?.toLocaleString()} />
        </div>
        {career.legacy_championships > 0 && (
          <p className="text-xs text-gray-600">
            * Includes {career.legacy_championships} pre-history championship{career.legacy_championships > 1 ? 's' : ''} (2011/2012) — honored based on league legend and oral history only, not statistically verified like 2013+.
          </p>
        )}
      </div>

      <h2 className="text-xl font-semibold text-white mb-4">Year by Year</h2>
      <div className="overflow-x-auto rounded-xl border border-gray-700">
        <table className="w-full text-sm">
          <thead className="bg-gray-800 text-gray-400 uppercase text-xs tracking-wider">
            <tr>
              {['Year', 'Manager', 'Team Name', 'W', 'L', 'T', 'Playoff W', 'Playoff L', 'Pts For', 'Finish'].map(h => (
                <th key={h} className="px-4 py-3 text-left">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800">
            {seasons.map((s, i) => (
              <tr key={s.year} className={i % 2 === 0 ? 'bg-gray-900' : 'bg-gray-950'}>
                <td className="px-4 py-3 text-gray-200 font-medium">{s.year}</td>
                <td className="px-4 py-3">
                  <button
                    onClick={() => navigate(`/owner/${encodeURIComponent(s.owner_name)}`)}
                    className="text-green-400 hover:underline"
                  >
                    {s.owner_name}
                  </button>
                </td>
                <td className="px-4 py-3 text-gray-300">{s.team_name}</td>
                <td className="px-4 py-3 text-gray-200">{s.wins}</td>
                <td className="px-4 py-3 text-gray-200">{s.losses}</td>
                <td className="px-4 py-3 text-gray-200">{s.ties}</td>
                <td className="px-4 py-3 text-gray-200">{s.playoff_wins ?? '—'}</td>
                <td className="px-4 py-3 text-gray-200">{s.playoff_losses ?? '—'}</td>
                <td className="px-4 py-3 text-gray-200">{s.points_for?.toLocaleString() ?? '—'}</td>
                <td className="px-4 py-3">
                  <span className={`font-bold ${s.final_standing === 1 ? 'text-yellow-400' : s.final_standing <= 3 ? 'text-green-400' : 'text-gray-400'}`}>
                    #{s.final_standing}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h2 className="text-xl font-semibold text-white mb-1 mt-10">Head-to-Head Records</h2>
      <p className="text-xs text-gray-500 mb-4">2013–present, plus any unverified pre-2013 legacy record*</p>
      <div className="overflow-x-auto rounded-xl border border-gray-700">
        <table className="w-full text-sm">
          <thead className="bg-gray-800 text-gray-400 uppercase text-xs tracking-wider">
            <tr>
              {['Opponent', 'W', 'L', 'T', 'Win%', 'Avg Pts For', 'Avg Pts Against'].map(h => (
                <th key={h} className="px-4 py-3 text-left">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800">
            {h2h.map((row, i) => {
              const pct = row.wins + row.losses > 0
                ? ((row.wins / (row.wins + row.losses + row.ties)) * 100).toFixed(1) + '%'
                : '—'
              return (
                <tr
                  key={row.opp_team_id}
                  onClick={() => navigate(`/team/${teamId}/h2h/${row.opp_team_id}`)}
                  className={`cursor-pointer hover:bg-gray-800 transition-colors ${i % 2 === 0 ? 'bg-gray-900' : 'bg-gray-950'}`}
                >
                  <td className="px-4 py-3 text-green-400 hover:underline">
                    {row.opponent}{row.has_legacy_h2h && <span className="text-gray-500">*</span>}
                  </td>
                  <td className="px-4 py-3 text-gray-200">{row.wins}</td>
                  <td className="px-4 py-3 text-gray-200">{row.losses}</td>
                  <td className="px-4 py-3 text-gray-200">{row.ties}</td>
                  <td className="px-4 py-3 text-gray-200">{pct}</td>
                  <td className="px-4 py-3 text-gray-200">{row.avg_pts_for ?? '—'}</td>
                  <td className="px-4 py-3 text-gray-200">{row.avg_pts_against ?? '—'}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      {h2h.some(row => row.has_legacy_h2h) && (
        <p className="text-xs text-gray-600 mt-2">
          * Includes a pre-2013 head-to-head record honored based on league legend and oral history only — no game-by-game data exists for those meetings.
        </p>
      )}
    </div>
  )
}
