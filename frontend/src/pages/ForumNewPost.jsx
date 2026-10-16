import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AUTH_KEY, loadAuth, LoginForm } from '../components/OwnerLogin'
import ForumPostForm from '../components/ForumPostForm'

export default function ForumNewPost() {
  const navigate = useNavigate()
  const [owners, setOwners] = useState([])
  const [auth, setAuth] = useState(loadAuth)

  const authHeaders = auth ? { Authorization: `Bearer ${auth.token}` } : {}

  useEffect(() => {
    fetch('/api/punishments/owners').then(r => r.json()).then(setOwners)
  }, [])

  function handleLogout() {
    localStorage.removeItem(AUTH_KEY)
    setAuth(null)
  }

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-3xl font-bold text-white mb-2" style={{ fontFamily: 'var(--heading)' }}>
        Write a deep dive
      </h1>
      <p className="text-gray-400 text-sm mb-8">
        Long-form takes, breakdowns, and arguments — published under your name for the whole league to see.
      </p>

      {auth ? (
        <div className="flex items-center justify-between mb-4">
          <p className="text-gray-400 text-sm">
            Posting as <span className="text-gray-200 font-semibold">{auth.owner_name}</span>
          </p>
          <button onClick={handleLogout} className="text-gray-500 hover:text-gray-300 text-xs underline">
            Log out
          </button>
        </div>
      ) : null}

      {auth ? (
        <ForumPostForm
          mode="create"
          authHeaders={authHeaders}
          onSaved={post => navigate(`/forums/${post.id}`)}
        />
      ) : (
        <LoginForm owners={owners} onLoggedIn={setAuth} helpText="Log in to write a deep dive." />
      )}
    </div>
  )
}
