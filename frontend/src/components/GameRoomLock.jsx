import { useEffect, useState } from 'react'

export default function GameRoomLock({ year, week, refreshKey }) {
  const [lock, setLock] = useState(null)

  useEffect(() => {
    fetch(`/api/game-room/lock/${year}/${week}`).then(r => r.json()).then(setLock)
  }, [year, week, refreshKey])

  if (!lock) return null

  if (lock.locked) {
    return (
      <div className="rounded-lg border-2 border-red-500 bg-red-950/70 px-4 py-3 mb-3 text-center">
        <p className="text-red-300 font-bold">🔒 LOCKED</p>
        <p className="text-red-400 text-xs mt-1">Locked at {new Date(lock.lock_at).toLocaleString()}</p>
      </div>
    )
  }

  return (
    <div className="rounded-lg border border-gray-700 bg-gray-800/50 px-4 py-2 mb-3 text-center">
      <p className="text-gray-300 text-sm">
        Picks lock <span className="font-semibold">{new Date(lock.lock_at).toLocaleString()}</span>
        {lock.is_override && <span className="text-gray-500 text-xs"> (adjusted this week)</span>}
      </p>
    </div>
  )
}
