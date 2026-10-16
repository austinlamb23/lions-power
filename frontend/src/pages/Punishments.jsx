import { useEffect, useState } from 'react'
import { AUTH_KEY, loadAuth, parseError, LoginForm, FlaggedBanner } from '../components/OwnerLogin'

const IDEA_MAX_LEN = 280

function IdeaForm({ authHeaders, onSubmitted }) {
  const [text, setText] = useState('')
  const [error, setError] = useState('')
  const [flagged, setFlagged] = useState('')
  const [submitting, setSubmitting] = useState(false)

  function handleSubmit(e) {
    e.preventDefault()
    const trimmed = text.trim()
    if (!trimmed) return
    setSubmitting(true)
    setError('')
    setFlagged('')
    fetch('/api/punishments/ideas', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders },
      body: JSON.stringify({ text: trimmed }),
    })
      .then(async r => {
        if (r.status === 423) { setFlagged(await parseError(r)); throw new Error('') }
        if (!r.ok) throw new Error(await parseError(r))
        return r.json()
      })
      .then(() => {
        setText('')
        onSubmitted()
      })
      .catch(err => { if (err.message) setError(err.message) })
      .finally(() => setSubmitting(false))
  }

  return (
    <form onSubmit={handleSubmit} className="rounded-xl border border-gray-700 bg-gray-900 p-4 mb-8">
      <FlaggedBanner message={flagged} />
      <label className="block text-gray-400 text-sm mb-1.5">Submit a punishment idea</label>
      <div className="flex flex-col sm:flex-row gap-2">
        <input
          type="text"
          value={text}
          onChange={e => setText(e.target.value.slice(0, IDEA_MAX_LEN))}
          placeholder="e.g. Wear last year's jersey to the draft"
          className="flex-1 bg-gray-800 text-gray-200 border border-gray-600 rounded-md px-3 py-2 text-sm"
        />
        <button
          type="submit"
          disabled={!text.trim() || submitting}
          className="bg-green-700 hover:bg-green-600 disabled:opacity-50 disabled:hover:bg-green-700 text-white rounded-md px-4 py-2 text-sm font-semibold whitespace-nowrap transition-colors"
        >
          Submit
        </button>
      </div>
      <div className="flex items-center justify-between mt-1.5">
        <p className="text-red-400 text-xs">{error}</p>
        <p className="text-gray-600 text-xs">{text.length}/{IDEA_MAX_LEN}</p>
      </div>
    </form>
  )
}

