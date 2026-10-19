import { useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'
import { useNotifications } from '../context/NotificationContext.jsx'

const ICONS = {
  gantt: '▤',
  analytics: '◔',
  operator: '☰',
  admin: '◈',
  settings: '⚙',
  logout: '⏻',
  machines: '🔧',
  jobs: '📋',
  compare: '⚖',
  copilot: '🤖',
}

const TYPE_STYLES = {
  success: { color: '#137333', bg: '#e6f4ea', dot: '#34a853' },
  error:   { color: '#c5221f', bg: '#fce8e6', dot: '#ea4335' },
  warning: { color: '#b06000', bg: '#fef7e0', dot: '#fbbc04' },
  info:    { color: '#1a73e8', bg: '#e8f0fe', dot: '#1a73e8' },
}

export default function Sidebar() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const { notifications, clearAll, dismiss } = useNotifications()
  const [showNotifs, setShowNotifs] = useState(false)
  const isManager = user?.role === 'factory_manager' || user?.role === 'admin'
  const isAdmin = user?.role === 'admin'
  const unread = notifications.length

  function handleLogout() {
    logout()
    navigate('/')
  }

  return (
    <aside style={{
      width: 'var(--sidebar-width)',
      padding: '24px 0',
      display: 'flex',
      flexDirection: 'column',
      gap: 4,
      background: '#ffffff',
      borderRight: '1px solid #dadce0',
      height: '100vh',
      position: 'sticky',
      top: 0,
      zIndex: 10,
    }}>
      {/* Brand */}
      <div style={{ padding: '0 24px 22px 24px', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <div style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: 18, color: '#1a73e8', letterSpacing: '-0.02em' }}>
            AutoPilot
          </div>
          <div style={{ fontSize: 11.5, color: '#5f6368', fontWeight: 500, marginTop: 2 }}>
            Scheduler
          </div>
        </div>

        {/* Notification Bell */}
        <div style={{ position: 'relative' }}>
          <button
            onClick={() => setShowNotifs(v => !v)}
            style={{
              background: showNotifs ? '#e8f0fe' : 'transparent',
              border: 'none', cursor: 'pointer',
              width: 32, height: 32, borderRadius: 8,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 16, position: 'relative',
            }}
            title="Notifications"
          >
            🔔
            {unread > 0 && (
              <span style={{
                position: 'absolute', top: 2, right: 2,
                width: 14, height: 14, borderRadius: '50%',
                background: '#d93025', color: '#fff',
                fontSize: 8, fontWeight: 700,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                {unread > 9 ? '9+' : unread}
              </span>
            )}
          </button>

          {/* Dropdown Panel */}
          {showNotifs && (
            <div style={{
              position: 'absolute', top: 38, left: -8,
              width: 280, background: '#fff',
              border: '1px solid #dadce0', borderRadius: 10,
              boxShadow: '0 4px 20px rgba(0,0,0,0.12)',
              zIndex: 100, overflow: 'hidden',
            }}>
              <div style={{ padding: '10px 14px', borderBottom: '1px solid #e8eaed', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: 12.5, fontWeight: 700, color: '#202124' }}>Notifications</span>
                {notifications.length > 0 && (
                  <button onClick={clearAll} style={{ fontSize: 11, color: '#1a73e8', background: 'none', border: 'none', cursor: 'pointer' }}>
                    Clear all
                  </button>
                )}
              </div>

              <div style={{ maxHeight: 320, overflowY: 'auto' }}>
                {notifications.length === 0 ? (
                  <div style={{ padding: '20px 14px', fontSize: 12, color: '#9aa0a6', textAlign: 'center' }}>
                    No notifications yet
                  </div>
                ) : (
                  notifications.map(n => {
                    const s = TYPE_STYLES[n.type] || TYPE_STYLES.info
                    return (
                      <div key={n.id} style={{
                        padding: '9px 14px', borderBottom: '1px solid #f1f3f4',
                        display: 'flex', gap: 10, alignItems: 'flex-start',
                        background: '#fff',
                      }}>
                        <span style={{ width: 7, height: 7, borderRadius: '50%', background: s.dot, marginTop: 4, flexShrink: 0 }} />
                        <div style={{ flex: 1 }}>
                          <div style={{ fontSize: 12, color: '#202124', lineHeight: 1.4 }}>{n.message}</div>
                          <div style={{ fontSize: 10.5, color: '#9aa0a6', marginTop: 2 }}>
                            {n.time.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                          </div>
                        </div>
                        <button onClick={() => dismiss(n.id)} style={{ fontSize: 12, color: '#9aa0a6', background: 'none', border: 'none', cursor: 'pointer', flexShrink: 0 }}>✕</button>
                      </div>
                    )
                  })
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Nav Links */}
      {isManager && (
        <>
          <NavItem to="/" icon={ICONS.gantt} label="Master Schedule" />
          <NavItem to="/machines" icon={ICONS.machines} label="Manage Machines" />
          <NavItem to="/jobs" icon={ICONS.jobs} label="Manage Jobs & Routing" />
          <NavItem to="/compare" icon={ICONS.compare} label="Scenario Compare" />
          <NavItem to="/copilot" icon={ICONS.copilot} label="AI Scheduler" />
        </>
      )}
      {!isManager && (
        <NavItem to="/" icon={ICONS.operator} label="My Shift Queue" />
      )}
      <NavItem to="/analytics" icon={ICONS.analytics} label="Analytics" />
      <NavItem to="/settings" icon={ICONS.settings} label="Settings" />
      {isAdmin && <NavItem to="/admin" icon={ICONS.admin} label="Admin — Users" />}

      <div style={{ flex: 1 }} />

      <div style={{ fontSize: 11.5, color: '#5f6368', padding: '0 24px 6px 24px' }}>
        {user?.full_name} · {user?.role?.replace('_', ' ')}
      </div>
      <button className="btn btn-ghost" onClick={handleLogout} style={{ justifyContent: 'flex-start', margin: '0 12px', border: 'none', background: 'transparent' }}>
        {ICONS.logout} &nbsp;Sign out
      </button>
    </aside>
  )
}

function NavItem({ to, icon, label }) {
  return (
    <NavLink
      to={to}
      end
      style={({ isActive }) => ({
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        padding: '10px 24px',
        borderRadius: '0 24px 24px 0',
        fontSize: 13.5,
        fontWeight: isActive ? 700 : 500,
        color: isActive ? '#1a73e8' : '#5f6368',
        background: isActive ? '#e8f0fe' : 'transparent',
        textDecoration: 'none',
        transition: 'background 0.15s ease, color 0.15s ease',
        marginRight: 12,
      })}
    >
      <span style={{ fontSize: 16, opacity: 0.85 }}>{icon}</span>
      {label}
    </NavLink>
  )
}
