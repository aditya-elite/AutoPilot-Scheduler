import { useMemo, useRef, useState, useEffect } from 'react'

const MAX_ROW_HEIGHT = 64
const MIN_ROW_HEIGHT = 40
const RULER_HEIGHT = 46
const MIN_PX_PER_MINUTE = 1.8
const MAX_PX_PER_MINUTE = 7.0
const LABEL_WIDTH = 170

const STATUS_COLORS = {
  planned: ['#e8f0fe', '#1a73e8'],      /* Light Google Blue on Dark Blue border */
  confirmed: ['#c2e7ff', '#185abc'],    /* Google Sky Blue */
  in_progress: ['#fef7e0', '#b06000'],  /* Google Amber */
  completed: ['#f1f3f4', '#5f6368'],    /* Google light grey */
}

function priorityGradient(status, violates) {
  if (violates) return ['#fce8e6', '#c5221f'] /* Google Red alert colors */
  return STATUS_COLORS[status] || STATUS_COLORS.planned
}

export default function GanttChart({ machines, assignments, onOverride, readOnly = false }) {
  const containerRef = useRef(null)
  const [drag, setDrag] = useState(null) 
  const [ghost, setGhost] = useState(null)
  const [timelineViewportWidth, setTimelineViewportWidth] = useState(900)
  const [timelineViewportHeight, setTimelineViewportHeight] = useState(420)
  const [zoom, setZoom] = useState(1.15)
  
  // Simulation Playback states
  const [simTime, setSimTime] = useState(null) 
  const [isSimPlaying, setIsSimPlaying] = useState(false)
  const simTimerRef = useRef(null)

  const { horizonStart, horizonEnd } = useMemo(() => {
    if (assignments.length === 0) {
      const now = new Date()
      return { horizonStart: now, horizonEnd: new Date(now.getTime() + 8 * 3600 * 1000) }
    }
    const starts = assignments.map((a) => new Date(a.scheduled_start).getTime())
    const ends = assignments.map((a) => new Date(a.scheduled_end).getTime())
    const min = Math.min(...starts) - 30 * 60 * 1000
    const max = Math.max(...ends) + 60 * 60 * 1000
    return { horizonStart: new Date(min), horizonEnd: new Date(max) }
  }, [assignments])

  const totalMinutes = (horizonEnd - horizonStart) / 60000
  const pxPerMinute = useMemo(() => {
    if (totalMinutes <= 0) return MAX_PX_PER_MINUTE
    const fitPx = timelineViewportWidth / totalMinutes
    const scaled = fitPx * zoom
    return Math.min(MAX_PX_PER_MINUTE, Math.max(MIN_PX_PER_MINUTE, scaled))
  }, [timelineViewportWidth, totalMinutes, zoom])
  const timelineWidth = Math.max(totalMinutes * pxPerMinute, timelineViewportWidth)
  const rowHeight = useMemo(() => {
    const machineCount = Math.max(1, machines.length)
    const availableHeight = Math.max(180, timelineViewportHeight - RULER_HEIGHT)
    const fitted = Math.floor(availableHeight / machineCount)
    return Math.max(MIN_ROW_HEIGHT, Math.min(MAX_ROW_HEIGHT, fitted))
  }, [machines.length, timelineViewportHeight])

  function xForDate(date) {
    return ((new Date(date) - horizonStart) / 60000) * pxPerMinute
  }

  useEffect(() => {
    const measure = () => {
      const el = containerRef.current
      if (!el) return
      const available = el.clientWidth - LABEL_WIDTH
      const availableHeight = el.clientHeight
      setTimelineViewportWidth(Math.max(320, available))
      setTimelineViewportHeight(Math.max(220, availableHeight))
    }

    measure()
    window.addEventListener('resize', measure)
    return () => window.removeEventListener('resize', measure)
  }, [])

  const hourMarks = useMemo(() => {
    const marks = []
    const start = new Date(horizonStart)
    start.setMinutes(0, 0, 0)
    for (let t = start.getTime(); t < horizonEnd.getTime(); t += 3600 * 1000) {
      marks.push(new Date(t))
    }
    return marks
  }, [horizonStart, horizonEnd])

  const startSimulation = () => {
    if (simTime === null || simTime >= totalMinutes) {
      setSimTime(0)
    }
    setIsSimPlaying(true)
  }

  const pauseSimulation = () => {
    setIsSimPlaying(false)
  }

  const resetSimulation = () => {
    setIsSimPlaying(false)
    setSimTime(null)
  }

  useEffect(() => {
    if (isSimPlaying) {
      simTimerRef.current = setInterval(() => {
        setSimTime((prev) => {
          if (prev >= totalMinutes) {
            clearInterval(simTimerRef.current)
            setIsSimPlaying(false)
            return totalMinutes
          }
          return prev + 6 // sweep 6 minutes of scheduling time every 100ms
        })
      }, 100)
    } else {
      clearInterval(simTimerRef.current)
    }
    return () => clearInterval(simTimerRef.current)
  }, [isSimPlaying, totalMinutes])

  function handleMouseDown(e, assignment) {
    if (readOnly || simTime !== null) return // block drags during simulation playback
    const machineIndex = machines.findIndex((m) => m.machine_id === assignment.machine_id)
    setDrag({
      assignmentId: assignment.assignment_id,
      startClientX: e.clientX,
      startClientY: e.clientY,
      origStartMs: new Date(assignment.scheduled_start).getTime(),
      origDurationMs: new Date(assignment.scheduled_end) - new Date(assignment.scheduled_start),
      origMachineIndex: machineIndex,
    })
    setGhost({ assignment, machineIndex, startMs: new Date(assignment.scheduled_start).getTime() })
    e.stopPropagation()
  }

  function handleMouseMove(e) {
    if (!drag) return
    const dxMinutes = (e.clientX - drag.startClientX) / pxPerMinute
    const dyRows = Math.round((e.clientY - drag.startClientY) / rowHeight)
    const newMachineIndex = Math.min(machines.length - 1, Math.max(0, drag.origMachineIndex + dyRows))
    const snappedMinutes = Math.round(dxMinutes / 5) * 5
    const newStartMs = drag.origStartMs + snappedMinutes * 60000
    setGhost((g) => ({ ...g, machineIndex: newMachineIndex, startMs: newStartMs }))
  }

  function handleMouseUp() {
    if (!drag || !ghost) {
      setDrag(null)
      setGhost(null)
      return
    }
    const newMachine = machines[ghost.machineIndex]
    onOverride?.(drag.assignmentId, newMachine.machine_id, new Date(ghost.startMs).toISOString())
    setDrag(null)
    setGhost(null)
  }

  return (
    <div
      className="acrylic"
      style={{ padding: 0, overflow: 'hidden', cursor: drag ? 'grabbing' : 'default' }}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
    >
      <style>{`
        @keyframes gantt-pulse {
          0% { box-shadow: 0 0 4px #4ade80, inset 0 0 4px rgba(255,255,255,0.2); }
          100% { box-shadow: 0 0 16px #4ade80, inset 0 0 8px rgba(255,255,255,0.4); }
        }
      `}</style>

      {/* Outer scroll container — horizontal and vertical scroll as needed */}
      <div
        ref={containerRef}
        style={{
          display: 'flex',
          overflowX: 'auto',
          overflowY: 'auto',
          height: '100%',
          scrollbarWidth: 'thin',
          scrollbarColor: '#dadce0 transparent',
        }}
      >
        {/* Sticky machine label column */}
        <div style={{ minWidth: LABEL_WIDTH, flexShrink: 0, position: 'sticky', left: 0, zIndex: 3, background: '#ffffff', borderRight: '1px solid #dadce0' }}>
          <div style={{ height: RULER_HEIGHT, borderBottom: '1px solid #dadce0', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 6, padding: '0 8px' }}>
            <div style={{ display: 'flex', gap: 4 }}>
              <button className="btn" style={{ padding: '2px 6px', fontSize: 10 }} onClick={() => setZoom(z => Math.max(0.85, Number((z - 0.15).toFixed(2))))}>
                −
              </button>
              <span style={{ fontSize: 10.5, color: '#5f6368', minWidth: 48, textAlign: 'center' }}>{Math.round(zoom * 100)}%</span>
              <button className="btn" style={{ padding: '2px 6px', fontSize: 10 }} onClick={() => setZoom(z => Math.min(1.9, Number((z + 0.15).toFixed(2))))}>
                +
              </button>
            </div>
            {simTime === null ? (
              <button className="btn" style={{ padding: '2px 8px', fontSize: 11, background: '#e8f0fe', color: '#1a73e8', border: 'none' }} onClick={startSimulation}>
                ▶ Play Sim
              </button>
            ) : (
              <div style={{ display: 'flex', gap: 4 }}>
                <button className="btn" style={{ padding: '2px 6px', fontSize: 10 }} onClick={isSimPlaying ? pauseSimulation : startSimulation}>
                  {isSimPlaying ? '⏸' : '▶'}
                </button>
                <button className="btn btn-ghost text-danger" style={{ padding: '2px 6px', fontSize: 10, border: 'none' }} onClick={resetSimulation}>
                  ↺
                </button>
              </div>
            )}
          </div>
          {machines.map((m) => (
            <div
              key={m.machine_id}
              style={{
                height: rowHeight,
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'center',
                padding: '0 14px',
                borderBottom: '1px solid #e0e0e0',
              }}
            >
              <div style={{ fontSize: 13, fontWeight: 600 }}>{m.machine_code}</div>
              <div className={m.status === 'offline' ? 'badge badge-offline' : 'badge badge-online'} style={{ width: 'fit-content', marginTop: 3 }}>
                <span className="badge-dot" />
                {m.status}
              </div>
            </div>
          ))}
        </div>

        {/* Scrollable timeline */}
        <div style={{ position: 'relative', width: timelineWidth, flexShrink: 0 }}>
          {/* Hour ruler */}
          <div style={{ height: RULER_HEIGHT, position: 'relative', borderBottom: '1px solid #dadce0', background: '#fafbff' }}>
            {hourMarks.map((mark, i) => (
              <div
                key={i}
                style={{
                  position: 'absolute',
                  left: xForDate(mark),
                  top: 0,
                  height: '100%',
                  display: 'flex',
                  alignItems: 'center',
                  fontSize: 11.5,
                  color: '#3c4043',
                  paddingLeft: 6,
                  borderLeft: '1px solid #c8ccd1',
                }}
              >
                {mark.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </div>
            ))}
          </div>

          {/* Machine rows with grid lines */}
          {machines.map((m, idx) => {
            const isDraggingThis = drag !== null
            const isEligible = isDraggingThis && (ghost?.assignment?.eligible_machine_ids || []).includes(m.machine_id)
            const isTarget = isDraggingThis && ghost?.machineIndex === idx
            
            let rowBg = idx % 2 === 0 ? '#ffffff' : '#fcfcfd'
            let borderStyle = '1px solid #e0e0e0'
            
            if (m.status === 'offline') {
              rowBg = 'repeating-linear-gradient(135deg, #fdf8f8 0 10px, #fbf2f2 10px 20px)'
            }
            
            if (isDraggingThis) {
              if (isEligible) {
                rowBg = isTarget ? 'rgba(74, 222, 128, 0.15)' : 'rgba(74, 222, 128, 0.04)'
                borderStyle = isTarget ? '2px solid #4ade80' : '1px dashed rgba(74, 222, 128, 0.3)'
              } else {
                rowBg = 'rgba(239, 68, 68, 0.05)'
                borderStyle = '1px dashed rgba(239, 68, 68, 0.2)'
              }
            }

            return (
              <div
                key={m.machine_id}
                style={{
                  height: rowHeight,
                  position: 'relative',
                  borderBottom: borderStyle,
                  background: rowBg,
                  transition: 'background 0.15s ease, border 0.15s ease'
                }}
              >
                {hourMarks.map((mark, i) => (
                  <div key={i} style={{ position: 'absolute', left: xForDate(mark), top: 0, bottom: 0, borderLeft: '1px solid #e6e9ee' }} />
                ))}

                {assignments
                  .filter((a) => a.machine_id === m.machine_id && !(ghost && ghost.assignment.assignment_id === a.assignment_id))
                  .map((a) => (
                    <TaskBar 
                      key={a.assignment_id} 
                      assignment={a} 
                      xForDate={xForDate} 
                      pxPerMinute={pxPerMinute}
                      rowHeight={rowHeight}
                      readOnly={readOnly || simTime !== null} 
                      onMouseDown={handleMouseDown} 
                      simTime={simTime}
                      horizonStart={horizonStart}
                    />
                  ))}
              </div>
            )
          })}

          {/* Ghost bar while dragging */}
          {ghost && (
            <div
              style={{
                position: 'absolute',
                top: RULER_HEIGHT + ghost.machineIndex * rowHeight + 6,
                left: xForDate(ghost.startMs),
                width: ((ghost.assignment.scheduled_end && new Date(ghost.assignment.scheduled_end) - new Date(ghost.assignment.scheduled_start)) / 60000) * pxPerMinute,
                height: rowHeight - 12,
                borderRadius: 10,
                border: '2px dashed var(--color-aurora-teal)',
                background: 'rgba(79,209,197,0.12)',
                pointerEvents: 'none',
                zIndex: 5,
              }}
            />
          )}

          {/* Red simulation time sweep bar */}
          {simTime !== null && (
            <div
              style={{
                position: 'absolute',
                top: RULER_HEIGHT,
                bottom: 0,
                left: simTime * pxPerMinute,
                width: 2,
                background: '#ef4444',
                boxShadow: '0 0 10px #ef4444',
                zIndex: 4,
                pointerEvents: 'none',
              }}
            />
          )}
        </div>
      </div>
    </div>
  )
}

function TaskBar({ assignment, xForDate, pxPerMinute, rowHeight, readOnly, onMouseDown, simTime, horizonStart }) {
  const [c1, c2] = priorityGradient(assignment.status, assignment.violates_constraint)
  const left = xForDate(assignment.scheduled_start)
  const width = Math.max(18, (new Date(assignment.scheduled_end) - new Date(assignment.scheduled_start)) / 60000 * pxPerMinute)

  // Determine active task state during simulation playback
  let opacity = 1
  let activeStyles = {}
  let progress = 0
  let isRunningSim = simTime !== null && horizonStart

  if (isRunningSim) {
    const startMin = (new Date(assignment.scheduled_start) - horizonStart) / 60000
    const endMin = (new Date(assignment.scheduled_end) - horizonStart) / 60000

    if (simTime < startMin) {
      opacity = 0.4
      progress = 0
    } else if (simTime >= startMin && simTime <= endMin) {
      opacity = 1
      progress = ((simTime - startMin) / (endMin - startMin)) * 100
      activeStyles = {
        boxShadow: '0 0 12px #4ade80, inset 0 0 8px rgba(255,255,255,0.4)',
        animation: 'gantt-pulse 0.8s infinite alternate',
      }
    } else {
      opacity = 0.25
      progress = 100
    }
  }

  return (
    <div
      title={`${assignment.job_code} — ${assignment.task_name}${assignment.violates_constraint ? '\n⚠ ' + assignment.violation_reason : ''}`}
      onMouseDown={(e) => onMouseDown(e, assignment)}
      style={{
        position: 'absolute',
        top: 6,
        left,
        width,
        height: rowHeight - 12,
        borderRadius: 10,
        background: `linear-gradient(135deg, ${c1}, ${c2})`,
        boxShadow: assignment.violates_constraint ? '0 0 0 2px rgba(245,97,122,0.6)' : '0 2px 8px rgba(0,0,0,0.25)',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        padding: '0 10px',
        overflow: 'hidden',
        cursor: readOnly ? 'default' : 'grab',
        userSelect: 'none',
        opacity,
        transition: 'opacity 0.2s ease',
        ...activeStyles,
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontSize: 11.5, fontWeight: 700, color: 'rgba(0,0,0,0.75)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
          {assignment.job_code}
        </span>
        {isRunningSim && progress === 100 && (
          <span style={{ fontSize: 10, color: '#137333', fontWeight: 'bold' }}>✓</span>
        )}
      </div>
      <div style={{ fontSize: 10, color: 'rgba(0,0,0,0.6)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
        {assignment.task_name}
      </div>

      {/* Point 4: Live Telemetry Progress Bar */}
      {isRunningSim && (
        <div style={{
          marginTop: 3,
          height: 3,
          background: 'rgba(0,0,0,0.12)',
          borderRadius: 1.5,
          overflow: 'hidden',
          width: '100%'
        }}>
          <div style={{
            height: '100%',
            width: `${progress}%`,
            background: progress === 100 ? '#137333' : '#1a73e8',
            transition: 'width 0.1s linear'
          }} />
        </div>
      )}
    </div>
  )
}
