import { Link } from 'react-router-dom'

// Data-driven so a future game is a one-line addition here, not a page rework.
const GAME_ROOM_ENTRIES = [
  {
    key: 'daily-game', label: 'Daily Game', to: '/games', requiresLogin: false,
    description: 'Hangman, Name Match, and Draft Match — a new one every day.',
  },
  {
    key: 'weekly-predictions', label: 'Weekly Predictions', to: '/game-room/predictions', requiresLogin: true,
    description: 'Pick the winner of every real matchup, every week.',
  },
  {
    key: 'all-star-roster', label: 'Weekly All-Star Roster', to: '/game-room/all-star-roster', requiresLogin: true,
    description: 'Draft a QB/RB/RB/WR/WR/TE/FLEX/D-ST/K from anyone in the league — max one player per real team.',
  },
]

function GameCard({ entry }) {
  return (
    <Link
      to={entry.to}
      className="block rounded-xl border border-gray-700 bg-gray-900 p-5 hover:border-green-700 transition-colors"
    >
      <div className="flex items-center justify-between mb-1">
        <h2 className="text-lg font-bold text-white">{entry.label}</h2>
        {entry.requiresLogin && (
          <span className="text-gray-600 text-[10px] uppercase tracking-wide border border-gray-700 rounded px-1.5 py-0.5">
            login required
          </span>
        )}
      </div>
      <p className="text-gray-400 text-sm">{entry.description}</p>
    </Link>
  )
}

export default function GameRoom() {
  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-3xl font-bold text-white mb-2" style={{ fontFamily: 'var(--heading)' }}>
        Game Room
      </h1>
      <p className="text-gray-400 text-sm mb-8">
        Everything to play against the league, in one place.
      </p>
      <div className="flex flex-col gap-4">
        {GAME_ROOM_ENTRIES.map(entry => <GameCard key={entry.key} entry={entry} />)}
      </div>
    </div>
  )
}
