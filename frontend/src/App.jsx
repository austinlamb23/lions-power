import { useState } from 'react'
import { Routes, Route, NavLink, Link } from 'react-router-dom'
import logo from './assets/lp3.jpeg'
import Home from './pages/Home'
import Almanac from './pages/Almanac'
import OwnerProfile from './pages/OwnerProfile'
import TeamProfile from './pages/TeamProfile'
import OwnerH2H from './pages/OwnerH2H'
import TeamH2H from './pages/TeamH2H'
import Hangman from './pages/Hangman'
import NameMatch from './pages/NameMatch'
import DraftMatch from './pages/DraftMatch'
import Games from './pages/Games'
import HallOfFame from './pages/HallOfFame'
import WallOfShame from './pages/WallOfShame'
import PowerRankings from './pages/PowerRankings'
import Pod from './pages/Pod'
import DraftIntel from './pages/DraftIntel'
import H2HPicker from './pages/H2HPicker'
import DraftData from './pages/DraftData'
import EastVsWest from './pages/EastVsWest'
import Transactions from './pages/Transactions'
import Punishments from './pages/Punishments'
import Rules from './pages/Rules'
import Forums from './pages/Forums'
import ForumPost from './pages/ForumPost'
import ForumNewPost from './pages/ForumNewPost'
import GameRoom from './pages/GameRoom'
import WeeklyPredictions from './pages/WeeklyPredictions'
import AllStarRoster from './pages/AllStarRoster'
import SideBets from './pages/SideBets'
import PodRoomGrades from './pages/PodRoomGrades'

const NAV_LINKS = [
  { to: '/', end: true, label: 'Home' },
  { to: '/almanac', label: 'Almanac' },
  { to: '/game-room', label: 'Game Room' },
  { to: '/hall-of-fame', label: 'Hall of Fame' },
  { to: '/wall-of-shame', label: 'Wall of Shame' },
  { to: '/power-rankings', label: 'Power Rankings' },
  { to: '/the-pod', label: 'The Pod' },
  { to: '/punishments', label: 'Punishments' },
  { to: '/side-bets', label: 'Side Bets' },
  { to: '/forums', label: 'Forums' },
  { to: '/rules', label: "Commissioner's Office" },
]

function Nav() {
  const [open, setOpen] = useState(false)
  const base = 'px-4 py-2 rounded-md text-sm font-medium transition-colors whitespace-nowrap'
  const active = `${base} bg-green-700 text-white`
  const inactive = `${base} text-gray-300 hover:text-white hover:bg-gray-700`
  const mobileBase = 'block w-full px-4 py-3 rounded-md text-base font-medium transition-colors'
  const mobileActive = `${mobileBase} bg-green-700 text-white`
  const mobileInactive = `${mobileBase} text-gray-300 hover:text-white hover:bg-gray-700`

  return (
    <nav className="bg-gray-900 border-b border-gray-700">
      <div className="px-4 sm:px-6 py-3 flex items-center justify-between gap-4">
        <span className="flex items-center gap-3 min-w-0">
          <img
            src={logo}
            alt="Lions Power 3"
            className="w-11 h-11 rounded-full ring-2 ring-green-700 shrink-0"
          />
          <span
            className="text-green-400 font-bold text-lg tracking-wide truncate"
            style={{ fontFamily: 'var(--heading)' }}
          >
            Lions Power 3
          </span>
        </span>

        <div className="hidden md:flex items-center gap-6">
          {NAV_LINKS.map(({ to, end, label }) => (
            <NavLink key={to} to={to} end={end} className={({ isActive }) => isActive ? active : inactive}>
              {label}
            </NavLink>
          ))}
        </div>

        <button
          type="button"
          onClick={() => setOpen(o => !o)}
          aria-label={open ? 'Close menu' : 'Open menu'}
          aria-expanded={open}
          className="md:hidden shrink-0 p-2 rounded-md text-gray-300 hover:text-white hover:bg-gray-700"
        >
          {open ? (
            <svg xmlns="http://www.w3.org/2000/svg" className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          ) : (
            <svg xmlns="http://www.w3.org/2000/svg" className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          )}
        </button>
      </div>

      {open && (
        <div className="md:hidden px-4 pb-4 flex flex-col gap-1 border-t border-gray-700 pt-3">
          {NAV_LINKS.map(({ to, end, label }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              onClick={() => setOpen(false)}
              className={({ isActive }) => isActive ? mobileActive : mobileInactive}
            >
              {label}
            </NavLink>
          ))}
        </div>
      )}
    </nav>
  )
}

export default function App() {
  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      <Nav />
      <main className="max-w-7xl mx-auto px-4 py-8">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/almanac" element={<Almanac />} />
          <Route path="/owner/:name" element={<OwnerProfile />} />
          <Route path="/owner/:name/h2h/:opponent" element={<OwnerH2H />} />
          <Route path="/team/:teamId" element={<TeamProfile />} />
          <Route path="/team/:teamId/h2h/:opponentId" element={<TeamH2H />} />
          <Route path="/games" element={<Games />} />
          <Route path="/games/hangman" element={<Hangman />} />
          <Route path="/games/name-match" element={<NameMatch />} />
          <Route path="/games/draft-match" element={<DraftMatch />} />
          <Route path="/hall-of-fame" element={<HallOfFame />} />
          <Route path="/wall-of-shame" element={<WallOfShame />} />
          <Route path="/power-rankings" element={<PowerRankings />} />
          <Route path="/the-pod" element={<Pod />} />
          <Route path="/the-pod/room-grades" element={<PodRoomGrades />} />
          <Route path="/draft-intel" element={<DraftIntel />} />
          <Route path="/h2h" element={<H2HPicker />} />
          <Route path="/draft-data" element={<DraftData />} />
          <Route path="/east-vs-west" element={<EastVsWest />} />
          <Route path="/transactions" element={<Transactions />} />
          <Route path="/punishments" element={<Punishments />} />
          <Route path="/side-bets" element={<SideBets />} />
          <Route path="/forums" element={<Forums />} />
          <Route path="/forums/new" element={<ForumNewPost />} />
          <Route path="/forums/:postId" element={<ForumPost />} />
          <Route path="/game-room" element={<GameRoom />} />
          <Route path="/game-room/predictions" element={<WeeklyPredictions />} />
          <Route path="/game-room/all-star-roster" element={<AllStarRoster />} />
          <Route path="/rules" element={<Rules />} />
        </Routes>
      </main>
    </div>
  )
}
