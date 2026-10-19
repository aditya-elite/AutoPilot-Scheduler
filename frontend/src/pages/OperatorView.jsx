import { useEffect, useState, useCallback, useRef } from 'react'
import client from '../api/client'
import { useScheduleSocket } from '../hooks/useScheduleSocket.js'

const STATUS_LABEL = {
  planned: 'Up next',
  confirmed: 'Confirmed',
  in_progress: 'In progress',
  completed: 'Done',
}

export default function OperatorView() {
  const [assignments, setAssignments] = useState([])
  const [pending, setPending] = useState({})
  const mountedRef = useRef(true)

  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
    }
  }, [])

  const load = useCallback(async () => {
    const res = await client.get('/schedule/gantt')
    if (!mountedRef.current) return
    setAssignments(res.data.sort((a, b) => new Date(a.scheduled_start) - new Date(b.scheduled_start)))
  }, [])

  useEffect(() => {
    load()
  }, [load])

  useScheduleSocket((msg) => {
    if (msg.type === 'schedule_updated' || msg.type === 'machine_status_changed') load()
  })

  async function toggle(assignment) {
    const nextStatus = assignment.status === 'completed' ? 'in_progress' : 'completed'
    setPending((p) => ({ ...p, [assignment.assignment_id]: true }))
    try {
      await client.patch(`/schedule/assignments/${assignment.assignment_id}/status`, { status: nextStatus })
      await load()
    } finally {
      setPending((p) => ({ ...p, [assignment.assignment_id]: false }))
    }
  }

  return (
    <div style={{ maxWidth: 520, margin: '0 auto' }}>
      <h1 style={{ fontSize: 20, marginBottom: 4 }}>My Shift Queue</h1>
      <p className="text-secondary" style={{ fontSize: 13, marginBottom: 20 }}>
        Today&rsquo;s tasks across all machines, in order. Checking a task off updates the live schedule.
      </p>

      <div className="flex-col gap-12" style={{ display: 'flex' }}>
        {assignments.length === 0 && (
          <div className="acrylic text-secondary" style={{ padding: 24, textAlign: 'center' }}>
            No tasks scheduled right now.
          </div>
        )}
        {assignments.map((a) => {
          const isDone = a.status === 'completed'
          return (
            <div
              key={a.assignment_id}
              className="acrylic"
              style={{
                padding: 16,
                display: 'flex',
                alignItems: 'flex-start',
                gap: 14,
                opacity: isDone ? 0.5 : pending[a.assignment_id] ? 0.7 : 1,
              }}
            >
              <input
                type="checkbox"
                checked={isDone}
                disabled={!!pending[a.assignment_id]}
                onChange={() => toggle(a)}
                style={{ width: 20, height: 20, marginTop: 3, accentColor: '#4fd1c5' }}
              />
              <div style={{ flex: 1 }}>
                <div className="flex justify-between items-center">
                  <span style={{ fontWeight: 700, fontSize: 14, textDecoration: isDone ? 'line-through' : 'none' }}>
                    {a.task_name}
                  </span>
                  {a.violates_constraint && (
                    <span className="badge badge-offline"><span className="badge-dot" />Flagged</span>
                  )}
                </div>
                <div className="text-secondary" style={{ fontSize: 12.5, marginTop: 3 }}>
                  {a.job_code} · Machine {a.machine_code}
                </div>
                <div className="flex gap-8 items-center" style={{ marginTop: 6 }}>
                  <span className="text-tertiary mono" style={{ fontSize: 11.5 }}>
                    {new Date(a.scheduled_start).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    {' – '}
                    {new Date(a.scheduled_end).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>
                  <span className="badge badge-online" style={{ opacity: 0.8 }}>{STATUS_LABEL[a.status] || a.status}</span>
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