function VoteTotalsPanel() {
  const [data, setData] = useState(null)

  useEffect(() => {
    fetch('/api/punishments/vote-totals').then(r => r.json()).then(setData)
  }, [])

  if (!data) return null

  return (
    <div className="rounded-lg border border-gray-700 bg-gray-800/50 px-4 py-3 mb-4">
      <p className="text-gray-400 text-xs uppercase tracking-wide mb-2">Manager vote usage</p>
      <div className="space-y-1.5">
        {data.totals.map(t => {
          const pct = Math.min(100, (t.votes_used / data.votes_budget) * 100)
          return (
            <div key={t.owner_name} className="flex items-center gap-3 text-sm">
              <span className="text-gray-300 w-36 flex-shrink-0 truncate">{t.owner_name}</span>
              <div className="flex-1 h-1.5 rounded-full bg-gray-700 overflow-hidden">
                <div
                  className={`h-full rounded-full ${t.votes_used >= data.votes_budget ? 'bg-red-500' : 'bg-green-600'}`}
                  style={{ width: `${pct}%` }}
                />
              </div>
              <span className="text-gray-500 text-xs w-14 text-right flex-shrink-0">
                {t.votes_used} / {data.votes_budget}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function ActiveIdeaRow({ idea, rank }) {
  const eliminated = idea.status === 'eliminated'
  return (
    <div className="flex items-center gap-4 py-3 border-b border-gray-800 last:border-0">
      <span className={`text-sm font-semibold w-6 text-right shrink-0 ${eliminated ? 'text-gray-700' : 'text-gray-600'}`}>
        {rank}
      </span>
      <div className="flex-1 min-w-0">
        <p className={`text-sm break-words ${eliminated ? 'text-gray-600 line-through' : 'text-gray-100'}`}>
          {idea.text}
        </p>
        <p className="text-gray-600 text-xs mt-0.5">
          {eliminated
            ? `eliminated week ${idea.eliminated_week} by ${idea.eliminated_by}`
            : `submitted by ${idea.submitted_by}`}
        </p>
      </div>
      {eliminated ? (
        <span className="text-red-500 text-lg shrink-0">✂️</span>
      ) : (
        <span className="text-green-500 text-lg shrink-0">🥒</span>
      )}
    </div>
  )
}

function HonorableMentionRow({ idea, rank }) {
  return (
    <div className="flex items-center gap-4 py-2.5 border-b border-gray-800 last:border-0">
      <span className="text-gray-700 text-sm font-semibold w-6 text-right shrink-0">{rank}</span>
      <div className="flex-1 min-w-0">
        <p className="text-gray-400 text-sm break-words">{idea.text}</p>
        <p className="text-gray-700 text-xs mt-0.5">submitted by {idea.submitted_by}</p>
      </div>
    </div>
  )
}

function EliminationHistory() {
  const [data, setData] = useState(null)

  useEffect(() => {
    fetch('/api/punishments/eliminations').then(r => r.json()).then(setData)
  }, [])

  if (!data) return null
  const completed = data.eliminations.filter(e => e.status === 'completed')
  if (completed.length === 0) return null

  return (
    <div className="rounded-xl border border-gray-700 bg-gray-900 p-4 mb-8">
      <h3 className="text-gray-200 font-semibold mb-3">Elimination History</h3>
      <ol className="space-y-2">
        {completed.map(e => (
          <li key={`${e.year}-${e.week}`} className="text-sm">
            <span className="text-gray-600">Week {e.week}:</span>{' '}
            <span className="text-gray-300">{e.owner_name}</span>
            <span className="text-gray-600"> ({e.score} pts) eliminated </span>
            <span className="text-gray-300">"{e.idea_text}"</span>
          </li>
        ))}
      </ol>
    </div>
  )
}

function PickleRow({ idea, rank, maxVotes, votesRemaining, canVote, onSetVotes }) {
  const positions = Array.from({ length: maxVotes }, (_, i) => i + 1)

  return (
    <div className="flex items-center gap-4 py-3 border-b border-gray-800 last:border-0">
      <span className="text-gray-600 text-sm font-semibold w-6 text-right shrink-0">{rank}</span>

      <div className="flex-1 min-w-0">
        <p className="text-gray-100 text-sm break-words">{idea.text}</p>
        <p className="text-gray-600 text-xs mt-0.5">submitted by {idea.submitted_by}</p>
      </div>

      <div className="flex items-center gap-3 shrink-0">
        <div className="flex gap-1">
          {positions.map(position => {
            const lit = position <= idea.my_votes
            const additional = position - idea.my_votes
            const disabled = !canVote || (additional > 0 && votesRemaining !== null && additional > votesRemaining)
            return (
              <button
                key={position}
                type="button"
                disabled={disabled}
                onClick={() => onSetVotes(idea.id, position === idea.my_votes ? 0 : position)}
                title={canVote ? `Set ${position} vote${position > 1 ? 's' : ''}` : 'Log in to vote'}
                className={`text-xl leading-none transition-opacity ${
                  lit ? 'opacity-100' : 'opacity-25 grayscale'
                } ${disabled ? 'cursor-not-allowed' : 'hover:opacity-80 cursor-pointer'}`}
              >
                🥒
              </button>
            )
          })}
        </div>

        <div className="w-px self-stretch bg-gray-700" />

        <div className="flex flex-col items-center w-14">
          <span className="text-2xl font-bold leading-none text-green-400" style={{ fontFamily: 'var(--heading)' }}>
            {idea.vote_count}
          </span>
          <span className="text-gray-600 text-[10px] uppercase tracking-wide mt-0.5">votes</span>
        </div>
      </div>
    </div>
  )
}

export default function Punishments() {
  const [owners, setOwners] = useState([])
  const [auth, setAuth] = useState(loadAuth)
  const [ideas, setIdeas] = useState([])
  const [locked, setLocked] = useState(false)
  const [votesBudget, setVotesBudget] = useState(0)
  const [votesRemaining, setVotesRemaining] = useState(null)
  const [maxVotesPerIdea, setMaxVotesPerIdea] = useState(3)
  const [loading, setLoading] = useState(true)
  const [voteError, setVoteError] = useState('')
  const [voteFlagged, setVoteFlagged] = useState('')

  const authHeaders = auth ? { Authorization: `Bearer ${auth.token}` } : {}

  function loadIdeas() {
    setLoading(true)
    fetch('/api/punishments/ideas', { headers: authHeaders })
      .then(r => r.json())
      .then(data => {
        setIdeas(data.ideas)
        setLocked(data.locked)
        setVotesBudget(data.votes_budget)
        setVotesRemaining(data.votes_remaining)
        setMaxVotesPerIdea(data.max_votes_per_idea)
      })
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    fetch('/api/punishments/owners').then(r => r.json()).then(setOwners)
  }, [])

  useEffect(() => {
    loadIdeas()
  }, [auth])

  function handleLogout() {
    localStorage.removeItem(AUTH_KEY)
    setAuth(null)
  }

  function handleSetVotes(ideaId, votes) {
    setVoteError('')
    setVoteFlagged('')
    fetch(`/api/punishments/ideas/${ideaId}/vote`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders },
      body: JSON.stringify({ votes }),
    })
      .then(async r => {
        if (r.status === 401) {
          handleLogout()
          return
        }
        if (r.status === 423) { setVoteFlagged(await parseError(r)); return }
        if (!r.ok) throw new Error(await parseError(r))
        loadIdeas()
      })
      .catch(err => setVoteError(err.message))
  }

  if (locked) {
    // The original locked-in top 13 -- includes eliminated ones (shown
    // struck through), since lock_rank <= 13 is permanent regardless of
    // status. Only honorable_mention ideas were never in this pool at all.
    const pool = ideas.filter(i => i.status === 'active' || i.status === 'eliminated')
    const honorableMentions = ideas.filter(i => i.status === 'honorable_mention')
    const survivorCount = pool.filter(i => i.status === 'active').length

    return (
      <div className="max-w-2xl mx-auto">
        <h1 className="text-3xl font-bold text-white mb-2" style={{ fontFamily: 'var(--heading)' }}>
          Punishment Squid Games
        </h1>
        <p className="text-gray-400 text-sm mb-8">
          The pool is locked in — {pool.length} punishments made the cut. Voting's closed. Every week, that
          week's lowest-scoring team eliminates one from the pool. {survivorCount === 1
            ? "One punishment survives — that's what the season's loser gets."
            : `${survivorCount} still standing.`}
        </p>

        <h2 className="text-xl font-semibold text-white mb-3">The Pool</h2>
        {loading && <p className="text-gray-500 text-center py-12">Loading...</p>}
        {!loading && (
          <div className="rounded-xl border border-gray-700 bg-gray-900 px-4 mb-8">
            {pool.map((idea, i) => (
              <ActiveIdeaRow key={idea.id} idea={idea} rank={i + 1} />
            ))}
          </div>
        )}

        <EliminationHistory />

        {honorableMentions.length > 0 && (
          <>
            <h2 className="text-xl font-semibold text-white mb-3">Honorable Mentions</h2>
            <p className="text-gray-600 text-xs mb-3">Didn't make the top 13, archived here for posterity.</p>
            <div className="rounded-xl border border-gray-800 bg-gray-900/50 px-4">
              {honorableMentions.map((idea, i) => (
                <HonorableMentionRow key={idea.id} idea={idea} rank={i + 1} />
              ))}
            </div>
          </>
        )}
      </div>
    )
  }

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-3xl font-bold text-white mb-2" style={{ fontFamily: 'var(--heading)' }}>
        Punishment Squid Games
      </h1>
      <p className="text-gray-400 text-sm mb-8">
        We're picking 13 punishment ideas going into the season. Submit ideas, then spend your pickles —
        everyone gets {votesBudget || 25} to spread across the pool, up to {maxVotesPerIdea} per idea. Once the
        season starts, each week's lowest-scoring team eliminates one idea from the pool, until whatever's
        left is what the loser actually gets.
      </p>

      {auth ? (
        <div className="flex items-center justify-between mb-4">
          <p className="text-gray-400 text-sm">
            Logged in as <span className="text-gray-200 font-semibold">{auth.owner_name}</span>
          </p>
          <button onClick={handleLogout} className="text-gray-500 hover:text-gray-300 text-xs underline">
            Log out
          </button>
        </div>
      ) : null}

      {auth ? (
        <IdeaForm authHeaders={authHeaders} onSubmitted={loadIdeas} />
      ) : (
        <div className="mb-8">
          <LoginForm owners={owners} onLoggedIn={setAuth} />
        </div>
      )}

      {auth && votesRemaining !== null && (
        <div className="flex items-center justify-between mb-4 rounded-lg border border-gray-700 bg-gray-800/50 px-4 py-2">
          <span className="text-gray-300 text-sm">
            Votes remaining <span className="text-gray-600">· up to {maxVotesPerIdea} per idea</span>
          </span>
          <span className={`text-sm font-semibold ${votesRemaining === 0 ? 'text-red-400' : 'text-green-400'}`}>
            {votesRemaining} / {votesBudget}
          </span>
        </div>
      )}

      <FlaggedBanner message={voteFlagged} />
      {voteError && <p className="text-red-400 text-sm mb-4">{voteError}</p>}

      <VoteTotalsPanel />

      <h2 className="text-xl font-semibold text-white mb-3">The Pool</h2>

      {loading && <p className="text-gray-500 text-center py-12">Loading...</p>}

      {!loading && ideas.length === 0 && (
        <p className="text-gray-500 text-center py-12">No ideas yet — be the first to submit one.</p>
      )}

      {!loading && ideas.length > 0 && (
        <div className="rounded-xl border border-gray-700 bg-gray-900 px-4">
          {ideas.map((idea, i) => (
            <PickleRow
              key={idea.id}
              idea={idea}
              rank={i + 1}
              maxVotes={maxVotesPerIdea}
              votesRemaining={votesRemaining}
              canVote={!!auth}
              onSetVotes={handleSetVotes}
            />
          ))}
        </div>
      )}
    </div>
  )
}
