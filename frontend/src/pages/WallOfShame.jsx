import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { PUNISHMENT_MEDIA } from '../data/wallOfShamePhotos'

export default function WallOfShame() {
  const navigate = useNavigate()
  const [losers, setLosers] = useState([])
  const [loading, setLoading] = useState(true)
  const [lightbox, setLightbox] = useState(null)

  useEffect(() => {
    fetch('/api/almanac/wall-of-shame')
      .then(r => r.json())
      .then(data => { setLosers(data); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  return (
    <div>
      <h1 className="text-3xl font-bold text-white mb-2">Wall of Shame</h1>
      <p className="text-gray-400 mb-8">Every last-place finisher in Lions Power 3 history, most recent first.</p>

      {loading ? (
        <p className="text-center py-16 text-gray-500">Loading...</p>
      ) : losers.length === 0 ? (
        <div className="rounded-xl border border-gray-700 bg-gray-900 py-16 text-center text-gray-500">
          No last-place finishers on record yet.
        </div>
      ) : (
        <div className="relative">
          <div className="absolute left-6 top-2 bottom-2 w-px bg-gray-700 hidden sm:block" />
          <div className="space-y-4">
            {losers.map(l => {
              const media = PUNISHMENT_MEDIA[l.year]
              return (
                <div key={l.year} className="relative sm:pl-16">
                  <div className="hidden sm:flex absolute left-0 top-1/2 -translate-y-1/2 w-12 h-12 rounded-full bg-gray-900 border-2 border-gray-600 items-center justify-center text-xl">
                    🥒
                  </div>
                  <div className="rounded-xl border border-gray-700 bg-gray-900 px-6 py-5 flex flex-col sm:flex-row sm:flex-wrap items-center sm:items-center justify-between gap-4">
                    <div className="flex flex-col sm:flex-row items-center sm:items-center gap-4 text-center sm:text-left">
                      {media && (
                        <button
                          onClick={() => setLightbox({ type: media.type, src: media.src, caption: `${l.year} — ${l.owner_name}` })}
                          className="relative shrink-0 rounded-lg overflow-hidden border border-gray-700 hover:border-green-600 transition-colors"
                        >
                          {media.type === 'video' ? (
                            <>
                              <video
                                src={`${media.src}#t=0.5`}
                                muted
                                preload="metadata"
                                className="w-40 h-40 sm:w-24 sm:h-24 object-cover"
                              />
                              <span className="absolute inset-0 flex items-center justify-center bg-black/30">
                                <span className="w-8 h-8 rounded-full bg-black/60 flex items-center justify-center text-white text-sm">▶</span>
                              </span>
                            </>
                          ) : (
                            <img src={media.src} alt={`${l.year} punishment`} className="w-40 h-40 sm:w-24 sm:h-24 object-cover" />
                          )}
                        </button>
                      )}
                      <div>
                        <div className="flex items-center justify-center sm:justify-start gap-2">
                          <span className="sm:hidden text-xl">🥒</span>
                          <span className="text-2xl font-bold text-gray-400" style={{ fontFamily: 'var(--heading)' }}>
                            {l.year}
                          </span>
                        </div>
                        <button
                          onClick={() => navigate(`/owner/${encodeURIComponent(l.owner_name)}`)}
                          className="text-lg text-white hover:text-green-400 hover:underline font-medium transition-colors"
                        >
                          {l.owner_name}
                        </button>
                        <p className="text-sm text-gray-500">{l.team_name}</p>
                      </div>
                    </div>
                    <div className="text-center sm:text-right text-sm text-gray-400">
                      <p>
                        {l.wins}-{l.losses}{l.ties ? `-${l.ties}` : ''} · {l.points_for?.toLocaleString()} pts
                      </p>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      <p className="mt-8 text-xs text-gray-600">More punishment evidence and accolades coming soon.</p>

      {lightbox && (
        <div
          className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-6"
          onClick={() => setLightbox(null)}
        >
          <div className="max-w-2xl w-full" onClick={e => e.stopPropagation()}>
            {lightbox.type === 'video' ? (
              <video src={lightbox.src} controls autoPlay className="w-full rounded-xl border border-gray-700" />
            ) : (
              <img src={lightbox.src} alt={lightbox.caption} className="w-full rounded-xl border border-gray-700" />
            )}
            <p className="text-center text-gray-300 mt-3">{lightbox.caption}</p>
          </div>
        </div>
      )}
    </div>
  )
}
