import { createContext, useContext, useState, useCallback } from 'react'
import { useAuth } from './AuthContext.jsx'
import { useScheduleSocket } from '../hooks/useScheduleSocket.js'

const NotificationContext = createContext(null)

export function NotificationProvider({ children }) {
  const [notifications, setNotifications] = useState([])
  const { user } = useAuth()

  const addNotification = useCallback((message, type = 'info') => {
    const id = Date.now()
    setNotifications(prev => [{ id, message, type, time: new Date() }, ...prev].slice(0, 20))
    // Auto-remove after 8 seconds
    setTimeout(() => {
      setNotifications(prev => prev.filter(n => n.id !== id))
    }, 8000)
  }, [])

  const clearAll = useCallback(() => setNotifications([]), [])
  const dismiss = useCallback((id) => setNotifications(prev => prev.filter(n => n.id !== id)), [])

  // App-wide live-update feed: fires regardless of which page is open,
  // so e.g. a second manager tab or the operator view learns about a
  // re-optimization or breakdown even though they didn't trigger it.
  useScheduleSocket(useCallback((msg) => {
    if (!user) return
    const payload = msg?.payload || {}

    if (msg.type === 'schedule_updated') {
      if (payload.reason === 'optimization_complete') {
        addNotification(`AI optimization complete — makespan ${payload.makespan_minutes}m`, 'success')
      } else if (payload.reason === 'manual_override') {
        addNotification(
          payload.violates_constraint ? 'Schedule manually overridden — conflict flagged' : 'Schedule manually overridden',
          payload.violates_constraint ? 'warning' : 'info'
        )
      }
      // 'status_update' (operator checking off a task) is intentionally
      // ignored here — too granular for a global notification feed.
    } else if (msg.type === 'optimization_failed') {
      const detail = payload.blockers?.length
        ? `${payload.blockers.length} blocker(s) — see Master Schedule`
        : (payload.error_message || 'unknown error')
      addNotification(`AI optimization failed: ${detail}`, 'error')
    } else if (msg.type === 'machine_status_changed') {
      const label = payload.machine_code || `#${payload.machine_id}`
      addNotification(`Machine ${label} is now ${payload.status}`, payload.status === 'offline' ? 'error' : 'success')
    }
  }, [user, addNotification]))

  return (
    <NotificationContext.Provider value={{ notifications, addNotification, clearAll, dismiss }}>
      {children}
    </NotificationContext.Provider>
  )
}

export function useNotifications() {
  return useContext(NotificationContext)
}
