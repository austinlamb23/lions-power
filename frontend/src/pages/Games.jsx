import { useEffect, useState } from 'react'
import Hangman from './Hangman'
import NameMatch from './NameMatch'
import DraftMatch from './DraftMatch'

const GAME_LABELS = {
  'hangman': 'Hangman',
  'name-match': 'Name Match',
  'draft-match': 'Draft Match',
}

export default function Games() {
  const [game, setGame] = useState(null)

  useEffect(() => {
    fetch('/api/leaderboard/today-game')
      .then(r => r.json())
      .then(d => setGame(d.game))
      .catch(() => setGame(null))
  }, [])

  if (!game) return <p className="text-gray-500 text-center py-16">Loading...</p>

  if (game === 'hangman') return <Hangman />
  if (game === 'name-match') return <NameMatch />
  if (game === 'draft-match') return <DraftMatch />
}
