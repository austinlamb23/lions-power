import { useEffect, useState } from 'react'

function VsLabel({ bet }) {
  return bet.side_b ? `${bet.side_a} vs ${bet.side_b}` : bet.side_a
}

function OpenBetCard({ bet }) {
  return (
    <div className="rounded-xl border border-gray-700 bg-gray-900 p-4">
      <div className="flex items-center justify-between gap-3 mb-1">
        <p className="text-gray-200 text-sm font-semibold"><VsLabel bet={bet} /></p>
        <span className="text-gray-600 text-[10px] uppercase tracking-wide border border-gray-700 rounded px-1.5 py-0.5 shrink-0">
          open
        </span>
      </div>
      <p className="text-gray-100 text-sm mb-2">{bet.description}</p>
      <p className="text-gray-500 text-xs">Stakes: <span className="text-gray-300">{bet.stakes}</span></p>
      <p className="text-gray-600 text-xs mt-1">
        {bet.resolution_note ? `Auto-resolves: ${bet.resolution_note}` : 'Resolved manually by the commissioner'}
      </p>
      <p className="text-gray-700 text-xs mt-2">added by {bet.submitted_by}</p>
    </div>
  )
}

function ResolvedBetCard({ bet }) {
  const pushed = bet.winner === 'PUSH'
  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4">
      <div className="flex items-center justify-between gap-3 mb-1">
        <p className="text-gray-400 text-sm font-semibold"><VsLabel bet={bet} /></p>
        <span className={`text-[10px] uppercase tracking-wide border rounded px-1.5 py-0.5 shrink-0 ${
          pushed ? 'text-gray-500 border-gray-700' : 'text-green-500 border-green-800'
        }`}>
          {pushed ? 'push' : 'resolved'}
        </span>
      </div>
      <p className="text-gray-400 text-sm mb-2">{bet.description}</p>
      <p className="text-gray-600 text-xs">Stakes: {bet.stakes}</p>
      <p className="text-sm mt-1">
        {pushed
          ? <span className="text-gray-400">Push — no winner</span>
          : <span className="text-green-400 font-medium">{bet.winner} wins</span>}
        <span className="text-gray-700 text-xs"> · {bet.resolved_by === 'auto' ? 'auto-resolved' : 'commissioner call'}</span>
      </p>
    </div>
  )
}

function VoidedBetRow({ bet }) {
  return (
    <div className="py-2.5 border-b border-gray-800 last:border-0">
      <p className="text-gray-600 text-sm"><VsLabel bet={bet} /> — {bet.description}</p>
      <p className="text-gray-700 text-xs mt-0.5">voided by the commissioner</p>
    </div>
  )
}

export default function SideBets() {
  const [bets, setBets] = useState(null)

  useEffect(() => {
    fetch('/api/side-bets').then(r => r.json()).then(d => setBets(d.bets))
  }, [])

  if (bets === null) return <p className="text-gray-500 text-center py-16">Loading...</p>

  const open = bets.filter(b => b.status === 'open')
  const resolved = bets.filter(b => b.status === 'resolved')
  const voided = bets.filter(b => b.status === 'voided')

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-3xl font-bold text-white mb-2" style={{ fontFamily: 'var(--heading)' }}>
        Side Bets
      </h1>
      <p className="text-gray-400 text-sm mb-8">
        The league's wager library. Ask Gabe in GroupMe to add one — bets tied to fantasy or real player
        outcomes resolve themselves automatically once the facts are in; anything else gets called by the
        commissioner.
      </p>

      <h2 className="text-xl font-semibold text-white mb-3">Open</h2>
      {open.length === 0 ? (
        <p className="text-gray-500 text-sm text-center py-8 mb-8 border border-dashed border-gray-700 rounded-xl">
          No open bets right now — ask Gabe to add one.
        </p>
      ) : (
        <div className="space-y-3 mb-8">
          {open.map(bet => <OpenBetCard key={bet.id} bet={bet} />)}
        </div>
      )}

      {resolved.length > 0 && (
        <>
          <h2 className="text-xl font-semibold text-white mb-3">Resolved</h2>
          <div className="space-y-3 mb-8">
            {resolved.map(bet => <ResolvedBetCard key={bet.id} bet={bet} />)}
          </div>
        </>
      )}

      {voided.length > 0 && (
        <>
          <h2 className="text-xl font-semibold text-white mb-3">Voided</h2>
          <div className="rounded-xl border border-gray-800 bg-gray-900/30 px-4 mb-8">
            {voided.map(bet => <VoidedBetRow key={bet.id} bet={bet} />)}
          </div>
        </>
      )}
    </div>
  )
}
