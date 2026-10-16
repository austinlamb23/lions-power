import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

export default function HallOfFame() {
  const navigate = useNavigate()
  const [champions, setChampions] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch('/api/almanac/hall-of-fame')
      .then(r => r.json())
      .then(data => { setChampions(data); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  return (
    <div>
      <h1 className="text-3xl font-bold text-white mb-2">Hall of Fame</h1>
      <p className="text-gray-400 mb-8">Every champion in Lions Power 3 history, most recent first.</p>

      {loading ? (
        <p className="text-center py-16 text-gray-500">Loading...</p>
      ) : champions.length === 0 ? (
        <div className="rounded-xl border border-gray-700 bg-gray-900 py-16 text-center text-gray-500">
          No champions on record yet.
        </div>
      ) : (
        <div className="relative">
          <div className="absolute left-6 top-2 bottom-2 w-px bg-gray-700 hidden sm:block" />
          <div className="space-y-4">
            {champions.map(c => (
              <div key={c.year} className="relative sm:pl-16">
                <div className={`hidden sm:flex absolute left-0 top-1/2 -translate-y-1/2 w-12 h-12 rounded-full bg-gray-900 border-2 items-center justify-center text-xl ${c.verified ? 'border-green-700' : 'border-gray-600 border-dashed'}`}>
                  🏆
                </div>
                <div className={`rounded-xl border bg-gray-900 px-6 py-5 flex flex-col sm:flex-row items-center sm:items-center justify-between gap-4 ${c.verified ? 'border-gray-700' : 'border-gray-700 border-dashed'}`}>
                  <div className="text-center sm:text-left">
                    <div className="flex items-center justify-center sm:justify-start gap-2">
                      <span className="sm:hidden text-2xl">🏆</span>
                      <span className="text-2xl font-bold text-green-400" style={{ fontFamily: 'var(--heading)' }}>
                        {c.year}{!c.verified && <span className="text-gray-500">*</span>}
                      </span>
                    </div>
                    <button
                      onClick={() => navigate(`/owner/${encodeURIComponent(c.owner_name)}`)}
                      className="text-lg text-white hover:text-green-400 hover:underline font-medium transition-colors"
                    >
                      {c.owner_name}
                    </button>
                    {c.team_name && <p className="text-sm text-gray-500">{c.team_name}</p>}
                  </div>
                  {c.verified ? (
                    <div className="text-center sm:text-right text-sm text-gray-400">
                      <p>
                        {c.wins}-{c.losses}{c.ties ? `-${c.ties}` : ''} · {c.points_for?.toLocaleString()} pts
                      </p>
                      {(c.playoff_wins || c.playoff_losses) ? (
                        <p className="text-gray-500">Playoffs: {c.playoff_wins}-{c.playoff_losses}</p>
                      ) : null}
                    </div>
                  ) : (
                    <p className="text-center sm:text-right text-xs text-gray-500 italic sm:max-w-xs">
                      * {c.note}
                    </p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <p className="mt-8 text-xs text-gray-600">Accolades coming soon.</p>
    </div>
  )
}
