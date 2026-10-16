import { useEffect, useState } from 'react'
import { useNavigate, useParams, Link } from 'react-router-dom'
import { loadAuth, parseError, FlaggedBanner } from '../components/OwnerLogin'
import Markdown from '../components/Markdown'
import ForumPostForm from '../components/ForumPostForm'

export default function ForumPost() {
  const { postId } = useParams()
  const navigate = useNavigate()
  const [auth] = useState(loadAuth)
  const [post, setPost] = useState(null)
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState(false)
  const [error, setError] = useState('')
  const [flagged, setFlagged] = useState('')

  const authHeaders = auth ? { Authorization: `Bearer ${auth.token}` } : {}

  function loadPost() {
    setLoading(true)
    fetch(`/api/forums/posts/${postId}`, { headers: authHeaders })
      .then(async r => {
        if (!r.ok) throw new Error(await parseError(r))
        return r.json()
      })
      .then(setPost)
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    loadPost()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [postId])

  function handleDelete() {
    if (!window.confirm('Delete this post? This can\'t be undone.')) return
    setFlagged('')
    fetch(`/api/forums/posts/${postId}`, { method: 'DELETE', headers: authHeaders })
      .then(async r => {
        if (r.status === 423) { setFlagged(await parseError(r)); throw new Error('') }
        if (!r.ok) throw new Error(await parseError(r))
        navigate('/forums')
      })
      .catch(err => { if (err.message) setError(err.message) })
  }

  if (loading) return <p className="text-gray-500 text-center py-12">Loading...</p>
  if (error && !post) return <p className="text-red-400 text-center py-12">{error}</p>
  if (!post) return null

  if (editing) {
    return (
      <div className="max-w-2xl mx-auto">
        <ForumPostForm
          mode="edit"
          initial={post}
          authHeaders={authHeaders}
          onCancel={() => setEditing(false)}
          onSaved={updated => {
            setPost(p => ({ ...p, ...updated }))
            setEditing(false)
          }}
        />
      </div>
    )
  }

  return (
    <div className="max-w-2xl mx-auto">
      <Link to="/forums" className="text-gray-500 hover:text-gray-300 text-sm mb-4 inline-block">
        ← Back to Forums
      </Link>

      {post.cover_image_path && (
        <img
          src={`/api/forums/images/${post.cover_image_path}`}
          alt=""
          className="w-full h-56 rounded-xl object-cover mb-6"
        />
      )}

      <h1 className="text-3xl font-bold text-white mb-2" style={{ fontFamily: 'var(--heading)' }}>
        {post.title}
      </h1>
      <p className="text-gray-600 text-sm mb-6">
        {post.submitted_by} · {new Date(post.created_at).toLocaleDateString()}
      </p>

      <FlaggedBanner message={flagged} />

      <div className="mb-6">
        <Markdown>{post.body_markdown}</Markdown>
      </div>

      {post.cta_url && post.cta_label && (
        <div className="mb-8">
          {post.cta_url.startsWith('/') ? (
            <Link
              to={post.cta_url}
              className="inline-block bg-green-700 hover:bg-green-600 text-white rounded-md px-5 py-2.5 text-sm font-semibold transition-colors"
            >
              {post.cta_label}
            </Link>
          ) : (
            <a
              href={post.cta_url}
              target="_blank"
              rel="noreferrer"
              className="inline-block bg-green-700 hover:bg-green-600 text-white rounded-md px-5 py-2.5 text-sm font-semibold transition-colors"
            >
              {post.cta_label}
            </a>
          )}
        </div>
      )}

      {error && <p className="text-red-400 text-sm mb-4">{error}</p>}

      {post.can_edit && (
        <div className="flex gap-3 pt-4 border-t border-gray-800">
          <button
            onClick={() => setEditing(true)}
            className="text-gray-400 hover:text-white text-sm underline"
          >
            Edit
          </button>
          <button
            onClick={handleDelete}
            className="text-red-500 hover:text-red-400 text-sm underline"
          >
            Delete
          </button>
        </div>
      )}
    </div>
  )
}
