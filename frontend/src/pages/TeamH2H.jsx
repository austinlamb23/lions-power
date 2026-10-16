import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'

function StatCard({ label, value }) {
  return (
    <div className="bg-gray-800 rounded-xl p-4 text-center">
      <div className="text-2xl font-bold text-white">{value ?? '—'}</div>
      <div className="text-xs text-gray-400 mt-1 uppercase tracking-wide">{label}</div>
    </div>
  )
}

export default function TeamH2H() {
  const { teamId, opponentId } = useParams()
  const navigate = useNavigate()
  const [data, setData] = useState(null)

  useEffect(() => {
    setData(null)
    fetch(`/api/almanac/team/${teamId}/h2h/${opponentId}`)
      .then(r => r.json())
      .then(setData)
  }, [teamId, opponentId])

  if (!data) return <div className="text-gray-500 py-12 text-center">Loading...</div>

  const { me, opponent, games, legacy } = data
  const realWins = games.filter(g => g.my_score > g.opp_score).length
  const realLosses = games.filter(g => g.my_score < g.opp_score).length
  const realTies = games.filter(g => g.my_score === g.opp_score).length
  const avgFor = games.length ? (games.reduce((s, g) => s + g.my_score, 0) / games.length).toFixed(1) : '—'
  const avgAgainst = games.length ? (games.reduce((s, g) => s + g.opp_score, 0) / games.length).toFixed(1) : '—'

  const wins = realWins + (legacy?.wins ?? 0)
  const losses = realLosses + (legacy?.losses ?? 0)
  const ties = realTies + (legacy?.ties ?? 0)
  const totalGames = games.length + (legacy ? legacy.wins + legacy.losses + legacy.ties : 0)
  const winPct = totalGames ? ((wins / totalGames) * 100).toFixed(1) + '%' : '—'

  return (
    <div>
      <button onClick={() => navigate(-1)} className="text-gray-400 hover:text-white text-sm mb-6 flex items-center gap-1">
        ← Back
      </button>

      <h1 className="text-3xl font-bold text-white mb-1" style={{ fontFamily: 'var(--heading)' }}>
        <button onClick={() => navigate(`/team/${teamId}`)} className="hover:text-green-400 hover:underline">
          Team {teamId}
        </button>
        <span className="text-gray-500 mx-2">vs</span>
        <button onClick={() => navigate(`/team/${opponentId}`)} className="hover:text-green-400 hover:underline">
          Team {opponentId}
        </button>
      </h1>
      <p className="text-gray-400 mb-8">
        {me.owner_name} vs {opponent.owner_name} · all-time series, 2013–present, regular season and real playoff games only
        {legacy && ' — plus an unverified pre-2013 record'}
      </p>

      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 mb-2">
        <StatCard label="Record" value={`${wins}-${losses}${ties ? `-${ties}` : ''}`} />
        <StatCard label="Win %" value={winPct} />
        <StatCard label="Games" value={totalGames} />
        <StatCard label="Avg Pts For" value={avgFor} />
        <StatCard label="Avg Pts Against" value={avgAgainst} />
      </div>
      {legacy && (
        <p className="text-xs text-gray-600 mb-8">
          * Record includes a {legacy.wins}-{legacy.losses}{legacy.ties ? `-${legacy.ties}` : ''} pre-2013 head-to-head honored based on league legend and oral history only — no game-by-game data exists for those meetings, so they aren't shown in the log below.
        </p>
      )}
      {!legacy && <div className="mb-8" />}

      <h2 className="text-xl font-semibold text-white mb-4">Game Log (2013–present)</h2>
      {games.length === 0 ? (
        <div className="rounded-xl border border-gray-700 bg-gray-900 py-16 text-center text-gray-500">
          No recorded meetings between these two franchises (2013–present).
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-gray-700">
          <table className="w-full text-sm">
            <thead className="bg-gray-800 text-gray-400 uppercase text-xs tracking-wider">
              <tr>
                {['Year', 'Week', me.owner_name, opponent.owner_name, 'Result'].map(h => (
                  <th key={h} className="px-4 py-3 text-left">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800">
              {games.map((g, i) => {
                const result = g.my_score > g.opp_score ? 'W' : g.my_score < g.opp_score ? 'L' : 'T'
                const resultColor = result === 'W' ? 'text-green-400' : result === 'L' ? 'text-red-400' : 'text-gray-400'
                return (
                  <tr key={`${g.year}-${g.week}`} className={i % 2 === 0 ? 'bg-gray-900' : 'bg-gray-950'}>
                    <td className="px-4 py-3 text-gray-200 font-medium">{g.year}</td>
                    <td className="px-4 py-3 text-gray-300">
                      Wk {g.week}
                      {g.is_playoff ? <span className="ml-2 text-xs text-yellow-500">Playoffs</span> : null}
                    </td>
                    <td className="px-4 py-3">
                      <div className="text-gray-200 font-semibold">{g.my_score}</div>
                      <div className="text-xs text-gray-500">{g.my_team_name}</div>
                    </td>
                    <td className="px-4 py-3">
                      <div className="text-gray-200 font-semibold">{g.opp_score}</div>
                      <div className="text-xs text-gray-500">{g.opp_team_name}</div>
                    </td>
                    <td className={`px-4 py-3 font-bold ${resultColor}`}>{result}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
