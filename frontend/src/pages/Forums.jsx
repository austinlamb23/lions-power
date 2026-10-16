import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

function PostCard({ post }) {
  return (
    <Link
      to={`/forums/${post.id}`}
      className="block rounded-xl border border-gray-700 bg-gray-900 p-5 hover:border-green-700 transition-colors"
    >
      <div className="flex gap-4">
        {post.cover_image_path && (
          <img
            src={`/api/forums/images/${post.cover_image_path}`}
            alt=""
            className="w-20 h-20 rounded-lg object-cover shrink-0"
          />
        )}
        <div className="min-w-0">
          <h2 className="text-lg font-bold text-white mb-1 truncate">{post.title}</h2>
          <p className="text-gray-600 text-xs mb-2">
            {post.submitted_by} · {new Date(post.created_at).toLocaleDateString()}
          </p>
          <p className="text-gray-400 text-sm line-clamp-2">{post.excerpt}</p>
        </div>
      </div>
    </Link>
  )
}

export default function Forums() {
  const [posts, setPosts] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch('/api/forums/posts')
      .then(r => r.json())
      .then(data => setPosts(data.posts))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="max-w-2xl mx-auto">
      <div className="flex items-center justify-between mb-2">
        <h1 className="text-3xl font-bold text-white" style={{ fontFamily: 'var(--heading)' }}>
          Forums
        </h1>
        <Link
          to="/forums/new"
          className="bg-green-700 hover:bg-green-600 text-white rounded-md px-4 py-2 text-sm font-semibold whitespace-nowrap transition-colors"
        >
          Write a deep dive
        </Link>
      </div>
      <p className="text-gray-400 text-sm mb-8">
        Long-form breakdowns, arguments, and deep dives from anyone in the league.
      </p>

      {loading && <p className="text-gray-500 text-center py-12">Loading...</p>}

      {!loading && posts.length === 0 && (
        <p className="text-gray-500 text-center py-12">No posts yet — be the first to write one.</p>
      )}

      <div className="flex flex-col gap-4">
        {posts.map(post => <PostCard key={post.id} post={post} />)}
      </div>
    </div>
  )
}
