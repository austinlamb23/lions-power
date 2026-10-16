import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { AUTH_KEY, loadAuth, parseError, LoginForm } from '../components/OwnerLogin'

function EpisodeCard({ ep, canManage, onDelete }) {
  return (
    <div className="rounded-xl border border-gray-700 bg-gray-900 overflow-hidden">
      <div className="aspect-video bg-black">
        <iframe
          className="w-full h-full"
          src={`https://www.youtube.com/embed/${ep.youtube_id}`}
          title={ep.title}
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
          allowFullScreen
        />
      </div>
      <div className="p-4 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-gray-100 font-medium truncate">{ep.title}</p>
          <p className="text-gray-600 text-xs mt-0.5">
            {ep.year} · {ep.week === 0 ? 'Preseason' : `Week ${ep.week}`}
          </p>
        </div>
        {canManage && (
          <button
            onClick={() => onDelete(ep.id)}
            className="text-gray-600 hover:text-red-400 text-xs whitespace-nowrap"
          >
            Remove
          </button>
        )}
      </div>
    </div>
  )
}

function AddEpisodeForm({ authHeaders, defaultYear, onAdded }) {
  const [year, setYear] = useState(defaultYear || '')
  const [week, setWeek] = useState(0)
  const [url, setUrl] = useState('')
  const [title, setTitle] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (defaultYear && year === '') setYear(defaultYear)
  }, [defaultYear])

  function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setSubmitting(true)
    fetch('/api/pod-episodes', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders },
      body: JSON.stringify({ year: Number(year), week: Number(week), url, title: title.trim() || null }),
    })
      .then(async r => {
        if (!r.ok) throw new Error(await parseError(r))
        setUrl('')
        setTitle('')
        onAdded()
      })
      .catch(err => setError(err.message))
      .finally(() => setSubmitting(false))
  }

  return (
    <form onSubmit={handleSubmit} className="rounded-xl border border-gray-700 bg-gray-900 p-4">
      <p className="text-gray-400 text-sm mb-3">Add an episode</p>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-2">
        <div>
          <label className="block text-gray-500 text-xs mb-1">Year</label>
          <input
            type="number" value={year} onChange={e => setYear(e.target.value)}
            className="w-full bg-gray-800 text-gray-200 border border-gray-600 rounded-md px-2 py-1.5 text-sm"
          />
        </div>
        <div>
          <label className="block text-gray-500 text-xs mb-1">Week (0 = preseason)</label>
          <input
            type="number" value={week} onChange={e => setWeek(e.target.value)}
            className="w-full bg-gray-800 text-gray-200 border border-gray-600 rounded-md px-2 py-1.5 text-sm"
          />
        </div>
        <div className="col-span-2 sm:col-span-2">
          <label className="block text-gray-500 text-xs mb-1">YouTube URL</label>
          <input
            type="text" value={url} onChange={e => setUrl(e.target.value)}
            placeholder="https://www.youtube.com/watch?v=..."
            className="w-full bg-gray-800 text-gray-200 border border-gray-600 rounded-md px-2 py-1.5 text-sm"
          />
        </div>
      </div>
      <label className="block text-gray-500 text-xs mb-1">Title (optional — auto-fetched from YouTube if left blank)</label>
      <input
        type="text" value={title} onChange={e => setTitle(e.target.value)}
        className="w-full bg-gray-800 text-gray-200 border border-gray-600 rounded-md px-2 py-1.5 text-sm mb-3"
      />
      {error && <p className="text-red-400 text-sm mb-2">{error}</p>}
      <button
        type="submit"
        disabled={submitting || !url}
        className="bg-green-700 hover:bg-green-600 disabled:opacity-50 text-white rounded-md px-4 py-2 text-sm font-semibold transition-colors"
      >
        {submitting ? 'Adding...' : 'Add episode'}
      </button>
    </form>
  )
}

export default function Pod() {
  const [episodes, setEpisodes] = useState(null)
  const [auth, setAuth] = useState(loadAuth)
  const [crew, setCrew] = useState([])
  const [defaultYear, setDefaultYear] = useState(null)

  const authHeaders = auth ? { Authorization: `Bearer ${auth.token}` } : {}
  const canManage = auth && crew.includes(auth.owner_name)

  function loadEpisodes() {
    fetch('/api/pod-episodes').then(r => r.json()).then(d => setEpisodes(d.episodes))
  }

  useEffect(() => {
    loadEpisodes()
    fetch('/api/pod-grades/graders').then(r => r.json()).then(d => setCrew(d.graders))
    fetch('/api/power-rankings/current-week').then(r => r.json()).then(d => setDefaultYear(d.year))
  }, [])

  function handleLogout() {
    localStorage.removeItem(AUTH_KEY)
    setAuth(null)
  }

  function handleDelete(id) {
    fetch(`/api/pod-episodes/${id}`, { method: 'DELETE', headers: authHeaders })
      .then(r => { if (r.ok) loadEpisodes() })
  }

  return (
    <div className="max-w-3xl mx-auto">
      <h1 className="text-3xl font-bold text-white mb-2">The Pod</h1>
      <p className="text-gray-400 mb-6">Every episode of the league podcast, embedded from YouTube.</p>

      {episodes === null && <p className="text-gray-500 text-center py-16">Loading...</p>}

      {episodes && episodes.length === 0 && (
        <div className="rounded-xl border border-gray-700 bg-gray-900 py-16 text-center text-gray-500 mb-6">
          No episodes yet — check back soon.
        </div>
      )}

      {episodes && episodes.length > 0 && (
        <div className="space-y-4 mb-6">
          {episodes.map(ep => (
            <EpisodeCard key={ep.id} ep={ep} canManage={canManage} onDelete={handleDelete} />
          ))}
        </div>
      )}

      <Link to="/the-pod/room-grades" className="block text-gray-600 hover:text-gray-400 text-xs text-center mb-6">
        Room Grades (crew only)
      </Link>

      {auth ? (
        <div className="flex items-center justify-between mb-3">
          <p className="text-gray-500 text-xs">
            Logged in as <span className="text-gray-300 font-medium">{auth.owner_name}</span>
            {!canManage && <span className="text-gray-600"> (episode management is crew-only)</span>}
          </p>
          <button onClick={handleLogout} className="text-gray-500 hover:text-gray-300 text-xs underline">
            Log out
          </button>
        </div>
      ) : (
        <div className="mb-3">
          <p className="text-gray-600 text-xs text-center mb-2">Pod crew — log in to add or remove episodes.</p>
          <LoginForm owners={crew} onLoggedIn={setAuth} />
        </div>
      )}

      {canManage && (
        <AddEpisodeForm authHeaders={authHeaders} defaultYear={defaultYear} onAdded={loadEpisodes} />
      )}
    </div>
  )
}
