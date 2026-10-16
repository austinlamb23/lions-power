import { useState } from 'react'
import { parseError, FlaggedBanner } from './OwnerLogin'
import Markdown from './Markdown'

export default function ForumPostForm({ mode, initial, authHeaders, onSaved, onCancel }) {
  const [title, setTitle] = useState(initial?.title || '')
  const [body, setBody] = useState(initial?.body_markdown || '')
  const [excerpt, setExcerpt] = useState(initial?.excerpt || '')
  const [coverImagePath, setCoverImagePath] = useState(initial?.cover_image_path || null)
  const [ctaUrl, setCtaUrl] = useState(initial?.cta_url || '')
  const [ctaLabel, setCtaLabel] = useState(initial?.cta_label || '')
  const [tab, setTab] = useState('write')
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')
  const [flagged, setFlagged] = useState('')
  const [submitting, setSubmitting] = useState(false)

  function handleImageUpload(file) {
    setUploading(true)
    const formData = new FormData()
    formData.append('file', file)
    fetch('/api/forums/images', { method: 'POST', headers: authHeaders, body: formData })
      .then(async r => {
        if (r.status === 423) { setFlagged(await parseError(r)); throw new Error('') }
        if (!r.ok) throw new Error(await parseError(r))
        return r.json()
      })
      .then(data => setCoverImagePath(data.image_path))
      .catch(err => { if (err.message) setError(err.message) })
      .finally(() => setUploading(false))
  }

  function handleSubmit(e) {
    e.preventDefault()
    if (!title.trim() || !body.trim()) return
    setSubmitting(true)
    setError('')
    setFlagged('')

    const payload = {
      title: title.trim(),
      body_markdown: body,
      excerpt: excerpt.trim() || null,
      cover_image_path: coverImagePath,
      cta_url: ctaUrl.trim() || null,
      cta_label: ctaLabel.trim() || null,
    }

    const url = mode === 'edit' ? `/api/forums/posts/${initial.id}` : '/api/forums/posts'
    const method = mode === 'edit' ? 'PUT' : 'POST'

    fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json', ...authHeaders },
      body: JSON.stringify(payload),
    })
      .then(async r => {
        if (r.status === 423) { setFlagged(await parseError(r)); throw new Error('') }
        if (!r.ok) throw new Error(await parseError(r))
        return r.json()
      })
      .then(data => onSaved(mode === 'edit' ? { ...initial, ...payload } : { id: data.id, ...payload }))
      .catch(err => { if (err.message) setError(err.message) })
      .finally(() => setSubmitting(false))
  }

  const tabBase = 'px-3 py-1.5 text-sm font-medium rounded-md transition-colors'
  const tabActive = `${tabBase} bg-green-700 text-white`
  const tabInactive = `${tabBase} text-gray-400 hover:text-white hover:bg-gray-700`

  return (
    <form onSubmit={handleSubmit} className="rounded-xl border border-gray-700 bg-gray-900 p-6">
      <FlaggedBanner message={flagged} />

      <label className="block text-gray-400 text-sm mb-1.5">Title</label>
      <input
        type="text"
        value={title}
        onChange={e => setTitle(e.target.value)}
        placeholder="e.g. The Best Draft in League History"
        className="w-full bg-gray-800 text-gray-200 border border-gray-600 rounded-md px-3 py-2 text-sm mb-4"
      />

      <div className="flex items-center justify-between mb-1.5">
        <label className="block text-gray-400 text-sm">Body (Markdown supported)</label>
        <div className="flex gap-1">
          <button type="button" className={tab === 'write' ? tabActive : tabInactive} onClick={() => setTab('write')}>
            Write
          </button>
          <button type="button" className={tab === 'preview' ? tabActive : tabInactive} onClick={() => setTab('preview')}>
            Preview
          </button>
        </div>
      </div>

      {tab === 'write' ? (
        <textarea
          value={body}
          onChange={e => setBody(e.target.value)}
          rows={16}
          placeholder="Write your deep dive here — headers, bold, lists, and tables are all supported."
          className="w-full bg-gray-800 text-gray-200 border border-gray-600 rounded-md px-3 py-2 text-sm font-mono mb-4"
        />
      ) : (
        <div className="border border-gray-700 rounded-md px-4 py-2 mb-4 bg-gray-950/50 min-h-[16rem]">
          {body.trim() ? <Markdown>{body}</Markdown> : <p className="text-gray-600 text-sm">Nothing to preview yet.</p>}
        </div>
      )}

      <label className="block text-gray-400 text-sm mb-1.5">Excerpt (optional)</label>
      <input
        type="text"
        value={excerpt}
        onChange={e => setExcerpt(e.target.value.slice(0, 500))}
        placeholder="Shown on the forums list page — auto-generated from the body if left blank"
        className="w-full bg-gray-800 text-gray-200 border border-gray-600 rounded-md px-3 py-2 text-sm mb-4"
      />

      <label className="block text-gray-400 text-sm mb-1.5">Cover image (optional)</label>
      <div className="flex items-center gap-3 mb-4">
        <input
          type="file"
          accept="image/jpeg,image/png,image/gif,image/webp"
          onChange={e => e.target.files[0] && handleImageUpload(e.target.files[0])}
          className="text-gray-400 text-sm file:mr-3 file:py-1.5 file:px-3 file:rounded-md file:border-0 file:bg-gray-700 file:text-gray-200 file:text-sm"
        />
        {uploading && <span className="text-gray-500 text-xs">Uploading...</span>}
        {coverImagePath && !uploading && (
          <img src={`/api/forums/images/${coverImagePath}`} alt="" className="w-12 h-12 rounded object-cover" />
        )}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-4">
        <div>
          <label className="block text-gray-400 text-sm mb-1.5">Call-to-action link (optional)</label>
          <input
            type="text"
            value={ctaUrl}
            onChange={e => setCtaUrl(e.target.value)}
            placeholder="/draft-intel or https://..."
            className="w-full bg-gray-800 text-gray-200 border border-gray-600 rounded-md px-3 py-2 text-sm"
          />
        </div>
        <div>
          <label className="block text-gray-400 text-sm mb-1.5">Button label</label>
          <input
            type="text"
            value={ctaLabel}
            onChange={e => setCtaLabel(e.target.value.slice(0, 100))}
            placeholder="e.g. Open the live dashboard"
            className="w-full bg-gray-800 text-gray-200 border border-gray-600 rounded-md px-3 py-2 text-sm"
          />
        </div>
      </div>

      {error && <p className="text-red-400 text-sm mb-4">{error}</p>}

      <div className="flex gap-2">
        <button
          type="submit"
          disabled={!title.trim() || !body.trim() || submitting}
          className="bg-green-700 hover:bg-green-600 disabled:opacity-50 disabled:hover:bg-green-700 text-white rounded-md px-4 py-2 text-sm font-semibold transition-colors"
        >
          {submitting ? 'Saving...' : mode === 'edit' ? 'Save changes' : 'Publish'}
        </button>
        {onCancel && (
          <button
            type="button"
            onClick={onCancel}
            className="text-gray-400 hover:text-gray-200 text-sm px-4 py-2"
          >
            Cancel
          </button>
        )}
      </div>
    </form>
  )
}
