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

function MoveRow({ move }) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-gray-800 last:border-0">
      <div className="flex items-center gap-2">
        <span className={`text-xs font-semibold px-2 py-0.5 rounded ${move.type === 'WAIVER' ? 'bg-gray-700 text-gray-300' : 'bg-gray-800 text-gray-400 border border-gray-700'}`}>
          {move.type === 'WAIVER' ? 'Waiver' : 'Free Agent'}
        </span>
        <span className="text-gray-500 text-xs">Wk {move.week}</span>
        {move.added.length > 0 && (
          <span className="text-green-400 text-sm">+ {move.added.join(', ')}</span>
        )}
        {move.dropped.length > 0 && (
          <span className="text-red-400 text-sm">− {move.dropped.join(', ')}</span>
        )}
      </div>
      {move.bid_amount > 0 && (
        <span className="text-xs text-gray-500">${move.bid_amount}</span>
      )}
    </div>
  )
}

function TradeCard({ trade, navigate }) {
  return (
    <div className="rounded-xl border border-gray-700 bg-gray-900 p-4 my-2">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-semibold px-2 py-0.5 rounded bg-yellow-900/40 text-yellow-500 border border-yellow-800">
          Trade
        </span>
        <span className="text-gray-500 text-xs">Wk {trade.week}</span>
      </div>
      {trade.complete ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {trade.sides.map(side => (
            <div key={side.team_id} className="bg-gray-800/50 rounded-lg p-3">
              <button
                onClick={() => navigate(`/owner/${encodeURIComponent(side.owner_name)}`)}
                className="text-sm font-semibold text-white hover:text-green-400 hover:underline mb-1.5"
              >
                {side.owner_name}
              </button>
              {side.received.length > 0 && (
                <div className="text-green-400 text-sm">+ {side.received.join(', ')}</div>
              )}
              {side.gave_up.length > 0 && (
                <div className="text-red-400 text-sm">− {side.gave_up.join(', ')}</div>
              )}
            </div>
          ))}
        </div>
      ) : (
        <p className="text-sm text-gray-500 italic">
          A trade happened here, but ESPN doesn't retain the full player details for it.
        </p>
      )}
    </div>
  )
}

export default function Transactions() {
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
    fetch(`/api/almanac/owner/${encodeURIComponent(owner)}/transactions`)
      .then(r => r.json())
      .then(d => {
        setData(d)
        setLoading(false)
      })
  }, [owner])

  const { analytics } = data || {}

  return (
    <div className="max-w-4xl mx-auto">
      <button onClick={() => navigate(-1)} className="text-gray-400 hover:text-white text-sm mb-6 flex items-center gap-1">
        ← Back
      </button>

      <h1 className="text-3xl font-bold text-white mb-2" style={{ fontFamily: 'var(--heading)' }}>
        Transactions
      </h1>
      <p className="text-gray-400 mb-8">
        Every trade, waiver claim, and free-agent add a manager's franchise has made, 2019–present.
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
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 mb-10">
            <StatCard label="Total Moves" value={analytics.total_moves} />
            <StatCard label="Waiver Adds" value={analytics.waiver_adds} />
            <StatCard label="FA Adds" value={analytics.freeagent_adds} />
            <StatCard label="Trades Made" value={analytics.trades_made} />
            <StatCard
              label="Busiest Year"
              value={analytics.busiest_year ? analytics.busiest_year.year : '—'}
              sub={analytics.busiest_year ? `${analytics.busiest_year.count} moves` : null}
            />
          </div>

          <h2 className="text-xl font-semibold text-white mb-1">Move History</h2>
          <p className="text-xs text-gray-500 mb-4">Every trade, waiver claim, and free-agent add, most recent first.</p>
          <div className="flex flex-col gap-8">
            {data.moves_by_year.map(y => (
              <div key={y.year}>
                <h3 className="text-lg font-semibold text-white mb-2">{y.year}</h3>
                <div className="rounded-xl border border-gray-700 bg-gray-900 p-4">
                  {y.moves.map((m, i) =>
                    m.kind === 'trade'
                      ? <TradeCard key={i} trade={m} navigate={navigate} />
                      : <MoveRow key={i} move={m} />
                  )}
                </div>
              </div>
            ))}
          </div>

          <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-6 text-sm text-gray-500 leading-relaxed mt-8">
            <p className="text-gray-400 font-semibold mb-2">Note</p>
            <p>
              Transaction data only exists 2019 onward — ESPN's API has no record of trades/waivers/adds
              for earlier seasons. Full "who traded whom" detail is also only recoverable for a minority
              of historical trades; where it isn't available, the trade is still shown but without item
              details.
            </p>
          </div>
        </>
      )}
    </div>
  )
}
