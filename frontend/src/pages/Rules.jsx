import { useEffect, useState } from 'react'

const STATUS_STYLE = {
  pending: 'bg-yellow-900/40 text-yellow-500 border-yellow-800',
  approved: 'bg-green-900/40 text-green-400 border-green-800',
  rejected: 'bg-red-900/40 text-red-400 border-red-800',
}

const TABS = [
  { key: 'rules', label: 'Rules' },
  { key: 'pending', label: 'Pending Changes' },
  { key: 'shitlist', label: "Commissioner's Shit List" },
]

function StatusBadge({ status }) {
  const cls = STATUS_STYLE[status] || 'bg-gray-800 text-gray-400 border-gray-700'
  return (
    <span className={`text-xs font-semibold px-2 py-0.5 rounded border capitalize ${cls}`}>
      {status}
    </span>
  )
}

function EmptyState({ children }) {
  return (
    <div className="rounded-xl border border-gray-700 bg-gray-900 py-16 text-center text-gray-500">
      {children}
    </div>
  )
}

function RulesTab({ categories }) {
  if (categories.length === 0) return <EmptyState>No rules on record yet.</EmptyState>

  return (
    <div className="space-y-8">
      {categories.map(({ category, rules }) => (
        <div key={category}>
          <h2
            className="text-xl font-bold text-green-400 mb-3"
            style={{ fontFamily: 'var(--heading)' }}
          >
            {category}
          </h2>
          <div className="space-y-3">
            {rules.map(rule => (
              <div key={rule.id} className="rounded-xl border border-gray-700 bg-gray-900 px-6 py-4">
                {rule.title && (
                  <div className="text-white font-semibold mb-1">{rule.title}</div>
                )}
                <p className="text-gray-300 whitespace-pre-wrap">{rule.text}</p>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

function PendingTab({ pending }) {
  if (pending.length === 0) return <EmptyState>No pending changes right now.</EmptyState>

  return (
    <div className="space-y-3">
      {pending.map(change => (
        <div key={change.id} className="rounded-xl border border-gray-700 bg-gray-900 px-6 py-4">
          <div className="flex items-start justify-between gap-4 mb-1">
            <p className="text-gray-300">{change.text}</p>
            <StatusBadge status={change.status} />
          </div>
          {(change.proposed_by || change.note) && (
            <div className="text-gray-500 text-sm mt-2 space-y-0.5">
              {change.proposed_by && <div>Proposed by {change.proposed_by}</div>}
              {change.note && <div>{change.note}</div>}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

function ShitlistTab({ shitlist }) {
  if (shitlist.length === 0) return <EmptyState>Nobody's on the commissioner's bad side right now.</EmptyState>

  return (
    <div className="space-y-3">
      {shitlist.map(entry => (
        <div key={entry.id} className="rounded-xl border border-red-900/60 bg-gray-900 px-6 py-4 flex items-start gap-4">
          <span
            className="shrink-0 w-9 h-9 rounded-full bg-red-950 border border-red-800 flex items-center justify-center text-red-400 font-bold text-sm"
            style={{ fontFamily: 'var(--heading)' }}
          >
            #{entry.rank}
          </span>
          <div>
            <div className="text-white font-semibold">{entry.owner_name}</div>
            {entry.reason && <p className="text-gray-300 mt-1">{entry.reason}</p>}
          </div>
        </div>
      ))}
    </div>
  )
}

export default function Rules() {
  const [tab, setTab] = useState('rules')
  const [categories, setCategories] = useState([])
  const [pending, setPending] = useState([])
  const [shitlist, setShitlist] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      fetch('/api/rules').then(r => r.json()),
      fetch('/api/rules/pending').then(r => r.json()),
      fetch('/api/rules/shitlist').then(r => r.json()),
    ])
      .then(([rules, pendingChanges, shitlistEntries]) => {
        setCategories(rules)
        setPending(pendingChanges)
        setShitlist(shitlistEntries)
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }, [])

  return (
    <div>
      <h1 className="text-3xl font-bold text-white mb-2">
        Assistant to the Vice Principal Commissioner Vinny's Office
      </h1>
      <p className="text-gray-400 mb-6">
        The official rules of Lions Power 3, proposed changes on the table for next season, and
        who's currently on the commissioner's bad side. All of it is managed by the commissioner
        through Gabe in the group chat.
      </p>

      <div className="flex gap-2 border-b border-gray-700 mb-6">
        {TABS.map(({ key, label }) => (
          <button
            key={key}
            type="button"
            onClick={() => setTab(key)}
            className={`px-4 py-2 text-sm font-medium rounded-t-md transition-colors ${
              tab === key
                ? 'bg-gray-900 text-green-400 border border-b-0 border-gray-700'
                : 'text-gray-400 hover:text-white'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {loading ? (
        <p className="text-center py-16 text-gray-500">Loading...</p>
      ) : (
        <>
          {tab === 'rules' && <RulesTab categories={categories} />}
          {tab === 'pending' && <PendingTab pending={pending} />}
          {tab === 'shitlist' && <ShitlistTab shitlist={shitlist} />}
        </>
      )}
    </div>
  )
}
