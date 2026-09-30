import { MotionConfig } from 'motion/react'
import { lazy, Suspense, type ReactNode } from 'react'
import { createBrowserRouter, Link, Navigate, RouterProvider, useLocation } from 'react-router-dom'
import { setUnauthorizedHandler } from './api'
import { Spinner } from './components/ui'
import { getToken } from './lib/auth'
import ChildRun from './pages/ChildRun'
import ChildSetup from './pages/ChildSetup'
import Login from './pages/Login'
import Parent from './pages/Parent'

// Teacher pages carry the chart and QR libraries; children's phones never load them.
const TeacherDashboard = lazy(() => import('./pages/TeacherDashboard'))
const ChildReport = lazy(() => import('./pages/ChildReport'))
// The landing page is for visitors; a child's phone goes straight to child mode.
const Home = lazy(() => import('./pages/Home'))
const Practice = lazy(() => import('./pages/Practice'))

// An expired or rejected token sends the teacher back to sign in, then to where they were.
setUnauthorizedHandler(() => {
  const here = window.location.pathname + window.location.search
  if (!window.location.pathname.startsWith('/login')) window.location.assign(`/login?next=${encodeURIComponent(here)}`)
})

function Lazy({ children }: { children: ReactNode }) {
  return (
    <Suspense
      fallback={
        <main className="p-8">
          <Spinner label="Loading" />
        </main>
      }
    >
      {children}
    </Suspense>
  )
}

/** Teacher and child-mode pages need a signed-in teacher. */
function RequireTeacher({ children }: { children: ReactNode }) {
  const location = useLocation()
  if (!getToken()) return <Navigate to={`/login?next=${encodeURIComponent(location.pathname + location.search)}`} replace />
  return <>{children}</>
}

function NotFound() {
  return (
    <main className="p-8">
      <p className="mb-3">Page not found.</p>
      <Link className="font-bold text-primary" to="/">
        Back to Akshar home
      </Link>
    </main>
  )
}

const router = createBrowserRouter([
  { path: '/', element: <Lazy><Home /></Lazy> },
  { path: '/login', element: <Login /> },
  { path: '/p/:token', element: <Parent /> },
  // Practice games need no login: the parent link's token only picks which games come first.
  { path: '/practice', element: <Lazy><Practice /></Lazy> },
  { path: '/practice/:token', element: <Lazy><Practice /></Lazy> },
  { path: '/child', element: <RequireTeacher><ChildSetup /></RequireTeacher> },
  { path: '/child/run/:sessionId', element: <RequireTeacher><ChildRun /></RequireTeacher> },
  { path: '/teacher', element: <RequireTeacher><Lazy><TeacherDashboard /></Lazy></RequireTeacher> },
  { path: '/teacher/child/:childId', element: <RequireTeacher><Lazy><ChildReport /></Lazy></RequireTeacher> },
  { path: '*', element: <NotFound /> },
])

export default function App() {
  // Respect the device's reduced-motion setting for every animation.
  return (
    <MotionConfig reducedMotion="user">
      <RouterProvider router={router} />
    </MotionConfig>
  )
}
