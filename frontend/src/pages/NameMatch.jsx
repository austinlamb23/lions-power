import { useEffect, useState, useCallback } from 'react'
import Leaderboard from '../components/Leaderboard'

export default function NameMatch() {
  const [players, setPlayers] = useState([])
  const [player, setPlayer] = useState(() => localStorage.getItem('lp3_player') || '')
  const [gameState, setGameState] = useState(null)
  const [guesses, setGuesses] = useState(['', '', ''])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    fetch('/api/games/name-match/players')
      .then(r => r.json())
      .then(setPlayers)
  }, [])

  const fetchState = useCallback((name) => {
    if (!name) return
    setLoading(true)
    fetch(`/api/games/name-match/today?player=${encodeURIComponent(name)}`)
      .then(r => r.json())
      .then(data => {
        setGameState(data)
        setGuesses(data.guesses?.length ? data.guesses : ['', '', ''])
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
    setGuesses(['', '', ''])
  }

  function setGuess(i, value) {
    setGuesses(prev => prev.map((g, idx) => idx === i ? value : g))
  }

  function handleSubmit() {
    if (!player || guesses.some(g => !g)) return
    fetch('/api/games/name-match/submit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ player_name: player, guesses }),
    })
      .then(r => r.json())
      .then(data => setGameState(data))
  }

  const allSelected = guesses.every(g => g !== '')

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-3xl font-bold text-white mb-2">Name Match</h1>
      <p className="text-gray-400 text-sm mb-6">Match each team name to its manager — 50 pts per correct answer</p>

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
          <div className="flex flex-col gap-4 mb-6">
            {gameState.team_names.map((name, i) => {
              const result = gameState.results?.[i]
              return (
                <div key={i} className={`rounded-xl border p-4 ${
                  result
                    ? result.correct
                      ? 'border-green-700 bg-green-900/20'
                      : 'border-red-800 bg-red-900/20'
                    : 'border-gray-700 bg-gray-800/50'
                }`}>
                  <p className="text-white font-semibold mb-3">{name}</p>
                  <select
                    value={guesses[i]}
                    onChange={e => setGuess(i, e.target.value)}
                    disabled={gameState.submitted}
                    className="w-full bg-gray-800 text-gray-200 border border-gray-600 rounded-md px-3 py-2 text-sm disabled:opacity-60"
                  >
                    <option value="">Select manager...</option>
                    {gameState.managers.map(m => (
                      <option key={m} value={m}>{m}</option>
                    ))}
                  </select>
                  {result && !result.correct && (
                    <p className="text-sm text-gray-400 mt-2">
                      Correct answer: <span className="text-green-400 font-medium">{result.correct_owner}</span>
                    </p>
                  )}
                </div>
              )
            })}
          </div>

          <Leaderboard show={gameState.submitted} player={player} />

          {!gameState.submitted ? (
            <button
              onClick={handleSubmit}
              disabled={!allSelected}
              className="w-full bg-green-700 hover:bg-green-600 disabled:bg-gray-700 disabled:text-gray-500 text-white font-semibold py-3 rounded-xl transition-colors"
            >
              Submit
            </button>
          ) : (
            <div className="rounded-xl border border-gray-700 bg-gray-800/50 p-6 text-center">
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
