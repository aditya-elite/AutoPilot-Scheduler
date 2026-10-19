import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'

const TICKER_LOGS = [
  '⚡ Initializing CP-SAT solver engine...',
  '📋 Loading 4 active jobs across 6 machines...',
  '🧼 Enforcing 15-min setup buffers between priorities...',
  '🎉 Solved! Makespan 150m · Tardiness 0m · OTD 100%',
  '🩺 All machines healthy — vibration within limits',
]

export default function LandingPage() {
  const navigate = useNavigate()
  const [tickerIdx, setTickerIdx] = useState(0)

  useEffect(() => {
    const t = setInterval(() => setTickerIdx(i => (i + 1) % TICKER_LOGS.length), 3000)
    return () => clearInterval(t)
  }, [])

  return (
    <div style={{ minHeight: '100vh', background: '#fff', color: '#202124', fontFamily: 'var(--font-body)', position: 'relative', zIndex: 1 }}>

      {/* Navbar */}
      <header style={{ padding: '12px 32px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #e8eaed' }}>
        <span style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: 17, color: '#1a73e8' }}>
          AutoPilot Scheduler
        </span>
        <div style={{ display: 'flex', gap: 10 }}>
          <button className="btn btn-ghost" onClick={() => navigate('/login?mode=login')} style={{ fontSize: 13, padding: '6px 14px' }}>Sign In</button>
          <button className="btn btn-primary" onClick={() => navigate('/login?mode=signup')} style={{ fontSize: 13, padding: '6px 16px' }}>Get Started</button>
        </div>
      </header>

      {/* Hero */}
      <section style={{ maxWidth: 960, margin: '0 auto', padding: '56px 24px 40px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 48, alignItems: 'center' }}>

        <div>
          <h1 style={{ fontFamily: 'var(--font-display)', fontSize: 36, fontWeight: 700, color: '#202124', lineHeight: 1.15, letterSpacing: '-0.02em', margin: '0 0 14px' }}>
            AI Production Scheduling
          </h1>
          <p style={{ fontSize: 15, lineHeight: 1.6, color: '#5f6368', margin: '0 0 24px', maxWidth: 420 }}>
            Automatically optimize machine assignments, enforce setup buffers, predict failures, and hit every delivery deadline.
          </p>
          <div style={{ display: 'flex', gap: 10, marginBottom: 28 }}>
            <button className="btn btn-primary" style={{ padding: '10px 22px', fontSize: 13.5 }} onClick={() => navigate('/login?mode=signup')}>Create Account</button>
            <button className="btn btn-ghost" style={{ padding: '10px 20px', fontSize: 13.5 }} onClick={() => navigate('/login?mode=login')}>Sign In</button>
          </div>

          {/* Terminal Ticker */}
          <div style={{ background: '#1e1e1e', color: '#34a853', padding: '8px 14px', borderRadius: 6, fontFamily: 'monospace', fontSize: 11.5, minHeight: 32, display: 'flex', alignItems: 'center', transition: 'opacity 0.3s' }}>
            {TICKER_LOGS[tickerIdx]}
          </div>
        </div>

        {/* Mini Gantt Mock */}
        <div style={{ background: '#f8f9fa', border: '1px solid #e8eaed', borderRadius: 12, padding: '18px 20px', boxShadow: '0 1px 6px rgba(0,0,0,0.04)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
            <span style={{ fontSize: 12, fontWeight: 700, color: '#202124' }}>Live Schedule Preview</span>
            <span style={{ fontSize: 10, color: '#1a73e8', fontWeight: 600 }}>Today</span>
          </div>

          {[
            { machine: 'CNC-01', left: '8%', width: '45%', color: '#1a73e8', bg: '#e8f0fe', label: 'SO-1001 Mill' },
            { machine: 'LATHE', left: '18%', width: '32%', color: '#137333', bg: '#e6f4ea', label: 'SO-1002 Turn' },
            { machine: 'WELD', left: '38%', width: '40%', color: '#b06000', bg: '#fef7e0', label: 'SO-1003 Weld' },
          ].map((row, i) => (
            <div key={i} style={{ display: 'grid', gridTemplateColumns: '52px 1fr', gap: 10, alignItems: 'center', marginBottom: 8 }}>
              <span style={{ fontSize: 10, fontWeight: 600, color: '#5f6368', fontFamily: 'monospace' }}>{row.machine}</span>
              <div style={{ height: 24, background: '#eee', borderRadius: 4, position: 'relative', overflow: 'hidden' }}>
                <div style={{ position: 'absolute', left: row.left, width: row.width, height: '100%', background: row.bg, border: `1px solid ${row.color}`, borderRadius: 4, display: 'flex', alignItems: 'center', paddingLeft: 6 }}>
                  <span style={{ fontSize: 9, fontWeight: 600, color: row.color, whiteSpace: 'nowrap' }}>{row.label}</span>
                </div>
              </div>
            </div>
          ))}

          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 9, color: '#9aa0a6', marginTop: 10, borderTop: '1px solid #e8eaed', paddingTop: 8 }}>
            <span>09:00</span><span>12:00</span><span>17:00</span>
          </div>
        </div>
      </section>

      {/* Stats Bar */}
      <section style={{ background: '#f8f9fa', borderTop: '1px solid #e8eaed', borderBottom: '1px solid #e8eaed', padding: '20px 24px' }}>
        <div style={{ maxWidth: 960, margin: '0 auto', display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, textAlign: 'center' }}>
          {[
            { value: '< 30s', label: 'Solve Time' },
            { value: '100%', label: 'On-Time Delivery' },
            { value: '6+', label: 'Machine Types' },
            { value: '∞', label: 'What-If Scenarios' },
          ].map((s, i) => (
            <div key={i}>
              <div style={{ fontSize: 22, fontWeight: 700, color: '#1a73e8' }}>{s.value}</div>
              <div style={{ fontSize: 11, color: '#5f6368', marginTop: 2 }}>{s.label}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Features */}
      <section style={{ maxWidth: 960, margin: '0 auto', padding: '40px 24px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 20 }}>
          {[
            { icon: '📅', title: 'Gantt Timelines', desc: 'Drag-and-drop scheduling with constraint violation alerts and simulation playback.' },
            { icon: '⚡', title: 'CP-SAT Optimizer', desc: 'Google OR-Tools solver balancing makespan, tardiness, and machine utilization.' },
            { icon: '🩺', title: 'Predictive Health', desc: 'IoT telemetry dials monitoring spindle RPM, temperature, and vibration levels.' },
            { icon: '🚨', title: 'Live Alerts', desc: 'Instant breakdown warnings with automatic AI-triggered rerouting of affected jobs.' },
            { icon: '🤖', title: 'AI Scheduler Chat', desc: 'Ask questions about delays, bottlenecks, and machine health in plain English.' },
            { icon: '⚖️', title: 'Scenario Compare', desc: 'Side-by-side KPI analysis of different optimization strategies before committing.' },
          ].map((f, i) => (
            <div key={i} style={{ padding: '20px', background: '#f8f9fa', borderRadius: 10, border: '1px solid #e8eaed' }}>
              <div style={{ fontSize: 20, marginBottom: 8 }}>{f.icon}</div>
              <h3 style={{ fontSize: 13.5, fontWeight: 700, color: '#202124', margin: '0 0 6px' }}>{f.title}</h3>
              <p style={{ fontSize: 12, lineHeight: 1.5, color: '#5f6368', margin: 0 }}>{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Footer */}
      <footer style={{ borderTop: '1px solid #e8eaed', padding: '16px 24px', textAlign: 'center', fontSize: 11.5, color: '#9aa0a6' }}>
        © {new Date().getFullYear()} AutoPilot Scheduler · Built with Google OR-Tools
      </footer>
    </div>
  )
}
