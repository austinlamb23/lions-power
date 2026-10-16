import { useEffect, useState } from 'react'

function ordinal(n) {
  if (n == null) return '—'
  const s = ['th', 'st', 'nd', 'rd']
  const v = n % 100
  return n + (s[(v - 20) % 10] || s[v] || s[0])
}

function OverallTable({ rows }) {
  if (!rows) {
    return (
      <div className="rounded-xl border border-gray-700 bg-gray-800/50 p-5">
        <h2 className="text-white font-semibold mb-3">All-Time Leaderboard</h2>
        <p className="text-gray-500 text-sm">Loading...</p>
      </div>
    )
  }
  return (
    <div className="rounded-xl border border-gray-700 bg-gray-800/50 p-5">
      <h2 className="text-white font-semibold mb-4">All-Time Leaderboard</h2>
      {rows.length === 0 ? (
        <p className="text-gray-500 text-sm">No scores yet.</p>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="text-gray-400 text-left border-b border-gray-700">
              <th className="pb-2 pr-3 w-6">#</th>
              <th className="pb-2">Player</th>
              <th className="pb-2 text-right">Total</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={r.player} className="border-b border-gray-800 last:border-0">
                <td className="py-2 pr-3 text-gray-500">{i + 1}</td>
                <td className="py-2 text-white">{r.player}</td>
                <td className="py-2 text-right font-semibold text-green-400">{r.total}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}

function WeeklyTable({ weekly }) {
  if (!weekly) {
    return (
      <div className="rounded-xl border border-gray-700 bg-gray-800/50 p-5">
        <h2 className="text-white font-semibold mb-3">This Week's Leaderboard</h2>
        <p className="text-gray-500 text-sm">Loading...</p>
      </div>
    )
  }
  const { rows } = weekly
  return (
    <div className="rounded-xl border border-gray-700 bg-gray-800/50 p-5">
      <h2 className="text-white font-semibold mb-4">This Week's Leaderboard</h2>
      {rows.length === 0 ? (
        <p className="text-gray-500 text-sm">No scores yet this week.</p>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="text-gray-400 text-left border-b border-gray-700">
              <th className="pb-2 pr-3 w-6">#</th>
              <th className="pb-2">Player</th>
              <th className="pb-2 text-right">Total</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={r.player} className="border-b border-gray-800 last:border-0">
                <td className="py-2 pr-3 text-gray-500">{i + 1}</td>
                <td className="py-2 text-white">{r.player}</td>
                <td className="py-2 text-right font-semibold text-green-400">{r.total}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}

function ScoreOnlyTable({ rows }) {
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="text-gray-400 text-left border-b border-gray-700">
          <th className="pb-2 pr-3 w-6">#</th>
          <th className="pb-2">Player</th>
          <th className="pb-2 text-right">Score</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r, i) => (
          <tr key={r.player} className="border-b border-gray-800 last:border-0">
            <td className="py-2 pr-3 text-gray-500">{i + 1}</td>
            <td className="py-2 text-white">{r.player}</td>
            <td className="py-2 text-right font-semibold text-green-400">{r.score}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function HangmanGuesses({ rows }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-gray-400 text-left border-b border-gray-700">
            <th className="pb-2 pr-3 w-6">#</th>
            <th className="pb-2">Player</th>
            <th className="pb-2">Result</th>
            <th className="pb-2">Wrong</th>
            <th className="pb-2">Letters Tried</th>
            <th className="pb-2 text-right">Score</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={r.player} className="border-b border-gray-800 last:border-0">
              <td className="py-2 pr-3 text-gray-500">{i + 1}</td>
              <td className="py-2 text-white">{r.player}</td>
              <td className="py-2">
                {r.solved
                  ? <span className="text-green-400">Solved</span>
                  : <span className="text-red-400">Failed</span>}
              </td>
              <td className="py-2 text-gray-300">{r.wrong_guesses}</td>
              <td className="py-2 text-gray-400 text-xs">{r.guessed_letters.join(', ')}</td>
              <td className="py-2 text-right font-semibold text-green-400">{r.score}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function NameMatchGuesses({ rows, teamNames, correctOwners }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-gray-400 text-left border-b border-gray-700">
            <th className="pb-2 pr-3 w-6">#</th>
            <th className="pb-2">Player</th>
            {teamNames.map((t, i) => (
              <th key={i} className="pb-2">{t}</th>
            ))}
            <th className="pb-2 text-right">Score</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={r.player} className="border-b border-gray-800 last:border-0">
              <td className="py-2 pr-3 text-gray-500">{i + 1}</td>
              <td className="py-2 text-white">{r.player}</td>
              {correctOwners.map((correct, gi) => {
                const guess = r.guesses[gi]
                return (
                  <td key={gi} className={guess === correct ? 'py-2 text-green-400' : 'py-2 text-red-400'}>
                    {guess || '—'}
                  </td>
                )
              })}
              <td className="py-2 text-right font-semibold text-green-400">{r.score}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="text-xs text-gray-600 mt-3">Correct: {correctOwners.join(' · ')}</p>
    </div>
  )
}

function DraftMatchGuesses({ rows, correct }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-gray-400 text-left border-b border-gray-700">
            <th className="pb-2 pr-3 w-6">#</th>
            <th className="pb-2">Player</th>
            <th className="pb-2">Manager</th>
            <th className="pb-2">Standing</th>
            <th className="pb-2">Year</th>
            <th className="pb-2 text-right">Score</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={r.player} className="border-b border-gray-800 last:border-0">
              <td className="py-2 pr-3 text-gray-500">{i + 1}</td>
              <td className="py-2 text-white">{r.player}</td>
              <td className={r.manager_guess === correct.manager ? 'py-2 text-green-400' : 'py-2 text-red-400'}>
                {r.manager_guess || '—'}
              </td>
              <td className={r.standing_guess === correct.standing ? 'py-2 text-green-400' : 'py-2 text-red-400'}>
                {ordinal(r.standing_guess)}
              </td>
              <td className={r.year_guess === correct.year ? 'py-2 text-green-400' : 'py-2 text-red-400'}>
                {r.year_guess ?? '—'}
              </td>
              <td className="py-2 text-right font-semibold text-green-400">{r.score}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="text-xs text-gray-600 mt-3">
        Correct: {correct.manager} · {ordinal(correct.standing)} · {correct.year}
      </p>
    </div>
  )
}

function DailyLeaderboard({ daily }) {
  if (!daily) {
    return (
      <div className="rounded-xl border border-gray-700 bg-gray-800/50 p-5">
        <h2 className="text-white font-semibold mb-3">Today's Leaderboard</h2>
        <p className="text-gray-500 text-sm">Loading...</p>
      </div>
    )
  }
  const { rows, unlocked, game } = daily
  return (
    <div className="rounded-xl border border-gray-700 bg-gray-800/50 p-5">
      <h2 className="text-white font-semibold mb-1">Today's Leaderboard</h2>
      {!unlocked && rows.length > 0 && (
        <p className="text-xs text-gray-500 mb-4">Finish today's puzzle to see everyone's guesses.</p>
      )}
      {rows.length === 0 ? (
        <p className="text-gray-500 text-sm mt-3">No scores yet.</p>
      ) : !unlocked ? (
        <ScoreOnlyTable rows={rows} />
      ) : game === 'hangman' ? (
        <HangmanGuesses rows={rows} />
      ) : game === 'name-match' ? (
        <NameMatchGuesses rows={rows} teamNames={daily.team_names} correctOwners={daily.correct_owners} />
      ) : (
        <DraftMatchGuesses rows={rows} correct={daily.correct} />
      )}
    </div>
  )
}

export default function Leaderboard({ show, player }) {
  const [daily, setDaily] = useState(null)
  const [weekly, setWeekly] = useState(null)
  const [overall, setOverall] = useState(null)

  useEffect(() => {
    if (!show) return
    fetch(`/api/leaderboard/daily?player=${encodeURIComponent(player || '')}`)
      .then(r => r.json())
      .then(setDaily)
      .catch(() => setDaily({ rows: [], unlocked: false, game: null }))
    fetch('/api/leaderboard/weekly').then(r => r.json()).then(setWeekly).catch(() => setWeekly({ rows: [] }))
    fetch('/api/leaderboard/overall').then(r => r.json()).then(setOverall).catch(() => setOverall([]))
  }, [show, player])

  if (!show) return null

  return (
    <div className="mt-8 flex flex-col gap-5">
      <DailyLeaderboard daily={daily} />
      <WeeklyTable weekly={weekly} />
      <OverallTable rows={overall} />
    </div>
  )
}
