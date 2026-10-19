import { useState } from 'react'

const GOALS = [
  { id: 'minimize_makespan', label: 'Maximize Speed', description: 'Finish every job as fast as possible.' },
  { id: 'minimize_tardiness', label: 'On-Time Priority', description: 'Protect due dates above all else.' },
  { id: 'maximize_profit', label: 'Maximize Profit', description: 'Weight high-value jobs heavily.' },
  { id: 'balanced', label: 'Balanced', description: 'Blend speed and on-time delivery.' },
]

export default function AIControlCenter({ onOptimize, runStatus, onApplyPreset }) {
  const [goal, setGoal] = useState('balanced')
  const [preset, setPreset] = useState('rush_order')
  const isRunning = runStatus === 'queued' || runStatus === 'running'

  return (
    <div className="acrylic" style={{ padding: 20 }}>
      <div className="flex justify-between items-center" style={{ marginBottom: 14 }}>
        <div>
          <h3 style={{ fontSize: 15 }}>AI Control Center</h3>
          <p className="text-secondary" style={{ fontSize: 12, marginTop: 3 }}>
            Choose an optimization priority, then run the engine.
          </p>
        </div>
        {runStatus && (
          <span className={`badge ${isRunning ? 'badge-warning' : 'badge-online'}`}>
            <span className="badge-dot" /> {runStatus}
          </span>
        )}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 16 }}>
        {GOALS.map((g) => (
          <button
            key={g.id}
            onClick={() => setGoal(g.id)}
            className="btn"
            style={{
              textAlign: 'left',
              alignItems: 'flex-start',
              flexDirection: 'column',
              display: 'flex',
              gap: 2,
              border: goal === g.id ? '1px solid var(--color-aurora-teal)' : '1px solid var(--color-acrylic-border)',
              background: goal === g.id ? 'rgba(79,209,197,0.1)' : 'var(--color-acrylic)',
            }}
          >
            <span style={{ fontSize: 13 }}>{g.label}</span>
            <span className="text-tertiary" style={{ fontSize: 11, fontWeight: 400 }}>{g.description}</span>
          </button>
        ))}
      </div>

      <button className="btn btn-primary" style={{ width: '100%' }} disabled={isRunning} onClick={() => onOptimize(goal)}>
        {isRunning ? 'Optimizing…' : '▶ Run AI Optimization'}
      </button>

      {onApplyPreset && (
        <div style={{ marginTop: 14, paddingTop: 14, borderTop: '1px solid var(--color-acrylic-border)' }}>
          <h4 style={{ fontSize: 13, marginBottom: 8 }}>One-Click Demo Presets</h4>
          <div className="flex gap-8" style={{ display: 'flex' }}>
            <select 
              value={preset} 
              onChange={(e) => setPreset(e.target.value)} 
              style={{ flex: 1, fontSize: 12.5 }}
              disabled={isRunning}
            >
              <option value="reset">Default Factory (FJSP)</option>
              <option value="job_shop">Traditional Job Shop (JSP)</option>
              <option value="flow_shop">Flow Shop Scheduling (FSP)</option>
              <option value="employee_shift">Employee Shift Scheduling</option>
              <option value="resource_allocation">Resource & Task Allocation</option>
              <option value="rush_order">Rush Order Crisis (FJSP)</option>
              <option value="cnc_breakdown">CNC-02 Sudden Failure (FJSP)</option>
            </select>
            <button 
              type="button"
              className="btn btn-secondary" 
              onClick={() => onApplyPreset(preset)}
              disabled={isRunning}
              style={{ padding: '6px 12px', fontSize: 12 }}
            >
              Apply
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
