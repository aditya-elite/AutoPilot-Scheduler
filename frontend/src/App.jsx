import { Suspense, lazy } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './context/AuthContext.jsx'
import Sidebar from './components/Sidebar.jsx'
import Login from './pages/Login.jsx'
import LandingPage from './pages/LandingPage.jsx'
import ManagerDashboard from './pages/ManagerDashboard.jsx'
import OperatorView from './pages/OperatorView.jsx'

const Analytics = lazy(() => import('./pages/Analytics.jsx'))
const Admin = lazy(() => import('./pages/Admin.jsx'))
const MachinesCRUD = lazy(() => import('./pages/MachinesCRUD.jsx'))
const JobsCRUD = lazy(() => import('./pages/JobsCRUD.jsx'))
const ScenarioComparison = lazy(() => import('./pages/ScenarioComparison.jsx'))
const AICopilot = lazy(() => import('./pages/AICopilot.jsx'))
const Settings = lazy(() => import('./pages/Settings.jsx'))

function AuroraBackdrop() {
  return (
    <div className="aurora-backdrop" aria-hidden="true">
      <div className="aurora-blob b1" />
      <div className="aurora-blob b2" />
      <div className="aurora-blob b3" />
    </div>
  )
}

function ProtectedLayout({ children }) {
  const { user } = useAuth()
  if (!user) return <Navigate to="/login" replace />
  return (
    <div className="app-shell">
      <Sidebar />
      <div className="main-content">{children}</div>
    </div>
  )
}

export default function App() {
  const { user } = useAuth()
  const isManager = user?.role === 'factory_manager' || user?.role === 'admin'

  return (
    <>
      <AuroraBackdrop />
      <Routes>
        <Route path="/login" element={user ? <Navigate to="/" replace /> : <Login />} />
        <Route
          path="/"
          element={
            user ? (
              <ProtectedLayout>
                {isManager ? <ManagerDashboard /> : <OperatorView />}
              </ProtectedLayout>
            ) : (
              <LandingPage />
            )
          }
        />
        <Route
          path="/analytics"
          element={
            <ProtectedLayout>
              <Suspense fallback={<div className="text-secondary">Loading analytics…</div>}>
                <Analytics />
              </Suspense>
            </ProtectedLayout>
          }
        />
        <Route
          path="/machines"
          element={
            <ProtectedLayout>
              {isManager ? (
                <Suspense fallback={<div className="text-secondary">Loading machines…</div>}>
                  <MachinesCRUD />
                </Suspense>
              ) : (
                <Navigate to="/" replace />
              )}
            </ProtectedLayout>
          }
        />
        <Route
          path="/jobs"
          element={
            <ProtectedLayout>
              {isManager ? (
                <Suspense fallback={<div className="text-secondary">Loading jobs…</div>}>
                  <JobsCRUD />
                </Suspense>
              ) : (
                <Navigate to="/" replace />
              )}
            </ProtectedLayout>
          }
        />
        <Route
          path="/compare"
          element={
            <ProtectedLayout>
              {isManager ? (
                <Suspense fallback={<div className="text-secondary">Loading comparison…</div>}>
                  <ScenarioComparison />
                </Suspense>
              ) : (
                <Navigate to="/" replace />
              )}
            </ProtectedLayout>
          }
        />
        <Route
          path="/copilot"
          element={
            <ProtectedLayout>
              <Suspense fallback={<div className="text-secondary">Loading copilot…</div>}>
                <AICopilot />
              </Suspense>
            </ProtectedLayout>
          }
        />
        <Route
          path="/settings"
          element={
            <ProtectedLayout>
              <Suspense fallback={<div className="text-secondary">Loading settings…</div>}>
                <Settings />
              </Suspense>
            </ProtectedLayout>
          }
        />
        <Route
          path="/admin"
          element={
            <ProtectedLayout>
              {user?.role === 'admin' ? (
                <Suspense fallback={<div className="text-secondary">Loading admin…</div>}>
                  <Admin />
                </Suspense>
              ) : (
                <Navigate to="/" replace />
              )}
            </ProtectedLayout>
          }
        />
      </Routes>
    </>
  )
}
