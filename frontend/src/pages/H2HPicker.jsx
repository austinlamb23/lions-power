import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

export default function H2HPicker() {
  const navigate = useNavigate()
  const [owners, setOwners] = useState([])
  const [ownerA, setOwnerA] = useState('')
  const [ownerB, setOwnerB] = useState('')

  useEffect(() => {
    fetch('/api/almanac/owners')
      .then(r => r.json())
      .then(setOwners)
  }, [])

  function handleSubmit() {
    if (!ownerA || !ownerB || ownerA === ownerB) return
    navigate(`/owner/${encodeURIComponent(ownerA)}/h2h/${encodeURIComponent(ownerB)}`)
  }

  return (
    <div className="max-w-xl mx-auto">
      <button onClick={() => navigate(-1)} className="text-gray-400 hover:text-white text-sm mb-6 flex items-center gap-1">
        ← Back
      </button>

      <h1 className="text-3xl font-bold text-white mb-2" style={{ fontFamily: 'var(--heading)' }}>
        Head-to-Head
      </h1>
      <p className="text-gray-400 mb-8">
        Pick any two managers to see their all-time series, 2013–present.
      </p>

      <div className="rounded-xl border border-gray-700 bg-gray-900 p-6 flex flex-col gap-4">
        <div>
          <label className="block text-gray-400 text-sm mb-1.5">Manager A</label>
          <select
            value={ownerA}
            onChange={e => setOwnerA(e.target.value)}
            className="w-full bg-gray-800 text-gray-200 border border-gray-600 rounded-md px-3 py-2 text-sm"
          >
            <option value="">Select manager...</option>
            {owners.filter(o => o !== ownerB).map(o => <option key={o} value={o}>{o}</option>)}
          </select>
        </div>

        <div className="text-center text-gray-600 text-sm">vs</div>

        <div>
          <label className="block text-gray-400 text-sm mb-1.5">Manager B</label>
          <select
            value={ownerB}
            onChange={e => setOwnerB(e.target.value)}
            className="w-full bg-gray-800 text-gray-200 border border-gray-600 rounded-md px-3 py-2 text-sm"
          >
            <option value="">Select manager...</option>
            {owners.filter(o => o !== ownerA).map(o => <option key={o} value={o}>{o}</option>)}
          </select>
        </div>

        <button
          onClick={handleSubmit}
          disabled={!ownerA || !ownerB || ownerA === ownerB}
          className="mt-2 w-full bg-green-700 hover:bg-green-600 disabled:bg-gray-700 disabled:text-gray-500 text-white font-semibold py-2.5 rounded-md text-sm transition-colors"
        >
          Get Head-to-Head
        </button>
      </div>
    </div>
  )
}
