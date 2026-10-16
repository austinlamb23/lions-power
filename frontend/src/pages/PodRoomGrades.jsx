import { useEffect, useState } from 'react'
import { AUTH_KEY, loadAuth, parseError, LoginForm } from '../components/OwnerLogin'

function GradeSelect({ value, scale, onChange }) {
  return (
    <select
      value={value || ''}
      onChange={e => onChange(e.target.value)}
      className={`bg-gray-800 border border-gray-600 rounded-md px-2 py-1.5 text-sm w-full ${
        value ? 'text-green-300 font-semibold' : 'text-gray-500'
      }`}
    >
      <option value="">—</option>
      {scale.map(g => <option key={g} value={g}>{g}</option>)}
    </select>
  )
}

// Every grader's row for this cell: yours is the only one that's ever
// editable (an actual <select>) -- everyone else's is always plain,
// read-only text, even though the backend already refuses to let you submit
// under anyone else's name regardless of what the UI shows. Missing graders
// still get a row (—), not omitted, so it's visually obvious who hasn't
// weighed in yet on this team/category.
function GradeCell({ myOwner, myValue, graders, categoryGrades, scale, onChangeMine }) {
  // "You" always first -- your own row is the one worth finding fastest.
  const ordered = [myOwner, ...graders.filter(o => o !== myOwner)]
  return (
    <div className="space-y-1 min-w-[130px]">
      {ordered.map(owner => {
        const isMe = owner === myOwner
        // Mine comes from local state (reflects an unsaved pending edit,
        // not just whatever was last saved) -- everyone else's only ever
        // exists as already-saved server data, so categoryGrades is right
        // for them.
        const grade = isMe ? myValue : categoryGrades[owner]
        return (
          <div key={owner} className="flex items-center gap-1.5">
            <span className={`text-[11px] w-16 flex-shrink-0 truncate ${isMe ? 'text-gray-300 font-semibold' : 'text-gray-600'}`}>
              {isMe ? 'You' : owner.split(' ')[0]}
            </span>
            {isMe ? (
              <GradeSelect value={grade} scale={scale} onChange={onChangeMine} />
            ) : (
              <span className={`text-xs ${grade ? 'text-gray-300 font-medium' : 'text-gray-700'}`}>
                {grade || '—'}
              </span>
            )}
          </div>
        )
      })}
    </div>
  )
}

