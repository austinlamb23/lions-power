import { useEffect, useState, useCallback } from 'react'
import Leaderboard from '../components/Leaderboard'

const STANDINGS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

const STEPS = [
  { key: 'year', label: 'Draft Year', points: 75 },
  { key: 'manager', label: 'Manager', points: 50 },
  { key: 'standing', label: 'Final Standing', points: 25 },
]

function ResultBadge({ correct }) {
  return correct
    ? <span className="text-green-400 font-semibold ml-2">✓ Correct</span>
    : <span className="text-red-400 font-semibold ml-2">✗ Wrong</span>
}

function ordinal(n) {
  const s = ['th', 'st', 'nd', 'rd']
  const v = n % 100
  return n + (s[(v - 20) % 10] || s[v] || s[0])
}

export default function DraftMatch() {
  const [players, setPlayers] = useState([])
  const [player, setPlayer] = useState(() => localStorage.getItem('lp3_player') || '')
  const [gameState, setGameState] = useState(null)
  const [guess, setGuess] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    fetch('/api/games/draft-match/players')
      .then(r => r.json())
      .then(setPlayers)
  }, [])

  const fetchState = useCallback((name) => {
    if (!name) return
    setLoading(true)
    fetch(`/api/games/draft-match/today?player=${encodeURIComponent(name)}`)
      .then(r => r.json())
      .then(data => {
        setGameState(data)
        setGuess('')
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }, [])

  useEffect(() => {
    fetchState(player)
  }, [player, fetchState])

  function selectPlayer(name) {
    setPlayer(name)
    localStorage.setItem('lp3_player', name)
    setGameState(null)
    setGuess('')
  }

  function handleSubmit() {
    if (!player || !guess || gameState.step === 'done') return
    fetch('/api/games/draft-match/submit-step', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ player_name: player, step: gameState.step, guess: String(guess) }),
    })
      .then(r => r.json())
      .then(data => {
        setGameState(data)
        setGuess('')
      })
  }

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-3xl font-bold text-white mb-2">Draft Match</h1>
      <p className="text-gray-400 text-sm mb-6">
        Three draft picks from a mystery team — guess the year, then the manager, then their finish.
        75 / 50 / 25 pts.
      </p>

      {/* Player selector */}
      <div className="mb-6">
        <label className="text-gray-400 text-sm mr-3">Playing as:</label>
        <select
          value={player}
          onChange={e => selectPlayer(e.target.value)}
          className="bg-gray-800 text-gray-200 border border-gray-600 rounded-md px-3 py-1.5 text-sm"
        >
          <option value="">Select your name</option>
          {players.map(p => <option key={p} value={p}>{p}</option>)}
        </select>
      </div>

      {!player && (
        <p className="text-gray-500 text-center py-16">Select your name to play today's puzzle.</p>
      )}

      {player && loading && (
        <p className="text-gray-500 text-center py-16">Loading...</p>
      )}

      {player && !loading && gameState && (
        <>
          {/* Draft picks display */}
          <div className="rounded-xl border border-gray-700 bg-gray-800/50 p-6 mb-6">
            <p className="text-gray-400 text-xs uppercase tracking-widest mb-3">Today's Draft Picks</p>
            <div className="flex flex-col gap-2">
              {gameState.picks.map(pick => (
                <div key={pick.round} className="flex items-baseline gap-2">
                  <span className="text-gray-500 text-sm">{pick.round_label} round:</span>
                  <span className="text-white font-semibold">{pick.player_name}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Sequential steps */}
          <div className="flex flex-col gap-4 mb-6">
            {STEPS.map(s => {
              const result = gameState.steps[s.key]
              const isAnswered = result.guess !== null
              const isCurrent = gameState.step === s.key

              if (!isAnswered && !isCurrent) return null // future step, not revealed yet

              return (
                <div
                  key={s.key}
                  className={`rounded-xl border p-4 ${
                    isAnswered
                      ? result.is_correct
                        ? 'border-green-700 bg-green-900/20'
                        : 'border-red-800 bg-red-900/20'
                      : 'border-gray-700 bg-gray-800/50'
                  }`}
                >
                  <p className="text-gray-400 text-sm mb-2">{s.label} <span className="text-gray-600">({s.points} pts)</span></p>

                  {isAnswered ? (
                    <div className="text-sm">
                      <span className="text-white font-medium">
                        {s.key === 'standing' ? ordinal(result.guess) : result.guess}
                      </span>
                      <ResultBadge correct={result.is_correct} />
                      {!result.is_correct && (
                        <span className="text-gray-400 ml-2">
                          Correct: <span className="text-green-400 font-medium">
                            {s.key === 'standing' ? ordinal(result.correct) : result.correct}
                          </span>
                        </span>
                      )}
                    </div>
                  ) : (
                    <>
                      {s.key === 'manager' && (
                        <select
                          value={guess}
                          onChange={e => setGuess(e.target.value)}
                          className="w-full bg-gray-800 text-gray-200 border border-gray-600 rounded-md px-3 py-2 text-sm"
                        >
                          <option value="">Select manager...</option>
                          {gameState.managers.map(m => <option key={m} value={m}>{m}</option>)}
                        </select>
                      )}
                      {s.key === 'standing' && (
                        <select
                          value={guess}
                          onChange={e => setGuess(e.target.value)}
                          className="w-full bg-gray-800 text-gray-200 border border-gray-600 rounded-md px-3 py-2 text-sm"
                        >
                          <option value="">Select finish...</option>
                          {STANDINGS.map(n => <option key={n} value={n}>{ordinal(n)} place</option>)}
                        </select>
                      )}
                      {s.key === 'year' && (
                        <select
                          value={guess}
                          onChange={e => setGuess(e.target.value)}
                          className="w-full bg-gray-800 text-gray-200 border border-gray-600 rounded-md px-3 py-2 text-sm"
                        >
                          <option value="">Select year...</option>
                          {gameState.draft_years.map(y => <option key={y} value={y}>{y}</option>)}
                        </select>
                      )}
                      <button
                        onClick={handleSubmit}
                        disabled={!guess}
                        className="mt-3 w-full bg-green-700 hover:bg-green-600 disabled:bg-gray-700 disabled:text-gray-500 text-white font-semibold py-2 rounded-md text-sm transition-colors"
                      >
                        Lock in {s.label.toLowerCase()}
                      </button>
                    </>
                  )}
                </div>
              )
            })}
          </div>

          <Leaderboard show={gameState.submitted} player={player} />

          {gameState.submitted && (
            <div className="rounded-xl border border-gray-700 bg-gray-800/50 p-6 text-center mt-6">
              <div className="text-gray-400 text-sm mb-1">Today's score</div>
              <div className="text-4xl font-bold text-white">{gameState.score}</div>
              <div className="text-gray-500 text-sm mt-1">/ 150 pts</div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
