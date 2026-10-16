import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import logo from '../assets/lp3.jpeg'
import { PUNISHMENT_MEDIA } from '../data/wallOfShamePhotos'

function QuickLink({ to, label, emoji, sub }) {
  const navigate = useNavigate()
  return (
    <button
      onClick={() => navigate(to)}
      className="rounded-xl border border-gray-700 bg-gray-900 hover:border-green-600 transition-colors px-4 py-5 text-center"
    >
      <div className="text-2xl mb-2">{emoji}</div>
      <div className="text-white font-medium">{label}</div>
      {sub && <div className="text-xs text-gray-500 mt-1">{sub}</div>}
    </button>
  )
}

export default function Home() {
  const navigate = useNavigate()
  const [champion, setChampion] = useState(null)
  const [loser, setLoser] = useState(null)

  useEffect(() => {
    fetch('/api/almanac/hall-of-fame')
      .then(r => r.json())
      .then(data => setChampion(data[0] || null))
      .catch(() => {})
    fetch('/api/almanac/wall-of-shame')
      .then(r => r.json())
      .then(data => setLoser(data[0] || null))
      .catch(() => {})
  }, [])

  const loserMedia = loser && PUNISHMENT_MEDIA[loser.year]

  return (
    <div>
      {/* Hero */}
      <div className="flex flex-col items-center text-center py-10 sm:py-16">
        <img
          src={logo}
          alt="Lions Power 3"
          className="w-32 h-32 sm:w-40 sm:h-40 rounded-full ring-4 ring-green-700 shadow-[0_0_30px_rgba(156,122,63,0.35)] mb-6"
        />
        <h1
          className="text-4xl sm:text-5xl font-bold text-green-400 tracking-wide"
          style={{ fontFamily: 'var(--heading)' }}
        >
          Lions Power 3
        </h1>
        <p className="text-gray-400 mt-3 max-w-md">
          The complete record of the league — every champion, every collapse,
          every argument settled by the numbers. Since 2013 (and, allegedly, 2011).
        </p>
        <div className="flex flex-wrap justify-center gap-3 mt-6">
          <button
            onClick={() => navigate('/almanac')}
            className="px-5 py-2.5 rounded-md bg-green-700 text-white font-medium hover:bg-green-600 transition-colors"
          >
            View the Almanac
          </button>
          <button
            onClick={() => navigate('/games')}
            className="px-5 py-2.5 rounded-md border border-gray-600 text-gray-200 font-medium hover:border-green-600 hover:text-white transition-colors"
          >
            Play Today's Game
          </button>
        </div>
      </div>

      {/* Highlights */}
      <div className="grid sm:grid-cols-2 gap-4 mb-10">
        <div className="rounded-xl border border-gray-700 bg-gray-900 p-6">
          <p className="text-xs uppercase tracking-wide text-gray-500 mb-3">Reigning Champion</p>
          {champion ? (
            <div className="flex items-center gap-4">
              <div className="w-14 h-14 rounded-full bg-gray-800 border-2 border-green-700 flex items-center justify-center text-2xl shrink-0">
                🏆
              </div>
              <div>
                <span className="text-xl font-bold text-green-400" style={{ fontFamily: 'var(--heading)' }}>
                  {champion.year}
                </span>
                <button
                  onClick={() => navigate(`/owner/${encodeURIComponent(champion.owner_name)}`)}
                  className="block text-lg text-white hover:text-green-400 hover:underline font-medium transition-colors"
                >
                  {champion.owner_name}
                </button>
                {champion.team_name && <p className="text-sm text-gray-500">{champion.team_name}</p>}
              </div>
            </div>
          ) : (
            <p className="text-gray-600 text-sm">Loading...</p>
          )}
        </div>

        <div className="rounded-xl border border-gray-700 bg-gray-900 p-6">
          <p className="text-xs uppercase tracking-wide text-gray-500 mb-3">Wall of Shame Inductee</p>
          {loser ? (
            <div className="flex items-center gap-4">
              {loserMedia?.type === 'image' ? (
                <img src={loserMedia.src} alt={`${loser.year} punishment`} className="w-14 h-14 rounded-full object-cover border-2 border-gray-600 shrink-0" />
              ) : loserMedia?.type === 'video' ? (
                <video src={`${loserMedia.src}#t=0.5`} muted preload="metadata" className="w-14 h-14 rounded-full object-cover border-2 border-gray-600 shrink-0" />
              ) : (
                <div className="w-14 h-14 rounded-full bg-gray-800 border-2 border-gray-600 flex items-center justify-center text-2xl shrink-0">
                  🥒
                </div>
              )}
              <div>
                <span className="text-xl font-bold text-gray-400" style={{ fontFamily: 'var(--heading)' }}>
                  {loser.year}
                </span>
                <button
                  onClick={() => navigate(`/owner/${encodeURIComponent(loser.owner_name)}`)}
                  className="block text-lg text-white hover:text-green-400 hover:underline font-medium transition-colors"
                >
                  {loser.owner_name}
                </button>
                {loser.team_name && <p className="text-sm text-gray-500">{loser.team_name}</p>}
              </div>
            </div>
          ) : (
            <p className="text-gray-600 text-sm">Loading...</p>
          )}
        </div>
      </div>

      {/* Explore */}
      <p className="text-xs uppercase tracking-wide text-gray-500 mb-3">Explore</p>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <QuickLink to="/hall-of-fame" emoji="🏆" label="Hall of Fame" />
        <QuickLink to="/wall-of-shame" emoji="🥒" label="Wall of Shame" />
        <QuickLink to="/power-rankings" emoji="📊" label="Power Rankings" sub="Coming soon" />
        <QuickLink to="/the-pod" emoji="🎙️" label="The Pod" sub="Coming soon" />
      </div>
    </div>
  )
}
