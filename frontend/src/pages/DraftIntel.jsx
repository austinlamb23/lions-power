import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

function StatCard({ label, value, sub }) {
  return (
    <div className="bg-gray-800 rounded-xl p-4 text-center">
      <div className="text-2xl font-bold text-white">{value}</div>
      <div className="text-xs text-gray-400 mt-1 uppercase tracking-wide">{label}</div>
      {sub && <div className="text-xs text-gray-600 mt-1">{sub}</div>}
    </div>
  )
}

function BucketBars({ buckets }) {
  const max = 10
  return (
    <div className="flex items-end gap-6 h-40 px-2">
      {buckets.map(b => (
        <div key={b.label} className="flex-1 flex flex-col items-center justify-end h-full">
          <div className="text-sm font-semibold text-white mb-1">{b.avg_finish}</div>
          <div className="w-full flex items-end justify-center h-full">
            <div
              className="w-full max-w-[80px] bg-green-700 rounded-t"
              style={{ height: `${(b.avg_finish / max) * 100}%` }}
            />
          </div>
          <div className="text-xs text-gray-500 mt-2 text-center">{b.label}</div>
        </div>
      ))}
    </div>
  )
}

function FranchiseBar({ f, maxAbs }) {
  const pct = (Math.abs(f.delta) / maxAbs) * 50
  const isOver = f.delta < 0
  return (
    <div className="grid grid-cols-[120px_1fr] items-center gap-3 h-7">
      <div className="text-sm text-gray-400 text-right truncate">{f.owner_name}</div>
      <div className="relative h-full">
        <div className="absolute left-1/2 top-0 bottom-0 w-px bg-gray-600" />
        <div
          className={`absolute top-0.5 bottom-0.5 rounded ${isOver ? 'bg-green-700' : 'bg-red-800'}`}
          style={
            isOver
              ? { right: '50%', width: `${pct}%` }
              : { left: '50%', width: `${pct}%` }
          }
        />
        <div
          className="absolute top-1/2 -translate-y-1/2 text-xs font-semibold text-gray-300"
          style={
            isOver
              ? { right: `calc(50% + ${pct}% + 6px)` }
              : { left: `calc(50% + ${pct}% + 6px)` }
          }
        >
          {f.delta > 0 ? '+' : ''}{f.delta}
        </div>
      </div>
    </div>
  )
}

