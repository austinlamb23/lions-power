import { useEffect, useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  flexRender,
} from '@tanstack/react-table'

const VIEW_MODES = [
  { value: 'manager', label: 'Manager' },
  { value: 'team', label: 'Team' },
]

const GAME_TYPES = [
  { value: 'regular', label: 'Regular Season' },
  { value: 'playoff', label: 'Playoffs' },
  { value: 'all', label: 'All Games' },
]

function GameTypeTab({ value, label, active, onClick }) {
  return (
    <button
      onClick={() => onClick(value)}
      className={`px-4 py-1.5 rounded-full text-sm font-medium transition-colors ${
        active
          ? 'bg-green-700 text-white'
          : 'text-gray-400 hover:text-white hover:bg-gray-700'
      }`}
    >
      {label}
    </button>
  )
}

function SortIcon({ sorted }) {
  if (!sorted) return <span className="text-gray-600 ml-1">⇅</span>
  return <span className="text-green-400 ml-1">{sorted === 'asc' ? '↑' : '↓'}</span>
}

export default function Almanac() {
  const navigate = useNavigate()
  const [viewMode, setViewMode] = useState('manager')
  const [gameType, setGameType] = useState('regular')
  const [yearMode, setYearMode] = useState('all') // 'all' | 'single' | 'range'
  const [yearSingle, setYearSingle] = useState('')
  const [yearFrom, setYearFrom] = useState('')
  const [yearTo, setYearTo] = useState('')
  const [data, setData] = useState([])
  const [seasons, setSeasons] = useState([])
  const [sorting, setSorting] = useState([{ id: 'total_wins', desc: true }])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (viewMode === 'team') setYearMode('all')
  }, [viewMode])

  useEffect(() => {
    fetch('/api/almanac/seasons')
      .then(r => r.json())
      .then(data => {
        setSeasons(data)
        if (data.length > 0) {
          setYearSingle(String(data[0].year))
          setYearTo(String(data[0].year))
          setYearFrom(String(data[data.length - 1].year))
        }
      })
  }, [])

  useEffect(() => {
    setLoading(true)
    const params = new URLSearchParams({ game_type: gameType })

    let url
    if (viewMode === 'team') {
      url = `/api/almanac/standings/teams?${params}`
    } else if (yearMode === 'single' && yearSingle) {
      url = `/api/almanac/standings?${params}&year=${yearSingle}`
    } else if (yearMode === 'range' && yearFrom && yearTo) {
      url = `/api/almanac/standings/summary?${params}&year_from=${yearFrom}&year_to=${yearTo}`
    } else {
      url = `/api/almanac/standings/summary?${params}`
    }

    fetch(url)
      .then(r => r.json())
      .then(rows => { setData(rows); setLoading(false) })
      .catch(() => setLoading(false))
  }, [viewMode, gameType, yearMode, yearSingle, yearFrom, yearTo])

  const isSummary = yearMode === 'all' || yearMode === 'range'

  const columns = useMemo(() => {
    if (viewMode === 'team') {
      return [
        { accessorKey: 'current_manager', header: 'Current Manager', cell: info => (
          <button
            onClick={() => navigate(`/team/${info.row.original.team_id}`)}
            className="text-green-400 hover:underline font-medium"
          >
            {info.getValue()}
          </button>
        )},
        {
          id: 'seasons',
          header: gameType === 'playoff' ? 'Playoffs' : 'Seasons',
          accessorFn: row => gameType === 'playoff' ? row.playoff_appearances : row.seasons,
        },
        {
          accessorKey: 'championships',
          header: '🏆',
          cell: info => (
            <>
              {info.getValue()}
              {info.row.original.legacy_championships > 0 && <span className="text-gray-500">*</span>}
            </>
          ),
        },
        ...(gameType !== 'playoff' ? [{ accessorKey: 'last_place', header: '🥒' }] : []),
        ...(gameType !== 'playoff' ? [
          {
            id: 'playoff_appearances',
            header: 'Playoffs',
            accessorFn: row => row.playoff_appearances,
          },
          {
            id: 'playoff_pct',
            header: 'Playoff %',
            accessorFn: row => row.seasons > 0
              ? ((row.playoff_appearances / row.seasons) * 100).toFixed(0) + '%'
              : null,
          },
        ] : []),
        {
          id: 'total_wins',
          header: 'W',
          accessorFn: row => gameType === 'regular' ? row.reg_wins
            : gameType === 'playoff' ? row.playoff_wins
            : row.total_wins,
        },
        {
          id: 'total_losses',
          header: 'L',
          accessorFn: row => gameType === 'regular' ? row.reg_losses
            : gameType === 'playoff' ? row.playoff_losses
            : row.total_losses,
        },
        {
          id: 'win_pct',
          header: 'Win%',
          accessorFn: row => {
            const w = gameType === 'regular' ? row.reg_wins : gameType === 'playoff' ? row.playoff_wins : row.total_wins
            const l = gameType === 'regular' ? row.reg_losses : gameType === 'playoff' ? row.playoff_losses : row.total_losses
            const t = gameType === 'regular' ? row.reg_ties : 0
            if (!w && !l) return null
            return ((w / (w + l + (t || 0))) * 100).toFixed(1) + '%'
          },
        },
        ...(gameType !== 'playoff' ? [{
          id: 'ties',
          header: 'T',
          accessorFn: row => row.reg_ties,
        }] : []),
        {
          id: 'pts_for',
          header: gameType === 'playoff' ? 'Pts For *' : 'Pts For',
          accessorFn: row => gameType === 'regular' ? row.reg_points : gameType === 'playoff' ? row.playoff_points : row.total_points,
          cell: info => info.getValue()?.toLocaleString(),
        },
        ...(gameType !== 'playoff' ? [{
          id: 'pps',
          header: 'Pts/Season',
          accessorFn: row => {
            const pts = gameType === 'regular' ? row.reg_points : row.total_points
            return row.seasons > 0 ? (pts / row.seasons).toFixed(1) : null
          },
        }] : []),
        {
          id: 'ppg',
          header: gameType === 'playoff' ? 'PPG *' : 'PPG',
          accessorFn: row => {
            const pts = gameType === 'regular' ? row.reg_points : gameType === 'playoff' ? row.playoff_points : row.total_points
            const games = gameType === 'regular' ? row.reg_wins + row.reg_losses + (row.reg_ties || 0)
              : gameType === 'playoff' ? row.playoff_games
              : row.total_wins + row.total_losses + (row.total_ties || 0)
            return games > 0 ? (pts / games).toFixed(1) : null
          },
        },
      ]
    }

    if (isSummary) {
      return [
        { accessorKey: 'owner_name', header: 'Manager', cell: info => (
          <button
            onClick={() => navigate(`/owner/${encodeURIComponent(info.getValue())}`)}
            className="text-green-400 hover:underline font-medium"
          >
            {info.getValue()}
          </button>
        )},
        {
          id: 'seasons',
          header: gameType === 'playoff' ? 'Playoffs' : 'Seasons',
          accessorFn: row => gameType === 'playoff' ? row.playoff_appearances : row.seasons,
        },
        {
          accessorKey: 'championships',
          header: '🏆',
          cell: info => (
            <>
              {info.getValue()}
              {info.row.original.legacy_championships > 0 && <span className="text-gray-500">*</span>}
            </>
          ),
        },
        ...(gameType !== 'playoff' ? [{ accessorKey: 'last_place', header: '🥒' }] : []),
        ...(gameType !== 'playoff' ? [
          {
            id: 'playoff_appearances',
            header: 'Playoffs',
            accessorFn: row => row.playoff_appearances,
          },
          {
            id: 'playoff_pct',
            header: 'Playoff %',
            accessorFn: row => row.seasons > 0
              ? ((row.playoff_appearances / row.seasons) * 100).toFixed(0) + '%'
              : null,
          },
        ] : []),
        {
          id: 'total_wins',
          header: 'W',
          accessorFn: row => gameType === 'regular' ? row.reg_wins
            : gameType === 'playoff' ? row.playoff_wins
            : row.total_wins,
        },
        {
          id: 'total_losses',
          header: 'L',
          accessorFn: row => gameType === 'regular' ? row.reg_losses
            : gameType === 'playoff' ? row.playoff_losses
            : row.total_losses,
        },
        {
          id: 'win_pct',
          header: 'Win%',
          accessorFn: row => {
            const w = gameType === 'regular' ? row.reg_wins : gameType === 'playoff' ? row.playoff_wins : row.total_wins
            const l = gameType === 'regular' ? row.reg_losses : gameType === 'playoff' ? row.playoff_losses : row.total_losses
            const t = gameType === 'regular' ? row.reg_ties : gameType === 'playoff' ? 0 : row.total_ties
            if (!w && !l) return null
            return ((w / (w + l + (t || 0))) * 100).toFixed(1) + '%'
          },
        },
        ...(gameType !== 'playoff' ? [{
          id: 'ties',
          header: 'T',
          accessorFn: row => row.reg_ties ?? row.total_ties,
        }] : []),
        {
          id: 'pts_for',
          header: gameType === 'playoff' ? 'Pts For *' : 'Pts For',
          accessorFn: row => gameType === 'regular' ? row.reg_points : gameType === 'playoff' ? row.playoff_points : row.total_points,
          cell: info => info.getValue()?.toLocaleString(),
        },
        ...(gameType !== 'playoff' ? [{
          id: 'pps',
          header: 'Pts/Season',
          accessorFn: row => {
            const pts = gameType === 'regular' ? row.reg_points : row.total_points
            return row.seasons > 0 ? (pts / row.seasons).toFixed(1) : null
          },
        }] : []),
        {
          id: 'ppg',
          header: gameType === 'playoff' ? 'PPG *' : 'PPG',
          accessorFn: row => {
            const pts = gameType === 'regular' ? row.reg_points : gameType === 'playoff' ? row.playoff_points : row.total_points
            const games = gameType === 'regular' ? row.reg_wins + row.reg_losses + (row.reg_ties || 0)
              : gameType === 'playoff' ? row.playoff_games
              : row.total_wins + row.total_losses + (row.total_ties || 0)
            return games > 0 ? (pts / games).toFixed(1) : null
          },
        },
      ]
    }
    return [
      { accessorKey: 'year', header: 'Year' },
      { accessorKey: 'owner_name', header: 'Manager', cell: info => (
        <button
          onClick={() => navigate(`/owner/${encodeURIComponent(info.getValue())}`)}
          className="text-green-400 hover:underline font-medium"
        >
          {info.getValue()}
        </button>
      )},
      { accessorKey: 'team_name', header: 'Team Name' },
      { accessorKey: 'wins', header: 'W' },
      { accessorKey: 'losses', header: 'L' },
      { accessorKey: 'ties', header: 'T' },
      { accessorKey: 'win_pct', header: 'Win%', cell: info => info.getValue() != null ? (info.getValue() * 100).toFixed(1) + '%' : '—' },
      {
        id: 'pts_for',
        header: 'Pts For',
        accessorFn: row => gameType === 'regular' ? row.reg_points : gameType === 'playoff' ? row.playoff_points : row.total_points,
        cell: info => info.getValue()?.toLocaleString() ?? '—',
      },
      {
        id: 'ppg',
        header: 'PPG',
        accessorFn: row => {
          const pts = gameType === 'regular' ? row.reg_points : gameType === 'playoff' ? row.playoff_points : row.total_points
          const games = gameType === 'regular' ? row.wins + row.losses + (row.ties || 0)
            : gameType === 'playoff' ? (row.playoff_wins || 0) + (row.playoff_losses || 0)
            : row.wins + row.losses + (row.ties || 0) + (row.playoff_wins || 0) + (row.playoff_losses || 0)
          return pts && games > 0 ? (pts / games).toFixed(1) : null
        },
      },
      { accessorKey: 'final_standing', header: 'Finish' },
    ]
  }, [viewMode, isSummary, yearMode, gameType, navigate])

  const table = useReactTable({
    data,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  })

  return (
    <div>
      <h1 className="text-3xl font-bold text-white mb-4">League Almanac</h1>

      {/* Quick links to Almanac subpages */}
      <div className="flex flex-wrap gap-2 mb-6">
        {[
          { to: '/h2h', label: 'Head-to-Head' },
          { to: '/draft-data', label: 'Draft Data' },
          { to: '/east-vs-west', label: 'East vs West' },
          { to: '/transactions', label: 'Transactions' },
          { to: '/draft-intel', label: 'Draft Intel' },
        ].map(l => (
          <button
            key={l.to}
            onClick={() => navigate(l.to)}
            className="px-3 py-1.5 rounded-full text-xs font-medium border border-gray-700 text-gray-400 hover:text-white hover:bg-gray-700 transition-colors"
          >
            {l.label} →
          </button>
        ))}
      </div>

      {/* Controls */}
      <div className="flex flex-wrap items-center gap-4 mb-6">
        {/* Manager / Team toggle */}
        <div className="flex gap-1 bg-gray-800 p-1 rounded-full border border-gray-600">
          {VIEW_MODES.map(m => (
            <GameTypeTab key={m.value} {...m} active={viewMode === m.value} onClick={setViewMode} />
          ))}
        </div>

        <div className="w-px h-6 bg-gray-600" />

        <div className="flex gap-1 bg-gray-800 p-1 rounded-full">
          {GAME_TYPES.map(g => (
            <GameTypeTab key={g.value} {...g} active={gameType === g.value} onClick={setGameType} />
          ))}
        </div>

        {viewMode === 'manager' && (
          <div className="flex items-center gap-2">
            <select
              value={yearMode}
              onChange={e => setYearMode(e.target.value)}
              className="bg-gray-800 text-gray-200 border border-gray-600 rounded-md px-3 py-1.5 text-sm"
            >
              <option value="all">All Years</option>
              <option value="single">Single Year</option>
              <option value="range">Year Range</option>
            </select>
            {yearMode === 'single' && (
              <select
                value={yearSingle}
                onChange={e => setYearSingle(e.target.value)}
                className="bg-gray-800 text-gray-200 border border-gray-600 rounded-md px-3 py-1.5 text-sm"
              >
                {seasons.map(s => (
                  <option key={s.year} value={s.year}>{s.year}</option>
                ))}
              </select>
            )}
            {yearMode === 'range' && (
              <>
                <select
                  value={yearFrom}
                  onChange={e => setYearFrom(e.target.value)}
                  className="bg-gray-800 text-gray-200 border border-gray-600 rounded-md px-3 py-1.5 text-sm"
                >
                  {seasons.slice().reverse().map(s => (
                    <option key={s.year} value={s.year}>{s.year}</option>
                  ))}
                </select>
                <span className="text-gray-400 text-sm">–</span>
                <select
                  value={yearTo}
                  onChange={e => setYearTo(e.target.value)}
                  className="bg-gray-800 text-gray-200 border border-gray-600 rounded-md px-3 py-1.5 text-sm"
                >
                  {seasons.map(s => (
                    <option key={s.year} value={s.year}>{s.year}</option>
                  ))}
                </select>
              </>
            )}
          </div>
        )}
      </div>

      {/* Table */}
      <div className="overflow-x-auto rounded-xl border border-gray-700">
        <table className="w-full text-sm">
          <thead className="bg-gray-800 text-gray-400 uppercase text-xs tracking-wider">
            {table.getHeaderGroups().map(hg => (
              <tr key={hg.id}>
                {hg.headers.map(header => (
                  <th
                    key={header.id}
                    onClick={header.column.getToggleSortingHandler()}
                    className="px-4 py-3 text-left cursor-pointer select-none hover:text-white transition-colors"
                  >
                    {flexRender(header.column.columnDef.header, header.getContext())}
                    <SortIcon sorted={header.column.getIsSorted()} />
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody className="divide-y divide-gray-800">
            {loading ? (
              <tr><td colSpan={10} className="text-center py-12 text-gray-500">Loading...</td></tr>
            ) : table.getRowModel().rows.map((row, i) => (
              <tr key={row.id} className={i % 2 === 0 ? 'bg-gray-900' : 'bg-gray-950'}>
                {row.getVisibleCells().map(cell => (
                  <td key={cell.id} className="px-4 py-3 text-gray-200">
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {data.some(row => row.legacy_championships > 0) && (
        <p className="mt-3 text-xs text-gray-600">
          * 🏆 count includes a pre-history championship (2011/2012) — honored based on league legend and oral history only, not statistically verified like 2013+.
        </p>
      )}
    </div>
  )
}
