import { useEffect, useState, useCallback, useRef } from 'react'
import client from '../api/client'

export default function ScenarioComparison() {
  const [runs, setRuns] = useState([])
  const [machines, setMachines] = useState([])
  const [jobs, setJobs] = useState([])
  
  // Selection
  const [runAId, setRunAId] = useState('')
  const [runBId, setRunBId] = useState('')
  
  // Scenarios data
  const [runA, setRunA] = useState(null)
  const [runB, setRunB] = useState(null)
  const [ganttA, setGanttA] = useState([])
  const [ganttB, setGanttB] = useState([])

  // Label Edit forms
  const [labelA, setLabelA] = useState('')
  const [labelB, setLabelB] = useState('')

  const [error, setError] = useState('')
  const mountedRef = useRef(true)

  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
    }
  }, [])

  const loadBase = useCallback(async () => {
    try {
      const [runsRes, machinesRes, jobsRes] = await Promise.all([
        client.get('/schedule/runs'),
        client.get('/machines'),
        client.get('/jobs')
      ])
      if (!mountedRef.current) return
      // Filter only completed runs to compare
      const completed = runsRes.data.filter(r => r.status === 'completed')
      setRuns(completed)
      setMachines(machinesRes.data)
      setJobs(jobsRes.data)
    } catch (err) {
      setError('Failed to load runs or configurations')
    }
  }, [])

  useEffect(() => {
    loadBase()
  }, [loadBase])

  const loadScenarioA = async (id) => {
    if (!id) {
      setRunA(null)
      setGanttA([])
      return
    }
    const runObj = runs.find(r => r.run_id === parseInt(id))
    setRunA(runObj)
    setLabelA(runObj?.solver_config?.label || '')
    
    try {
      const res = await client.get(`/schedule/gantt/${id}`)
      setGanttA(res.data)
    } catch (err) {
      setError('Failed to load assignments for Scenario A')
    }
  }

  const loadScenarioB = async (id) => {
    if (!id) {
      setRunB(null)
      setGanttB([])
      return
    }
    const runObj = runs.find(r => r.run_id === parseInt(id))
    setRunB(runObj)
    setLabelB(runObj?.solver_config?.label || '')
    
    try {
      const res = await client.get(`/schedule/gantt/${id}`)
      setGanttB(res.data)
    } catch (err) {
      setError('Failed to load assignments for Scenario B')
    }
  }

  const handleUpdateLabel = async (runId, newLabel) => {
    try {
      await client.put(`/schedule/runs/${runId}/label`, { label: newLabel })
      await loadBase() // reload runs list to get updated config
    } catch (err) {
      setError('Failed to update label')
    }
  }

  // Calculate Metrics
  const calculateMetrics = (run, gantt) => {
    if (!run || gantt.length === 0) return null

    // 1. Makespan
    const makespan = run.makespan_minutes || 0

    // 2. Tardiness
    const tardiness = run.total_tardiness_minutes || 0

    // 3. Late Jobs
    // Group assignments by job_id to find latest end date
    const jobCompletionTimes = {}
    gantt.forEach(a => {
      const endTime = new Date(a.scheduled_end).getTime()
      if (!jobCompletionTimes[a.job_id] || endTime > jobCompletionTimes[a.job_id]) {
        jobCompletionTimes[a.job_id] = endTime
      }
    })
    
    let lateJobsCount = 0
    Object.keys(jobCompletionTimes).forEach(jobId => {
      const job = jobs.find(j => j.job_id === parseInt(jobId))
      if (job) {
        const dueDate = new Date(job.due_date).getTime()
        if (jobCompletionTimes[jobId] > dueDate) {
          lateJobsCount++
        }
      }
    })

    // 4. Average Machine Utilization
    // Sum of processing minutes of all tasks in the run
    let totalActiveMinutes = 0
    gantt.forEach(a => {
      const duration = (new Date(a.scheduled_end) - new Date(a.scheduled_start)) / 60000 // duration in minutes
      totalActiveMinutes += duration
    })

    const activeMachineCount = machines.filter(m => m.status !== 'offline').length
    const horizonTotal = makespan * activeMachineCount
    const averageUtilization = horizonTotal > 0 ? (totalActiveMinutes / horizonTotal) * 100 : 0

    return {
      makespan,
      tardiness,
      lateJobsCount,
      averageUtilization,
      totalActiveMinutes
    }
  }

  const metricsA = calculateMetrics(runA, ganttA)
  const metricsB = calculateMetrics(runB, ganttB)

  const getRunDisplayName = (r) => {
    if (!r) return ''
    const timestamp = r.started_at || r.created_at
    let dateStr = 'Unknown Date'
    if (timestamp) {
      const d = new Date(timestamp)
      if (!isNaN(d.getTime())) {
        dateStr = d.toLocaleString([], { dateStyle: 'short', timeStyle: 'short' })
      }
    }
    const label = r.solver_config?.label ? `"${r.solver_config.label}"` : `Run #${r.run_id}`
    return `${label} - ${r.goal.replace('_', ' ')} (${dateStr})`
  }

  return (
    <div>
      <h1 style={{ fontSize: 22, marginBottom: 4 }}>Scenario Comparison</h1>
      <p className="text-secondary" style={{ fontSize: 13, marginBottom: 20 }}>
        Compare makespan, tardiness, machine utilization, and visual task routing of two completed schedules side-by-side.
      </p>

      {error && <div style={{ color: 'var(--color-danger)', fontSize: 12.5, marginBottom: 16 }}>{error}</div>}

      {/* Selectors */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 24 }}>
        <div className="acrylic" style={{ padding: 16 }}>
          <label className="flex-col gap-8" style={{ display: 'flex' }}>
            <span className="text-secondary" style={{ fontSize: 12, fontWeight: 600 }}>Select Scenario A</span>
            <select 
              value={runAId} 
              onChange={(e) => {
                setRunAId(e.target.value)
                loadScenarioA(e.target.value)
              }}
            >
              <option value="">-- Choose a schedule run --</option>
              {runs.map(r => (
                <option key={r.run_id} value={r.run_id}>
                  {getRunDisplayName(r)}
                </option>
              ))}
            </select>
          </label>
          
          {runA && (
            <div className="flex gap-8 items-center" style={{ display: 'flex', marginTop: 12 }}>
              <input 
                placeholder="Name Scenario A (e.g. Balanced Shift)" 
                value={labelA}
                onChange={(e) => setLabelA(e.target.value)}
                style={{ flex: 1, fontSize: 12, padding: '5px 8px' }}
              />
              <button 
                type="button" 
                className="btn" 
                style={{ padding: '5px 10px', fontSize: 11.5 }}
                onClick={() => handleUpdateLabel(runA.run_id, labelA)}
              >
                Save Name
              </button>
            </div>
          )}
        </div>

        <div className="acrylic" style={{ padding: 16 }}>
          <label className="flex-col gap-8" style={{ display: 'flex' }}>
            <span className="text-secondary" style={{ fontSize: 12, fontWeight: 600 }}>Select Scenario B</span>
            <select 
              value={runBId} 
              onChange={(e) => {
                setRunBId(e.target.value)
                loadScenarioB(e.target.value)
              }}
            >
              <option value="">-- Choose a schedule run --</option>
              {runs.map(r => (
                <option key={r.run_id} value={r.run_id}>
                  {getRunDisplayName(r)}
                </option>
              ))}
            </select>
          </label>

          {runB && (
            <div className="flex gap-8 items-center" style={{ display: 'flex', marginTop: 12 }}>
              <input 
                placeholder="Name Scenario B (e.g. Extra Welders)" 
                value={labelB}
                onChange={(e) => setLabelB(e.target.value)}
                style={{ flex: 1, fontSize: 12, padding: '5px 8px' }}
              />
              <button 
                type="button" 
                className="btn" 
                style={{ padding: '5px 10px', fontSize: 11.5 }}
                onClick={() => handleUpdateLabel(runB.run_id, labelB)}
              >
                Save Name
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Comparisons */}
      {runA && runB && (
        <div className="flex-col gap-20" style={{ display: 'flex' }}>
          {/* KPI Dashboard Compare */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
            {/* Scenario A Card */}
            <div className="acrylic" style={{ padding: 20 }}>
              <h3 style={{ fontSize: 15, marginBottom: 16, color: 'var(--color-primary)' }}>
                Scenario A: {runA.solver_config?.label || `Run #${runA.run_id}`}
              </h3>
              {metricsA ? (
                <div className="flex-col gap-12" style={{ display: 'flex' }}>
                  <div className="flex justify-between" style={{ borderBottom: '1px solid rgba(255,255,255,0.03)', paddingBottom: 6 }}>
                    <span className="text-secondary" style={{ fontSize: 12.5 }}>Makespan (Total Time)</span>
                    <span style={{ fontWeight: 700 }}>{metricsA.makespan} min</span>
                  </div>
                  <div className="flex justify-between" style={{ borderBottom: '1px solid rgba(255,255,255,0.03)', paddingBottom: 6 }}>
                    <span className="text-secondary" style={{ fontSize: 12.5 }}>Total Tardiness</span>
                    <span style={{ fontWeight: 700, color: metricsA.tardiness > 0 ? 'var(--color-danger)' : '#4ade80' }}>
                      {metricsA.tardiness} min
                    </span>
                  </div>
                  <div className="flex justify-between" style={{ borderBottom: '1px solid rgba(255,255,255,0.03)', paddingBottom: 6 }}>
                    <span className="text-secondary" style={{ fontSize: 12.5 }}>Late / Missed Deadlines</span>
                    <span style={{ fontWeight: 700, color: metricsA.lateJobsCount > 0 ? 'var(--color-danger)' : '#4ade80' }}>
                      {metricsA.lateJobsCount} Jobs
                    </span>
                  </div>
                  <div className="flex justify-between" style={{ borderBottom: '1px solid rgba(255,255,255,0.03)', paddingBottom: 6 }}>
                    <span className="text-secondary" style={{ fontSize: 12.5 }}>Avg Machine Utilization</span>
                    <span style={{ fontWeight: 700 }}>{metricsA.averageUtilization.toFixed(1)}%</span>
                  </div>
                  <div className="flex justify-between" style={{ paddingBottom: 6 }}>
                    <span className="text-secondary" style={{ fontSize: 12.5 }}>Workload (Total Active Time)</span>
                    <span>{metricsA.totalActiveMinutes.toFixed(0)} min</span>
                  </div>
                </div>
              ) : (
                <p className="text-secondary" style={{ fontSize: 12 }}>No scheduling results available.</p>
              )}
            </div>

            {/* Scenario B Card */}
            <div className="acrylic" style={{ padding: 20 }}>
              <h3 style={{ fontSize: 15, marginBottom: 16, color: '#f59e0b' }}>
                Scenario B: {runB.solver_config?.label || `Run #${runB.run_id}`}
              </h3>
              {metricsB ? (
                <div className="flex-col gap-12" style={{ display: 'flex' }}>
                  <div className="flex justify-between" style={{ borderBottom: '1px solid rgba(255,255,255,0.03)', paddingBottom: 6 }}>
                    <span className="text-secondary" style={{ fontSize: 12.5 }}>Makespan (Total Time)</span>
                    <span style={{ fontWeight: 700 }}>
                      {metricsB.makespan} min{' '}
                      {metricsA && (
                        <span style={{ fontSize: 11, fontWeight: 400, marginLeft: 6, color: metricsB.makespan < metricsA.makespan ? '#4ade80' : 'var(--color-danger)' }}>
                          ({metricsB.makespan < metricsA.makespan ? '-' : '+'}{Math.abs(metricsB.makespan - metricsA.makespan)} min)
                        </span>
                      )}
                    </span>
                  </div>
                  <div className="flex justify-between" style={{ borderBottom: '1px solid rgba(255,255,255,0.03)', paddingBottom: 6 }}>
                    <span className="text-secondary" style={{ fontSize: 12.5 }}>Total Tardiness</span>
                    <span style={{ fontWeight: 700, color: metricsB.tardiness > 0 ? 'var(--color-danger)' : '#4ade80' }}>
                      {metricsB.tardiness} min{' '}
                      {metricsA && (
                        <span style={{ fontSize: 11, fontWeight: 400, marginLeft: 6, color: metricsB.tardiness < metricsA.tardiness ? '#4ade80' : 'var(--color-danger)' }}>
                          ({metricsB.tardiness < metricsA.tardiness ? '-' : '+'}{Math.abs(metricsB.tardiness - metricsA.tardiness)} min)
                        </span>
                      )}
                    </span>
                  </div>
                  <div className="flex justify-between" style={{ borderBottom: '1px solid rgba(255,255,255,0.03)', paddingBottom: 6 }}>
                    <span className="text-secondary" style={{ fontSize: 12.5 }}>Late / Missed Deadlines</span>
                    <span style={{ fontWeight: 700, color: metricsB.lateJobsCount > 0 ? 'var(--color-danger)' : '#4ade80' }}>
                      {metricsB.lateJobsCount} Jobs{' '}
                      {metricsA && (
                        <span style={{ fontSize: 11, fontWeight: 400, marginLeft: 6, color: metricsB.lateJobsCount < metricsA.lateJobsCount ? '#4ade80' : 'var(--color-danger)' }}>
                          ({metricsB.lateJobsCount < metricsA.lateJobsCount ? '-' : '+'}{Math.abs(metricsB.lateJobsCount - metricsA.lateJobsCount)} jobs)
                        </span>
                      )}
                    </span>
                  </div>
                  <div className="flex justify-between" style={{ borderBottom: '1px solid rgba(255,255,255,0.03)', paddingBottom: 6 }}>
                    <span className="text-secondary" style={{ fontSize: 12.5 }}>Avg Machine Utilization</span>
                    <span style={{ fontWeight: 700 }}>
                      {metricsB.averageUtilization.toFixed(1)}%{' '}
                      {metricsA && (
                        <span style={{ fontSize: 11, fontWeight: 400, marginLeft: 6, color: metricsB.averageUtilization > metricsA.averageUtilization ? '#4ade80' : 'var(--color-text-tertiary)' }}>
                          ({metricsB.averageUtilization > metricsA.averageUtilization ? '+' : ''}{(metricsB.averageUtilization - metricsA.averageUtilization).toFixed(1)}%)
                        </span>
                      )}
                    </span>
                  </div>
                  <div className="flex justify-between" style={{ paddingBottom: 6 }}>
                    <span className="text-secondary" style={{ fontSize: 12.5 }}>Workload (Total Active Time)</span>
                    <span>{metricsB.totalActiveMinutes.toFixed(0)} min</span>
                  </div>
                </div>
              ) : (
                <p className="text-secondary" style={{ fontSize: 12 }}>No scheduling results available.</p>
              )}
            </div>
          </div>

          {/* Timelines comparison */}
          <div className="acrylic" style={{ padding: 20 }}>
            <h3 style={{ fontSize: 14, marginBottom: 16 }}>Timeline Task Allocation Side-by-Side</h3>
            
            <div className="flex-col gap-14" style={{ display: 'flex' }}>
              {machines.map(m => {
                const tasksA = ganttA.filter(a => a.machine_id === m.machine_id)
                const tasksB = ganttB.filter(a => a.machine_id === m.machine_id)
                
                return (
                  <div key={m.machine_id} style={{ borderBottom: '1px solid rgba(255,255,255,0.03)', paddingBottom: 10 }}>
                    <h4 className="mono" style={{ fontSize: 12.5, margin: '0 0 6px 0', fontWeight: 600 }}>{m.machine_code} ({m.machine_name})</h4>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
                      {/* Scenario A timeline list */}
                      <div style={{ background: 'rgba(0,180,216,0.02)', padding: 6, borderRadius: 6, minHeight: 30 }}>
                        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                          {tasksA.length > 0 ? tasksA.map(a => (
                            <span 
                              key={a.assignment_id} 
                              className={`badge badge-${a.violates_constraint ? 'critical' : 'online'}`}
                              style={{ fontSize: 9.5, padding: '2px 5px' }}
                              title={`Start: ${new Date(a.scheduled_start).toLocaleTimeString()} - End: ${new Date(a.scheduled_end).toLocaleTimeString()}`}
                            >
                              {a.job_code}: {a.task_name} ({Math.round((new Date(a.scheduled_end) - new Date(a.scheduled_start)) / 60000)}m)
                            </span>
                          )) : (
                            <span className="text-tertiary" style={{ fontSize: 10.5, fontStyle: 'italic' }}>No tasks assigned</span>
                          )}
                        </div>
                      </div>

                      {/* Scenario B timeline list */}
                      <div style={{ background: 'rgba(245,158,11,0.02)', padding: 6, borderRadius: 6, minHeight: 30 }}>
                        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                          {tasksB.length > 0 ? tasksB.map(a => (
                            <span 
                              key={a.assignment_id} 
                              style={{ 
                                fontSize: 9.5, 
                                padding: '2px 5px',
                                background: a.violates_constraint ? 'rgba(239,68,68,0.2)' : 'rgba(245,158,11,0.2)',
                                border: a.violates_constraint ? '1px solid rgba(239,68,68,0.4)' : '1px solid rgba(245,158,11,0.4)',
                                color: a.violates_constraint ? '#f87171' : '#fbcfe8',
                                borderRadius: 4
                              }}
                              title={`Start: ${new Date(a.scheduled_start).toLocaleTimeString()} - End: ${new Date(a.scheduled_end).toLocaleTimeString()}`}
                            >
                              {a.job_code}: {a.task_name} ({Math.round((new Date(a.scheduled_end) - new Date(a.scheduled_start)) / 60000)}m)
                            </span>
                          )) : (
                            <span className="text-tertiary" style={{ fontSize: 10.5, fontStyle: 'italic' }}>No tasks assigned</span>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