export default function DraftIntel() {
  const navigate = useNavigate()
  const [data, setData] = useState(null)

  useEffect(() => {
    fetch('/api/almanac/draft-intel')
      .then(r => r.json())
      .then(setData)
  }, [])

  if (!data) return <div className="text-gray-500 py-12 text-center">Loading...</div>

  const maxAbsDelta = Math.max(...data.franchises.map(f => Math.abs(f.delta)))

  return (
    <div className="max-w-3xl mx-auto">
      <button onClick={() => navigate(-1)} className="text-gray-400 hover:text-white text-sm mb-6 flex items-center gap-1">
        ← Back
      </button>

      <h1 className="text-3xl font-bold text-white mb-2" style={{ fontFamily: 'var(--heading)' }}>
        Draft Intel
      </h1>
      <p className="text-gray-400 mb-8">
        Does where you draft predict how you finish? 13 seasons of Lions Power 3 data, 2013–2025.
      </p>

      {/* Headline */}
      <div className="rounded-xl border border-gray-700 bg-gray-900 p-6 mb-8">
        <div className="grid grid-cols-1 max-w-xs mx-auto gap-3 mb-5">
          <StatCard label="Correlation, all years" value={data.correlations.all.pearson} sub={`n=${data.correlations.all.n}`} />
        </div>
        <p className="text-gray-300 leading-relaxed">
          <span className="text-white font-semibold">Where you draft doesn't predict how you finish.</span> Across
          {' '}{data.correlations.all.n} team-seasons, the correlation between draft position and final standing is
          essentially zero. Teams picking early (1-3) finished with an average standing of{' '}
          {data.buckets[0].avg_finish} — teams picking late (8-10) finished at {data.buckets[2].avg_finish}.
          A coin flip either way.
        </p>
      </div>

      {/* Pick-by-pick breakdown — front and center */}
      <h2 className="text-xl font-semibold text-white mb-1">Pick by pick, 2013–2025</h2>
      <p className="text-xs text-gray-500 mb-4">
        Every draft slot's track record: 13 seasons at each pick. Lower avg finish is better.
      </p>
      <div className="overflow-x-auto rounded-xl border border-gray-700 bg-gray-900 mb-8">
        <table className="w-full text-sm">
          <thead className="bg-gray-800 text-gray-400 uppercase text-xs tracking-wider">
            <tr>
              {['Pick', 'Avg Finish', 'Championships', 'Last Places'].map(h => (
                <th key={h} className="px-4 py-3 text-left">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800">
            {data.by_pick.map((p, i) => (
              <tr key={p.pick} className={i % 2 === 0 ? 'bg-gray-900' : 'bg-gray-950'}>
                <td className="px-4 py-3 text-white font-bold">#{p.pick}</td>
                <td className="px-4 py-3 text-gray-200">{p.avg_finish ?? '—'}</td>
                <td className="px-4 py-3">
                  {p.championships > 0
                    ? <span className="text-green-400 font-semibold">{p.championships}</span>
                    : <span className="text-gray-600">0</span>}
                </td>
                <td className="px-4 py-3">
                  {p.last_places > 0
                    ? <span className="text-red-400 font-semibold">{p.last_places}</span>
                    : <span className="text-gray-600">0</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Bucket chart */}
      <h2 className="text-xl font-semibold text-white mb-1">Average finish by draft slot</h2>
      <p className="text-xs text-gray-500 mb-4">Lower bar = better average finish (1 = champion, 10 = last).</p>
      <div className="rounded-xl border border-gray-700 bg-gray-900 p-6 mb-8">
        <BucketBars buckets={data.buckets} />
      </div>

      {/* Championships */}
      <h2 className="text-xl font-semibold text-white mb-1">The one place it does show up: championships</h2>
      <p className="text-xs text-gray-500 mb-4">
        Small sample (13 champs, one per year) — but a real, sensible pattern: good teams tend to stay good.
      </p>
      <div className="rounded-xl border border-gray-700 bg-gray-900 p-6 mb-8">
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-5">
          <StatCard label="Avg champ draft pos" value={data.championships.avg_draft_pos} sub={`vs ${data.championships.expected_avg} expected`} />
          {data.championships.tiers.map(t => (
            <StatCard key={t.label} label={t.label} value={`${t.count}/13`} sub={`vs ${t.expected_pct}% by chance`} />
          ))}
        </div>
        <p className="text-gray-300 leading-relaxed mb-4">
          Only <span className="text-white font-semibold">two champions in 13 years</span> came from the
          top-3 picks — meaning the worst teams almost never go worst-to-first. No single pick dominates:
          picks 4, 6, 7, and 8 are tied for the most titles at two apiece.
        </p>
        <div className="overflow-x-auto rounded-lg border border-gray-700">
          <table className="w-full text-sm">
            <thead className="bg-gray-800 text-gray-400 uppercase text-xs tracking-wider">
              <tr>
                {['Year', 'Champion', 'Draft Pick'].map(h => (
                  <th key={h} className="px-4 py-2 text-left">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800">
              {data.championships.list.map((c, i) => (
                <tr key={c.year} className={i % 2 === 0 ? 'bg-gray-900' : 'bg-gray-950'}>
                  <td className="px-4 py-2 text-gray-200 font-medium">{c.year}</td>
                  <td className="px-4 py-2 text-gray-200">{c.owner_name}</td>
                  <td className="px-4 py-2 text-green-400 font-semibold">#{c.draft_pos}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Franchise over/under performers */}
      <h2 className="text-xl font-semibold text-white mb-1">Who beats their draft slot?</h2>
      <p className="text-xs text-gray-500 mb-4">
        Avg final standing minus avg draft position. Green = finishes better than their slot suggests. Red = worse.
      </p>
      <div className="rounded-xl border border-gray-700 bg-gray-900 p-6 mb-8">
        <div className="flex flex-col gap-2">
          {data.franchises.map(f => (
            <FranchiseBar key={f.team_id} f={f} maxAbs={maxAbsDelta} />
          ))}
        </div>
      </div>

      {/* Caveats */}
      <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-6 text-sm text-gray-500 leading-relaxed">
        <p className="text-gray-400 font-semibold mb-2">Method &amp; caveats</p>
        <ul className="list-disc list-inside space-y-1.5">
          <li>Real draft records exist for every season, 2013–2025.</li>
          <li>"Final standing" uses the corrected ranking (wins desc., points-for desc. for
            non-playoff teams) — the raw stored standing disagreed with this in 48% of team-seasons
            checked.</li>
          <li>n=130 is small for correlation, and the championship read (n=13) especially so —
            directionally real, not something to bet heavily on.</li>
        </ul>
      </div>
    </div>
  )
}
