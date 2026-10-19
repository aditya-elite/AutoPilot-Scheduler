import { useEffect, useState } from 'react'

export default function BreakdownSimulator({ machines, onMarkOffline, onRestore }) {
  return (
    <div className="acrylic" style={{ padding: 20 }}>
      <h3 style={{ fontSize: 15 }}>Breakdown Simulator & IoT Dials</h3>
      <p className="text-secondary" style={{ fontSize: 12, marginTop: 3, marginBottom: 14 }}>
        Simulate unexpected downtime or inspect live machine health telemetry logs.
      </p>

      <div className="flex-col" style={{ display: 'flex' }}>
        {machines.map((m) => (
          <MachineTelemetryRow 
            key={m.machine_id} 
            m={m} 
            onRestore={onRestore} 
            onMarkOffline={onMarkOffline} 
          />
        ))}
      </div>
    </div>
  )
}

function MachineTelemetryRow({ m, onRestore, onMarkOffline }) {
  const [temp, setTemp] = useState(65)
  const [rpm, setRpm] = useState(2800)
  const [vib, setVib] = useState(1.4)
  
  const isOffline = m.status === 'offline'
  const risk = m.failure_risk_score || 0
  
  useEffect(() => {
    if (isOffline) {
      setTemp(24)
      setRpm(0)
      setVib(0.0)
      return
    }
    
    // Periodically fluctuate values in real-time
    const interval = setInterval(() => {
      setTemp(() => {
        const base = risk > 0.15 ? 82 : 70
        const delta = (Math.random() - 0.5) * 2
        return Math.round(base + delta)
      })
      
      setRpm(() => {
        const base = 2800
        const delta = Math.round((Math.random() - 0.5) * 100)
        return base + delta
      })
      
      setVib(() => {
        const base = risk > 0.15 ? 3.2 : 1.5
        const delta = (Math.random() - 0.5) * 0.4
        return parseFloat((base + delta).toFixed(1))
      })
    }, 2000)
    
    return () => clearInterval(interval)
  }, [isOffline, risk])

  // Get AI Health Status
  const getAIRecommendation = () => {
    if (isOffline) return null
    if (risk > 0.3) {
      return "AI: Spindle bearing replacement recommended next shift."
    }
    if (risk > 0.15) {
      return "AI: Degraded lubrication. Scheduled service within 24h."
    }
    return "AI: Optimal operation. No action required."
  }

  return (
    <div className="flex-col gap-6" style={{ display: 'flex', padding: 12, borderRadius: 10, background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.03)', marginBottom: 8 }}>
      <div className="flex justify-between items-center" style={{ display: 'flex' }}>
        <div>
          <div style={{ fontSize: 13, fontWeight: 700 }}>{m.machine_code}</div>
          <div className="text-secondary" style={{ fontSize: 10.5 }}>{m.machine_name}</div>
        </div>
        <div className="flex gap-6 items-center" style={{ display: 'flex' }}>
          <span className={`badge badge-${m.status}`} style={{ fontSize: 10.5 }}>
            <span className="badge-dot" /> {m.status}
          </span>
          {isOffline ? (
            <button className="btn" style={{ padding: '3px 8px', fontSize: 10.5 }} onClick={() => onRestore(m.machine_id)}>
              Restore
            </button>
          ) : (
            <button className="btn btn-danger" style={{ padding: '3px 8px', fontSize: 10.5 }} onClick={() => onMarkOffline(m.machine_id)}>
              Offline
            </button>
          )}
        </div>
      </div>
      
      {/* Telemetry Dials */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 6, marginTop: 4 }}>
        <div style={{ background: 'rgba(255,255,255,0.02)', padding: '6px 8px', borderRadius: 6, textAlign: 'center' }}>
          <div className="text-tertiary" style={{ fontSize: 9.5 }}>Spindle</div>
          <div className="mono" style={{ fontSize: 11.5, fontWeight: 600 }}>{rpm} RPM</div>
        </div>
        <div style={{ 
          background: !isOffline && temp > 80 ? 'rgba(239, 68, 68, 0.1)' : 'rgba(255,255,255,0.02)', 
          padding: '6px 8px', 
          borderRadius: 6, 
          textAlign: 'center',
          color: !isOffline && temp > 80 ? '#f87171' : 'inherit'
        }}>
          <div className="text-tertiary" style={{ fontSize: 9.5 }}>Temp</div>
          <div className="mono" style={{ fontSize: 11.5, fontWeight: 600 }}>{temp}°C</div>
        </div>
        <div style={{ 
          background: !isOffline && vib > 3.0 ? 'rgba(245, 158, 11, 0.1)' : 'rgba(255,255,255,0.02)', 
          padding: '6px 8px', 
          borderRadius: 6, 
          textAlign: 'center',
          color: !isOffline && vib > 3.0 ? '#fcd34d' : 'inherit'
        }}>
          <div className="text-tertiary" style={{ fontSize: 9.5 }}>Vibration</div>
          <div className="mono" style={{ fontSize: 11.5, fontWeight: 600 }}>{vib} mm/s</div>
        </div>
      </div>
      
      {/* AI Recommendation log */}
      {getAIRecommendation() && (
        <div style={{ 
          fontSize: 10, 
          background: risk > 0.15 ? 'rgba(239,68,68,0.05)' : 'rgba(74,222,128,0.05)',
          color: risk > 0.15 ? '#f87171' : '#4ade80',
          padding: '4px 8px', 
          borderRadius: 4, 
          borderLeft: risk > 0.15 ? '2px solid #ef4444' : '2px solid #4ade80'
        }}>
          {getAIRecommendation()}
        </div>
      )}
    </div>
  )
}
