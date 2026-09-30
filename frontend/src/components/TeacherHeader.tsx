import { MicrophoneIcon, SignOutIcon, UsersThreeIcon } from '@phosphor-icons/react'
import { motion } from 'motion/react'
import { Link, NavLink, useNavigate } from 'react-router-dom'
import { signOut } from '../lib/auth'
import { Owl } from './child'

const tabs = [
  { to: '/teacher', label: 'Class', icon: UsersThreeIcon, end: true },
  { to: '/child', label: 'Screen a child', icon: MicrophoneIcon, end: false },
]

/** Shared header for teacher pages: brand, the two teacher tasks, sign out. */
export function TeacherHeader() {
  const navigate = useNavigate()
  return (
    <header className="sticky top-0 z-20 border-b border-outline/50 bg-surface/90 backdrop-blur-sm">
      <div className="mx-auto flex h-16 max-w-[1200px] items-center gap-6 px-4 md:px-8">
        <Link to="/" className="flex items-center gap-2.5">
          <Owl size={34} />
          <span className="font-display text-xl font-semibold text-primary">Akshar</span>
        </Link>
        <nav aria-label="Teacher" className="flex items-center gap-1">
          {tabs.map(({ to, label, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end} className="relative rounded-[10px] px-3 py-2 text-sm font-bold">
              {({ isActive }) => (
                <>
                  {isActive && (
                    <motion.span
                      layoutId="teacher-tab"
                      className="absolute inset-0 rounded-[10px] bg-primary-container"
                      transition={{ type: 'spring', stiffness: 500, damping: 40 }}
                    />
                  )}
                  <span className={`relative flex items-center gap-2 ${isActive ? 'text-on-primary-container' : 'text-ink-muted hover:text-ink'}`}>
                    <Icon size={18} weight={isActive ? 'fill' : 'regular'} aria-hidden />
                    <span className="hidden sm:inline">{label}</span>
                  </span>
                </>
              )}
            </NavLink>
          ))}
        </nav>
        <button
          type="button"
          onClick={() => {
            signOut()
            navigate('/login')
          }}
          className="ml-auto flex items-center gap-2 rounded-[10px] px-3 py-2 text-sm font-bold text-ink-muted hover:bg-surface-container hover:text-ink"
        >
          <SignOutIcon size={18} aria-hidden />
          <span className="hidden sm:inline">Sign out</span>
        </button>
      </div>
    </header>
  )
}
