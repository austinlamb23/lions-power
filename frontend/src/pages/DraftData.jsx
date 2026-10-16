import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

function StatCard({ label, value, sub }) {
  return (
    <div className="bg-gray-800 rounded-xl p-4 text-center">
      <div className="text-2xl font-bold text-white">{value ?? '—'}</div>
      <div className="text-xs text-gray-400 mt-1 uppercase tracking-wide">{label}</div>
      {sub && <div className="text-xs text-gray-600 mt-1">{sub}</div>}
    </div>
  )
}

function Finish({ value }) {
  if (value == null) return <span className="text-gray-600">—</span>
  return <span className="text-gray-300">#{value}</span>
}

export default function DraftData() {
  const navigate = useNavigate()
  const [owners, setOwners] = useState([])
  const [owner, setOwner] = useState('')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    fetch('/api/almanac/owners')
      .then(r => r.json())
      .then(setOwners)
  }, [])

  useEffect(() => {
    if (!owner) {
      setData(null)
      return
    }
    setLoading(true)
    fetch(`/api/almanac/owner/${encodeURIComponent(owner)}/draft-history`)
      .then(r => r.json())
      .then(d => {
        setData(d)
        setLoading(false)
      })
  }, [owner])

  const { analytics } = data || {}

  return (
    <div className="max-w-5xl mx-auto">
      <button onClick={() => navigate(-1)} className="text-gray-400 hover:text-white text-sm mb-6 flex items-center gap-1">
        ← Back
      </button>

      <h1 className="text-3xl font-bold text-white mb-2" style={{ fontFamily: 'var(--heading)' }}>
        Draft Data
      </h1>
      <p className="text-gray-400 mb-1">
        Browse every pick a manager's franchise has ever made, 2013–present.
      </p>
      <p className="text-gray-500 text-sm mb-8">
        Looking for draft-position-vs-finish analysis instead?{' '}
        <button onClick={() => navigate('/draft-intel')} className="text-green-400 hover:underline">
          See Draft Intel →
        </button>
      </p>

      <div className="mb-8">
        <label className="block text-gray-400 text-sm mb-1.5">Manager</label>
        <select
          value={owner}
          onChange={e => setOwner(e.target.value)}
          className="w-full sm:w-80 bg-gray-800 text-gray-200 border border-gray-600 rounded-md px-3 py-2 text-sm"
        >
          <option value="">Select manager...</option>
          {owners.map(o => <option key={o} value={o}>{o}</option>)}
        </select>
      </div>

      {loading && <div className="text-gray-500 py-12 text-center">Loading...</div>}

      {data && !loading && (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
            <StatCard label="Years Drafted" value={analytics.years_drafted} />
            <StatCard label="Total Picks" value={analytics.total_picks} />
            <StatCard label="Keeper Picks" value={analytics.keeper_count} />
            <StatCard
              label="Favorite Position"
              value={analytics.favorite_position.position ?? '—'}
              sub={analytics.favorite_position.position ? `${analytics.favorite_position.count} picks` : null}
            />
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-10">
            <StatCard
              label="Best Draft Slot"
              value={analytics.best_slot ? `#${analytics.best_slot.round_pick}` : '—'}
              sub={analytics.best_slot ? `${analytics.best_slot.year}` : null}
            />
            <StatCard
              label="Worst Draft Slot"
              value={analytics.worst_slot ? `#${analytics.worst_slot.round_pick}` : '—'}
              sub={analytics.worst_slot ? `${analytics.worst_slot.year}` : null}
            />
            <StatCard
              label="Best Finish Drafted"
              value={analytics.best_finish ? `${analytics.best_finish.position}${analytics.best_finish.position_finish}` : '—'}
              sub={analytics.best_finish ? `${analytics.best_finish.player_name}, ${analytics.best_finish.year}` : null}
            />
          </div>

          <h2 className="text-xl font-semibold text-white mb-4">First-Round Picks</h2>
          <div className="overflow-x-auto rounded-xl border border-gray-700 mb-10">
            <table className="w-full text-sm">
              <thead className="bg-gray-800 text-gray-400 uppercase text-xs tracking-wider">
                <tr>
                  {['Year', 'Pick', 'Player', 'Pos', 'Team', 'Points', 'Finish'].map(h => (
                    <th key={h} className="px-4 py-3 text-left">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                {analytics.first_round_picks.map((p, i) => (
                  <tr key={p.year} className={i % 2 === 0 ? 'bg-gray-900' : 'bg-gray-950'}>
                    <td className="px-4 py-3 text-gray-200 font-medium">{p.year}</td>
                    <td className="px-4 py-3 text-green-400 font-semibold">#{p.round_pick}</td>
                    <td className="px-4 py-3 text-gray-200">{p.player_name}</td>
                    <td className="px-4 py-3 text-gray-400">{p.position ?? '—'}</td>
                    <td className="px-4 py-3 text-gray-400">{p.pro_team ?? '—'}</td>
                    <td className="px-4 py-3 text-gray-300">{p.season_points ?? '—'}</td>
                    <td className="px-4 py-3"><Finish value={p.position_finish} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <h2 className="text-xl font-semibold text-white mb-4">Keeper Picks</h2>
          {analytics.keeper_count === 0 ? (
            <div className="rounded-xl border border-gray-700 bg-gray-900 py-8 text-center text-gray-500 mb-10">
              No keeper picks on record.
            </div>
          ) : (
            <div className="overflow-x-auto rounded-xl border border-gray-700 mb-10">
              <table className="w-full text-sm">
                <thead className="bg-gray-800 text-gray-400 uppercase text-xs tracking-wider">
                  <tr>
                    {['Year', 'Round', 'Pick', 'Player', 'Pos', 'Team', 'Points', 'Finish'].map(h => (
                      <th key={h} className="px-4 py-3 text-left">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800">
                  {analytics.keeper_picks.map((p, i) => (
                    <tr key={`${p.year}-${p.overall_pick}`} className={i % 2 === 0 ? 'bg-gray-900' : 'bg-gray-950'}>
                      <td className="px-4 py-3 text-gray-200 font-medium">{p.year}</td>
                      <td className="px-4 py-3 text-gray-300">{p.round_num}</td>
                      <td className="px-4 py-3 text-gray-300">#{p.round_pick}</td>
                      <td className="px-4 py-3 text-gray-200">{p.player_name}</td>
                      <td className="px-4 py-3 text-gray-400">{p.position ?? '—'}</td>
                      <td className="px-4 py-3 text-gray-400">{p.pro_team ?? '—'}</td>
                      <td className="px-4 py-3 text-gray-300">{p.season_points ?? '—'}</td>
                      <td className="px-4 py-3"><Finish value={p.position_finish} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <h2 className="text-xl font-semibold text-white mb-1">Full Draft Archive</h2>
          <p className="text-xs text-gray-500 mb-4">Every pick, every year, most recent first.</p>
          <div className="flex flex-col gap-8 mb-8">
            {data.picks_by_year.map(y => (
              <div key={y.year}>
                <h3 className="text-lg font-semibold text-white mb-2">
                  {y.year} <span className="text-gray-500 font-normal">— {y.team_name}</span>
                </h3>
                <div className="overflow-x-auto rounded-xl border border-gray-700">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-800 text-gray-400 uppercase text-xs tracking-wider">
                      <tr>
                        {['Round', 'Pick', 'Overall', 'Player', 'Pos', 'Team', 'Points', 'Finish', ''].map(h => (
                          <th key={h} className="px-4 py-2 text-left">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-800">
                      {y.picks.map((p, i) => (
                        <tr key={p.overall_pick} className={i % 2 === 0 ? 'bg-gray-900' : 'bg-gray-950'}>
                          <td className="px-4 py-2 text-gray-300">{p.round_num}</td>
                          <td className="px-4 py-2 text-gray-300">#{p.round_pick}</td>
                          <td className="px-4 py-2 text-gray-500 text-xs">{p.overall_pick}</td>
                          <td className="px-4 py-2 text-gray-200">{p.player_name}</td>
                          <td className="px-4 py-2 text-gray-400">{p.position ?? '—'}</td>
                          <td className="px-4 py-2 text-gray-400">{p.pro_team ?? '—'}</td>
                          <td className="px-4 py-2 text-gray-300">{p.season_points ?? '—'}</td>
                          <td className="px-4 py-2"><Finish value={p.position_finish} /></td>
                          <td className="px-4 py-2">
                            {p.keeper ? <span className="text-xs text-yellow-500">Keeper</span> : null}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ))}
          </div>

          <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-6 text-sm text-gray-500 leading-relaxed">
            <p className="text-gray-400 font-semibold mb-2">Note</p>
            <p>
              "Finish" is that player's rank among every NFL player at their position that season
              (e.g. RB1 = the highest-scoring running back in the league that year), not just among
              players drafted in this league. It's only available for 2019 onward — ESPN's historical
              positional-rank data isn't reliably available before then, so it shows as "—" for 2013-2018 picks.
            </p>
          </div>
        </>
      )}
    </div>
  )
}