export default function PodRoomGrades() {
  const [auth, setAuth] = useState(loadAuth)
  const [graders, setGraders] = useState([])
  const [categories, setCategories] = useState([])
  const [gradeScale, setGradeScale] = useState([])
  const [year, setYear] = useState(null)
  const [data, setData] = useState(null)
  const [myGrades, setMyGrades] = useState({})
  const [forbidden, setForbidden] = useState(false)
  const [error, setError] = useState('')
  const [status, setStatus] = useState('')

  const authHeaders = auth ? { Authorization: `Bearer ${auth.token}` } : {}

  useEffect(() => {
    fetch('/api/pod-grades/graders').then(r => r.json()).then(d => {
      setGraders(d.graders)
      setCategories(d.categories)
      setGradeScale(d.grade_scale)
    })
    fetch('/api/power-rankings/current-week').then(r => r.json()).then(d => setYear(d.year))
  }, [])

  function loadGrades() {
    if (!auth || !year) return
    setForbidden(false)
    fetch(`/api/pod-grades/${year}`, { headers: authHeaders })
      .then(r => {
        if (r.status === 403) { setForbidden(true); throw new Error('') }
        if (!r.ok) throw new Error('Failed to load')
        return r.json()
      })
      .then(d => { setData(d); setMyGrades(d.my_grades || {}) })
      .catch(err => { if (err.message) setError(err.message) })
  }

  useEffect(loadGrades, [auth, year])

  function updateGrade(teamId, category, grade) {
    setMyGrades(prev => ({
      ...prev,
      [teamId]: { ...prev[teamId], [category]: grade },
    }))
    setStatus('')
  }

  function handleLogout() {
    localStorage.removeItem(AUTH_KEY)
    setAuth(null)
    setData(null)
  }

  function handleSave() {
    const grades = []
    for (const [teamId, byCategory] of Object.entries(myGrades)) {
      for (const [category, grade] of Object.entries(byCategory)) {
        if (grade) grades.push({ team_id: Number(teamId), category, grade })
      }
    }
    setError('')
    setStatus('Saving...')
    fetch(`/api/pod-grades/${year}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders },
      body: JSON.stringify({ grades }),
    })
      .then(async r => {
        if (!r.ok) throw new Error(await parseError(r))
        setStatus('Saved!')
        loadGrades()
      })
      .catch(err => { setError(err.message); setStatus('') })
  }

  return (
    <div className="max-w-4xl mx-auto">
      <h1 className="text-3xl font-bold text-white mb-2" style={{ fontFamily: 'var(--heading)' }}>
        Room Grades
      </h1>
      <p className="text-gray-400 text-sm mb-8">
        Crew-only prep for the pod — grade every team's QB, RB, WR, and TE room plus their bench.
        Everyone here sees everyone's grades as they come in.
      </p>

      {!auth && (
        <div className="mb-8">
          <LoginForm owners={graders} onLoggedIn={setAuth} helpText="Log in to grade — crew only." />
        </div>
      )}

      {auth && forbidden && (
        <div className="rounded-lg border-2 border-red-500 bg-red-950/70 px-4 py-3 text-center">
          <p className="text-red-300 font-bold">Not on the list for this one</p>
          <p className="text-red-400 text-xs mt-1">
            Room Grades is limited to a few people for this pod segment — logged in as {auth.owner_name}.
          </p>
          <button onClick={handleLogout} className="text-gray-500 hover:text-gray-300 text-xs underline mt-2">
            Log out
          </button>
        </div>
      )}

      {auth && !forbidden && data && (
        <>
          <div className="flex items-center justify-between mb-4">
            <p className="text-gray-500 text-xs">
              Logged in as <span className="text-gray-300 font-medium">{auth.owner_name}</span>
              {data.graders_started.length > 0 && (
                <span className="text-gray-600"> · {data.graders_started.length}/{graders.length} started grading</span>
              )}
            </p>
            <button onClick={handleLogout} className="text-gray-500 hover:text-gray-300 text-xs underline">
              Log out
            </button>
          </div>

          {error && <p className="text-red-400 text-sm mb-3">{error}</p>}

          <div className="overflow-x-auto rounded-xl border border-gray-700 bg-gray-900">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="border-b border-gray-800">
                  <th className="text-left text-gray-400 font-medium px-3 py-2 whitespace-nowrap">Team</th>
                  {categories.map(c => (
                    <th key={c} className="text-left text-gray-400 font-medium px-3 py-2">{c}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.teams.map(t => (
                  <tr key={t.team_id} className="border-b border-gray-800 last:border-0">
                    <td className="px-3 py-2 align-top whitespace-nowrap">
                      <p className="text-gray-200 font-medium">{t.owner_name}</p>
                      <p className="text-gray-600 text-xs">{t.team_name}</p>
                    </td>
                    {categories.map(category => (
                      <td key={category} className="px-3 py-2 align-top">
                        <GradeCell
                          myOwner={auth.owner_name}
                          myValue={myGrades[t.team_id]?.[category]}
                          graders={graders}
                          categoryGrades={t.grades[category] || {}}
                          scale={gradeScale}
                          onChangeMine={grade => updateGrade(t.team_id, category, grade)}
                        />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {status && <p className="text-green-400 text-sm mt-3">{status}</p>}

          <button
            onClick={handleSave}
            className="mt-4 w-full sm:w-auto bg-green-700 hover:bg-green-600 text-white rounded-md px-6 py-2.5 text-sm font-semibold transition-colors"
          >
            Save my grades
          </button>
        </>
      )}
    </div>
  )
}
