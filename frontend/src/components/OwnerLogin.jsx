import { useState } from 'react'

export const AUTH_KEY = 'lp3_owner_auth'

export function loadAuth() {
  try {
    const raw = localStorage.getItem(AUTH_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

export async function parseError(res) {
  try {
    const body = await res.json()
    return body.detail || 'Something went wrong'
  } catch {
    return 'Something went wrong'
  }
}

export function FlaggedBanner({ message }) {
  if (!message) return null
  return (
    <div className="rounded-lg border-2 border-red-500 bg-red-950/70 px-4 py-3 mb-3 text-center">
      <p className="text-red-300 font-bold text-lg tracking-wide">🚨 {message} 🚨</p>
    </div>
  )
}

export function LoginForm({ owners, onLoggedIn, helpText }) {
  const [ownerName, setOwnerName] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  function handleSubmit(e) {
    e.preventDefault()
    if (!ownerName || !password) return
    setSubmitting(true)
    setError('')
    fetch('/api/punishments/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ owner_name: ownerName, password }),
    })
      .then(async r => {
        if (!r.ok) throw new Error(await parseError(r))
        return r.json()
      })
      .then(auth => {
        localStorage.setItem(AUTH_KEY, JSON.stringify(auth))
        onLoggedIn(auth)
      })
      .catch(err => setError(err.message))
      .finally(() => setSubmitting(false))
  }

  return (
    <form onSubmit={handleSubmit} className="rounded-xl border border-gray-700 bg-gray-900 p-6 max-w-sm mx-auto">
      <p className="text-gray-400 text-sm mb-4">
        {helpText || "First time logging in as your name sets your password — remember it, there's no reset yet."}
      </p>

      <label className="block text-gray-400 text-sm mb-1.5">Your name</label>
      <select
        value={ownerName}
        onChange={e => setOwnerName(e.target.value)}
        className="w-full bg-gray-800 text-gray-200 border border-gray-600 rounded-md px-3 py-2 text-sm mb-4"
      >
        <option value="">Select your name</option>
        {owners.map(o => <option key={o} value={o}>{o}</option>)}
      </select>

      <label className="block text-gray-400 text-sm mb-1.5">Password</label>
      <input
        type="password"
        value={password}
        onChange={e => setPassword(e.target.value)}
        className="w-full bg-gray-800 text-gray-200 border border-gray-600 rounded-md px-3 py-2 text-sm mb-4"
        placeholder="At least 4 characters"
      />

      {error && <p className="text-red-400 text-sm mb-4">{error}</p>}

      <button
        type="submit"
        disabled={!ownerName || !password || submitting}
        className="w-full bg-green-700 hover:bg-green-600 disabled:opacity-50 disabled:hover:bg-green-700 text-white rounded-md px-4 py-2 text-sm font-semibold transition-colors"
      >
        {submitting ? 'Logging in...' : 'Log in'}
      </button>
    </form>
  )
}
