import { useEffect, useState } from 'react'
import client from '../api/client'
import UtilizationGauge from '../components/UtilizationGauge.jsx'
import { useNotifications } from '../context/NotificationContext.jsx'

const RISK_COLOR = { low: '#4ade80', medium: '#fbbf24', high: '#ef4444' }

export default function Analytics() {
  const [utilization, setUtilization] = useState([])
  const [auditLog, setAuditLog] = useState([])
  const [otd, setOtd] = useState(100)
  const [bottlenecks, setBottlenecks] = useState({})
  const [risk, setRisk] = useState([])
  const [riskLoading, setRiskLoading] = useState(false)
  const [riskError, setRiskError] = useState('')
  const [maintenanceLoadingId, setMaintenanceLoadingId] = useState(null)
  const [financials, setFinancials] = useState(null)
  const { addNotification } = useNotifications()

  useEffect(() => {
    client.get('/analytics/utilization').then((res) => setUtilization(res.data))
    client.get('/analytics/audit-log?limit=40').then((res) => setAuditLog(res.data))
    client.get('/breakdown/risk').then((res) => setRisk(res.data))
    client.get('/analytics/financials').then((res) => setFinancials(res.data))

    // Fetch data for OTD and Bottlenecks calculations
    Promise.all([
      client.get('/jobs'),
      client.get('/schedule/gantt')
    ]).then(([jobsRes, ganttRes]) => {
      const jobsList = jobsRes.data
      const ganttList = ganttRes.data
      
      // Calculate OTD
      if (jobsList.length > 0 && ganttList.length > 0) {
        const jobCompletionTimes = {}
        ganttList.forEach(a => {
          const endTime = new Date(a.scheduled_end).getTime()
          if (!jobCompletionTimes[a.job_id] || endTime > jobCompletionTimes[a.job_id]) {
            jobCompletionTimes[a.job_id] = endTime
          }
        })
        
        let onTimeCount = 0
        jobsList.forEach(j => {
          const compTime = jobCompletionTimes[j.job_id]
          if (!compTime) {
            onTimeCount++ // assume on time if not scheduled yet
          } else {
            const dueDate = new Date(j.due_date).getTime()
            if (compTime <= dueDate) {
              onTimeCount++
            }
          }
        })
        setOtd((onTimeCount / jobsList.length) * 100)

        // Calculate Bottlenecks (tardy workload minutes per machine)
        const machineScores = {}
        ganttList.forEach(a => {
          const job = jobsList.find(j => j.job_id === a.job_id)
          if (job) {
            const jobCompTime = jobCompletionTimes[a.job_id]
            const dueDate = new Date(job.due_date).getTime()
            if (jobCompTime > dueDate) {
              const duration = (new Date(a.scheduled_end) - new Date(a.scheduled_start)) / 60000
              machineScores[a.machine_id] = (machineScores[a.machine_id] || 0) + duration
            }
          }
        })
        setBottlenecks(machineScores)
      }
    })
  }, [])

  const getHeatmapColor = (minutes) => {
    if (!minutes || minutes === 0) return 'rgba(74, 222, 128, 0.15)' // Light green
    if (minutes < 60) return 'rgba(251, 191, 36, 0.25)' // Light amber
    return 'rgba(239, 68, 68, 0.35)' // Red alert
  }

  function recalculateRisk() {
    setRiskLoading(true)
    setRiskError('')
    client.post('/breakdown/risk/recompute')
      .then((res) => setRisk(res.data))
      .catch((err) => setRiskError(err.response?.data?.detail || 'Failed to recalculate risk.'))
      .finally(() => setRiskLoading(false))
  }

  function scheduleMaintenance(machine) {
    setMaintenanceLoadingId(machine.machine_id)
    client.post(`/breakdown/${machine.machine_id}/schedule-maintenance`, { duration_hours: 4 })
      .then(() => {
        addNotification(`Maintenance scheduled for ${machine.machine_code} — AI rerouting affected jobs.`, 'success')
        return client.get('/breakdown/risk').then((res) => setRisk(res.data))
      })
      .catch((err) => addNotification(err.response?.data?.detail || `Failed to schedule maintenance for ${machine.machine_code}.`, 'error'))
      .finally(() => setMaintenanceLoadingId(null))
  }

  return (
    <div>
      <h1 style={{ fontSize: 22, marginBottom: 4 }}>Analytics</h1>
      <p className="text-secondary" style={{ fontSize: 13, marginBottom: 24 }}>
        Resource utilization, predicted on-time delivery, and the schedule history log.
      </p>

      {/* KPI Stats Top */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 2fr', gap: 20, marginBottom: 32 }}>
        {/* OTD Prediction Gauge Card */}
        <div className="acrylic" style={{ padding: 20, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', textAlign: 'center' }}>
          <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--color-text-secondary)', marginBottom: 8 }}>
            OTD Prediction
          </span>
          <div style={{ fontSize: 36, fontWeight: 800, color: otd >= 80 ? '#4ade80' : otd >= 50 ? '#fbbf24' : '#ef4444' }}>
            {otd.toFixed(0)}%
          </div>
          <span className="text-tertiary" style={{ fontSize: 10.5, marginTop: 4 }}>
            predicted jobs on-schedule
          </span>
        </div>

        {/* Financial Impact Card */}
        <div className="acrylic" style={{ padding: 20 }}>
          <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--color-text-secondary)', display: 'block', marginBottom: 12 }}>
            Financial Impact
          </span>
          {financials ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                <span className="text-secondary" style={{ fontSize: 11 }}>Labor Cost</span>
                <span style={{ fontSize: 15, fontWeight: 700 }}>₹{financials.total_labor_cost.toLocaleString()}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                <span className="text-secondary" style={{ fontSize: 11 }}>Profit Secured ({financials.jobs_on_time_count})</span>
                <span style={{ fontSize: 15, fontWeight: 700, color: '#4ade80' }}>₹{financials.profit_on_time.toLocaleString()}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                <span className="text-secondary" style={{ fontSize: 11 }}>Profit At Risk ({financials.jobs_at_risk_count})</span>
                <span style={{ fontSize: 15, fontWeight: 700, color: '#ef4444' }}>₹{financials.profit_at_risk.toLocaleString()}</span>
              </div>
            </div>
          ) : (
            <p className="text-tertiary" style={{ fontSize: 12 }}>Loading…</p>
          )}
        </div>

        {/* Bottleneck Heatmap Card */}
        <div className="acrylic" style={{ padding: 20 }}>
          <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--color-text-secondary)', display: 'block', marginBottom: 12 }}>
            Bottleneck Detector Heatmap
          </span>
          <div className="flex gap-8" style={{ display: 'flex', flexWrap: 'wrap' }}>
            {utilization.map(u => {
              const tardyMinutes = bottlenecks[u.machine_id] || 0
              const isHot = tardyMinutes > 0
              return (
                <div 
                  key={u.machine_id} 
                  style={{ 
                    flex: 1, 
                    minWidth: 100, 
                    padding: 12, 
                    borderRadius: 8, 
                    background: getHeatmapColor(tardyMinutes),
                    border: isHot ? '1px solid rgba(239,68,68,0.2)' : '1px solid rgba(255,255,255,0.02)',
                    textAlign: 'center'
                  }}
                >
                  <div style={{ fontSize: 13, fontWeight: 700 }}>{u.machine_code}</div>
                  <div className="text-secondary" style={{ fontSize: 9.5, marginTop: 4 }}>
                    {tardyMinutes > 0 ? `${(tardyMinutes / 60).toFixed(1)}h delay` : 'No delay'}
                  </div>
                </div>
              )
            })}
            {utilization.length === 0 && <p className="text-tertiary" style={{ fontSize: 12 }}>No machine bottleneck data.</p>}
          </div>
        </div>
      </div>

      <h3 style={{ fontSize: 14, marginBottom: 12 }}>Machine Utilization</h3>
      <div className="flex gap-16" style={{ flexWrap: 'wrap', marginBottom: 32 }}>
        {utilization.map((u) => (
          <UtilizationGauge key={u.machine_id} machineCode={u.machine_code} utilizationPct={u.utilization_pct} />
        ))}
        {utilization.length === 0 && <p className="text-tertiary">No utilization data yet — run an optimization first.</p>}
      </div>

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <h3 style={{ fontSize: 14, margin: 0 }}>Predictive Maintenance</h3>
        <button className="btn btn-secondary" style={{ fontSize: 12, padding: '6px 12px' }} onClick={recalculateRisk} disabled={riskLoading}>
          {riskLoading ? 'Recalculating…' : 'Recalculate Risk'}
        </button>
      </div>
      {riskError && (
        <p style={{ fontSize: 12, color: '#ef4444', marginBottom: 8 }}>{riskError}</p>
      )}
      <div className="acrylic" style={{ padding: 0, overflow: 'hidden', marginBottom: 32 }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12.5 }}>
          <thead>
            <tr style={{ textAlign: 'left', borderBottom: '1px solid var(--color-acrylic-border)' }}>
              <th style={th}>Machine</th>
              <th style={th}>Type</th>
              <th style={th}>Failure Risk</th>
              <th style={th}>Hours Since Maintenance</th>
              <th style={th}>Age (yrs)</th>
              <th style={th}>Past Breakdowns</th>
              <th style={th}>Action</th>
            </tr>
          </thead>
          <tbody>
            {risk.map((m) => (
              <tr key={m.machine_id} style={{ borderBottom: '1px solid rgba(255,255,255,0.03)' }}>
                <td style={td} className="mono">{m.machine_code}</td>
                <td style={td}>{m.machine_type}</td>
                <td style={td}>
                  <span style={{ fontWeight: 700, color: RISK_COLOR[m.risk_level] || RISK_COLOR.low }}>
                    {(m.failure_risk_score * 100).toFixed(1)}%
                  </span>
                  <span className="text-tertiary" style={{ marginLeft: 6, textTransform: 'capitalize', fontSize: 10.5 }}>
                    {m.risk_level}
                  </span>
                </td>
                <td style={td}>{m.hours_since_last_maintenance.toFixed(0)}h</td>
                <td style={td}>{m.age_years}</td>
                <td style={td}>{m.historical_breakdown_count}</td>
                <td style={td}>
                  {m.risk_level === 'high' && m.status !== 'offline' && (
                    <button
                      className="btn btn-secondary"
                      style={{ fontSize: 11, padding: '4px 10px' }}
                      disabled={maintenanceLoadingId === m.machine_id}
                      onClick={() => scheduleMaintenance(m)}
                    >
                      {maintenanceLoadingId === m.machine_id ? 'Scheduling…' : 'Schedule Maintenance'}
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {risk.length === 0 && (
              <tr><td style={td} colSpan={7} className="text-tertiary">No machine data yet.</td></tr>
            )}
          </tbody>
        </table>
      </div>

      <h3 style={{ fontSize: 14, marginBottom: 12 }}>Schedule History Log</h3>
      <div className="acrylic" style={{ padding: 0, overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12.5 }}>
          <thead>
            <tr style={{ textAlign: 'left', borderBottom: '1px solid var(--color-acrylic-border)' }}>
              <th style={th}>Time</th>
              <th style={th}>Entity</th>
              <th style={th}>Action</th>
              <th style={th}>By</th>
            </tr>
          </thead>
          <tbody>
            {auditLog.map((log) => (
              <tr key={log.log_id} style={{ borderBottom: '1px solid rgba(255,255,255,0.03)' }}>
                <td style={td} className="mono text-tertiary">{new Date(log.changed_at).toLocaleString()}</td>
                <td style={td}>{log.entity_type} #{log.entity_id}</td>
                <td style={td}>
                  <span className="badge badge-online" style={{ textTransform: 'capitalize' }}>{log.action.replace('_', ' ')}</span>
                </td>
                <td style={td}>{log.changed_by_name}</td>
              </tr>
            ))}
            {auditLog.length === 0 && (
              <tr><td style={td} colSpan={4} className="text-tertiary">No history yet.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

const th = { padding: '10px 16px', fontWeight: 600, color: 'var(--color-text-secondary)' }
const td = { padding: '10px 16px' }
