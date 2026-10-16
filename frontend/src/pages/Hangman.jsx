import { useEffect, useState, useCallback } from 'react'
import Leaderboard from '../components/Leaderboard'

const LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('')

function LetterButton({ letter, status, onClick, disabled }) {
  const colors = {
    correct: 'bg-green-700 text-white cursor-default',
    wrong:   'bg-red-900 text-gray-400 cursor-default',
    default: 'bg-gray-700 text-gray-200 hover:bg-gray-600',
  }
  return (
    <button
      onClick={() => !disabled && onClick(letter)}
      disabled={disabled || status !== 'default'}
      className={`w-9 h-9 rounded text-sm font-bold transition-colors ${colors[status] ?? colors.default}`}
    >
      {letter}
    </button>
  )
}

function WordLetters({ word }) {
  return (
    <div className="flex gap-1 sm:gap-2">
      {word.split('').map((ch, i) => {
        if (!ch.match(/[A-Z_]/)) {
          return (
            <div key={i} className="flex flex-col items-center">
              <span className="text-lg sm:text-2xl font-bold text-gray-200">{ch}</span>
              <div className="w-4 sm:w-6 h-0.5 bg-gray-600 mt-1" />
            </div>
          )
        }
        return (
          <div key={i} className="flex flex-col items-center">
            <span className={`text-lg sm:text-2xl font-bold ${ch === '_' ? 'text-gray-700' : 'text-white'}`}>
              {ch === '_' ? '\u00A0' : ch}
            </span>
            <div className="w-4 sm:w-6 h-0.5 bg-gray-400 mt-1" />
          </div>
        )
      })}
    </div>
  )
}

function WordDisplay({ maskedWord }) {
  if (!maskedWord) return null
  // Each word is grouped into its own non-wrapping flex container, so the
  // outer flex-wrap can only break the line between words, never mid-word.
  return (
    <div className="flex flex-wrap justify-center gap-x-4 gap-y-3 my-8">
      {maskedWord.split(' ').map((word, wi) => (
        <WordLetters key={wi} word={word} />
      ))}
    </div>
  )
}

export default function Hangman() {
  const [players, setPlayers] = useState([])
  const [player, setPlayer] = useState(() => localStorage.getItem('lp3_player') || '')
  const [gameState, setGameState] = useState(null)
  const [wordGuess, setWordGuess] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    fetch('/api/games/hangman/players')
      .then(r => r.json())
      .then(setPlayers)
  }, [])

  const fetchState = useCallback((name) => {
    if (!name) return
    setLoading(true)
    fetch(`/api/games/hangman/today?player=${encodeURIComponent(name)}`)
      .then(r => r.json())
      .then(data => { setGameState(data); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  useEffect(() => {
    fetchState(player)
  }, [player, fetchState])

  function selectPlayer(name) {
    setPlayer(name)
    localStorage.setItem('lp3_player', name)
    setGameState(null)
    setError('')
  }

  function submitGuess(guess) {
    if (!player || !guess.trim()) return
    setError('')
    fetch('/api/games/hangman/guess', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ player_name: player, guess: guess.trim() }),
    })
      .then(r => r.json())
      .then(data => {
        setGameState(data)
        setWordGuess('')
      })
      .catch(() => setError('Something went wrong.'))
  }

  const letterStatus = (letter) => {
    if (!gameState) return 'default'
    const guessed = gameState.guessed_letters ?? []
    if (!guessed.includes(letter)) return 'default'
    return gameState.wrong_letters?.includes(letter) ? 'wrong' : 'correct'
  }

  const gameOver = gameState?.solved || gameState?.failed

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-3xl font-bold text-white mb-2">Hangman</h1>
      <p className="text-gray-400 text-sm mb-6">Guess the Lions Power 3 team name</p>

      {/* Player selector */}
      <div className="mb-6">
        <label className="text-gray-400 text-sm mr-3">Playing as:</label>
        <select
          value={player}
          onChange={e => selectPlayer(e.target.value)}
          className="bg-gray-800 text-gray-200 border border-gray-600 rounded-md px-3 py-1.5 text-sm"
        >
          <option value="">Select your name</option>
          {players.map(p => (
            <option key={p} value={p}>{p}</option>
          ))}
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
          {/* Wrong guesses */}
          <div className="flex items-center gap-3 mb-2">
            <span className="text-gray-400 text-sm">Wrong guesses:</span>
            <span className={`font-bold ${gameState.wrong_guesses >= 5 ? 'text-red-400' : 'text-gray-200'}`}>
              {gameState.wrong_guesses} / {gameState.wrong_guess_limit}
            </span>
            {gameState.wrong_letters?.length > 0 && (
              <span className="text-red-400 text-sm">[{gameState.wrong_letters.join(', ')}]</span>
            )}
          </div>

          {/* Word display */}
          <WordDisplay maskedWord={gameState.masked_word} />

          {/* Game over banner */}
          {gameOver && (
            <div className={`rounded-xl p-4 mb-6 text-center ${gameState.solved ? 'bg-green-900/40 border border-green-700' : 'bg-red-900/40 border border-red-800'}`}>
              {gameState.solved ? (
                <>
                  <div className="text-2xl font-bold text-green-400 mb-1">Solved!</div>
                  <div className="text-gray-300 text-sm mb-2">The answer was <span className="text-white font-semibold">{gameState.answer}</span></div>
                  <div className="text-3xl font-bold text-white">{gameState.score} pts</div>
                </>
              ) : (
                <>
                  <div className="text-2xl font-bold text-red-400 mb-1">Game Over</div>
                  <div className="text-gray-300 text-sm">The answer was <span className="text-white font-semibold">{gameState.answer}</span></div>
                </>
              )}
            </div>
          )}

          {!gameOver && (
            <>
              {/* Alphabet keyboard */}
              <div className="flex flex-wrap gap-1.5 justify-center mb-6">
                {LETTERS.map(l => (
                  <LetterButton
                    key={l}
                    letter={l}
                    status={letterStatus(l)}
                    onClick={submitGuess}
                    disabled={gameOver}
                  />
                ))}
              </div>

              {/* Full word guess */}
              <div className="flex gap-2 mt-2">
                <input
                  type="text"
                  value={wordGuess}
                  onChange={e => setWordGuess(e.target.value.toUpperCase())}
                  onKeyDown={e => e.key === 'Enter' && submitGuess(wordGuess)}
                  placeholder="Guess the full team name..."
                  className="flex-1 bg-gray-800 text-gray-200 border border-gray-600 rounded-md px-3 py-2 text-sm uppercase placeholder:normal-case placeholder:text-gray-500"
                />
                <button
                  onClick={() => submitGuess(wordGuess)}
                  className="bg-green-700 hover:bg-green-600 text-white px-4 py-2 rounded-md text-sm font-medium"
                >
                  Guess
                </button>
              </div>
              {error && <p className="text-red-400 text-sm mt-2">{error}</p>}
            </>
          )}
          <Leaderboard show={gameOver} player={player} />
        </>
      )}
    </div>
  )
}
