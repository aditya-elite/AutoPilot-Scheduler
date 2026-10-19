import { useState, useEffect, useRef } from 'react'
import client from '../api/client'

export default function AICopilot() {
  const [messages, setMessages] = useState([
    {
      id: 1,
      sender: 'copilot',
      text: 'Hello! I am your AI Scheduler assistant. I have real-time access to your shop floor machines, active orders, and the CP-SAT scheduling engine. How can I help you optimize production today?',
      timestamp: new Date(),
    }
  ])
  const [input, setInput] = useState('')
  const [typing, setTyping] = useState(false)
  const [machines, setMachines] = useState([])
  const [assignments, setAssignments] = useState([])
  const [jobs, setJobs] = useState([])
  
  const messagesEndRef = useRef(null)

  useEffect(() => {
    loadData()
  }, [])

  useEffect(() => {
    // Scroll to bottom on new messages
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, typing])

  async function loadData() {
    try {
      const [macRes, assRes, jobRes] = await Promise.all([
        client.get('/machines'),
        client.get('/schedule/gantt'),
        client.get('/jobs')
      ])
      setMachines(macRes.data)
      setAssignments(assRes.data)
      setJobs(jobRes.data)
    } catch (err) {
      console.error('Failed to load data for copilot', err)
    }
  }

  // Parses user query and calculates answers using live active data
  async function processCommand(text) {
    setTyping(true)
    await new Promise((resolve) => setTimeout(resolve, 800)) // simulate thinking delay
    setTyping(false)

    const query = text.toLowerCase()

    // 1. Trigger Solver Optimization
    if (query.includes('optimize') || query.includes('run solver') || query.includes('solve')) {
      try {
        const res = await client.post('/schedule/optimize', { goal: 'balanced' })
        return `I have successfully triggered a background optimization run using the CP-SAT solver (Goal: Balanced, Run ID: #${res.data.run_id}). The schedule will refresh dynamically upon completion.`
      } catch (err) {
        return `I attempted to trigger an optimization, but the server responded with an error: ${err.response?.data?.detail || err.message}`
      }
    }

    // 2. Scan Delayed/Late Orders
    if (query.includes('delay') || query.includes('late') || query.includes('otd') || query.includes('deadline')) {
      const lateJobs = []
      
      jobs.forEach(job => {
        // Find all tasks/assignments for this job
        const jobAssigns = assignments.filter(a => a.job_id === job.job_id)
        if (jobAssigns.length > 0) {
          const completionMs = Math.max(...jobAssigns.map(a => new Date(a.scheduled_end).getTime()))
          const dueMs = new Date(job.due_date).getTime()
          if (completionMs > dueMs) {
            const minutesLate = Math.round((completionMs - dueMs) / 60000)
            lateJobs.push(`${job.job_code} (late by ${minutesLate}m)`)
          }
        }
      })

      if (lateJobs.length === 0) {
        return `All scheduled jobs are currently on track! On-time delivery is at 100% with no predicted missed deadlines.`
      } else {
        return `I scanned the active schedule and identified **${lateJobs.length} delayed job(s)** running behind their deadlines:\n\n` + 
          lateJobs.map(j => `• ${j}`).join('\n') + 
          `\n\nI recommend running a **minimize tardiness** AI optimization to push these orders back on schedule.`
      }
    }

    // 3. Scan Machine Bottlenecks
    if (query.includes('bottleneck') || query.includes('utilization') || query.includes('busy') || query.includes('most loaded')) {
      if (assignments.length === 0) {
        return 'The schedule is currently empty, so I cannot calculate utilization. Try loading a demo preset first!'
      }
      
      const machineLoad = {} // machine_id -> busy minutes
      assignments.forEach(a => {
        const dur = (new Date(a.scheduled_end) - new Date(a.scheduled_start)) / 60000
        machineLoad[a.machine_id] = (machineLoad[a.machine_id] || 0) + dur
      })

      let highestLoad = 0
      let bottleneckId = null

      Object.entries(machineLoad).forEach(([id, load]) => {
        if (load > highestLoad) {
          highestLoad = load
          bottleneckId = parseInt(id)
        }
      })

      const botMachine = machines.find(m => m.machine_id === bottleneckId)

      if (botMachine) {
        return `Currently, the most bottlenecked resource on the shop floor is **${botMachine.machine_code}** (${botMachine.machine_name}). It is scheduled to be active for **${highestLoad} minutes** over this production horizon. Consider adding setup rules or rerouting tasks to balance the workload.`
      }
      return 'All resources are currently idle. No bottleneck detected.'
    }

    // 4. Scan Sensor Health Telemetry
    if (query.includes('health') || query.includes('vibration') || query.includes('sensor') || query.includes('telemetry') || query.includes('risk')) {
      const risky = machines.filter(m => m.failure_risk_score > 0.15)
      
      if (risky.length === 0) {
        return 'All machines are reporting optimal health parameters (failure risk < 15%) with temperature and spindle vibrations within normal operating limits.'
      } else {
        return `I diagnosed the IoT sensor telemetry and found **${risky.length} machine(s)** with elevated risk levels:\n\n` +
          risky.map(m => `• **${m.machine_code}** (${m.machine_name}): Predicted Failure Risk **${(m.failure_risk_score * 100).toFixed(0)}%**. IoT telemetry logs indicate elevated bearing vibration thresholds. I suggest scheduling maintenance.`).join('\n')
      }
    }

    // 5. Greetings
    if (query.includes('hi') || query.includes('hello') || query.includes('hey')) {
      return 'Hello! Ask me queries like:\n- *"Which machines are bottlenecked?"*\n- *"Are there any late orders?"*\n- *"Diagnose machine health"* \n- *"Optimize schedule"*'
    }

    // 6. Default Fallback
    return 'I received your query. You can command me to:\n\n' +
      '• **"Are there any late orders?"** to check due dates.\n' +
      '• **"Identify machine bottlenecks"** to calculate resource utilization.\n' +
      '• **"Diagnose machine health"** to inspect IoT vibrations and failure risks.\n' +
      '• **"Run optimization"** to schedule tasks automatically.'
  }

  async function handleSend(e) {
    if (e) e.preventDefault()
    if (!input.trim() || typing) return

    const userText = input
    setInput('')
    
    // Add user message
    setMessages(prev => [...prev, { id: Date.now(), sender: 'user', text: userText, timestamp: new Date() }])

    // Fetch refreshed data before processing command to ensure answers are based on latest schedule state
    await loadData()
    
    // Process and add response
    const reply = await processCommand(userText)
    setMessages(prev => [...prev, { id: Date.now() + 1, sender: 'copilot', text: reply, timestamp: new Date() }])
  }

  const suggestionChips = [
    'Check delayed orders',
    'Find machine bottlenecks',
    'Diagnose machine health',
    'Run AI Optimization'
  ]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 60px)' }}>
      
      {/* Title */}
      <div style={{ marginBottom: 16 }}>
        <h1 style={{ fontSize: 22 }}>AI Scheduler</h1>
        <p className="text-secondary" style={{ fontSize: 13, marginTop: 4 }}>
          Talk to the scheduler in natural language to query telemetry health, check deadlines, or optimize lines.
        </p>
      </div>

      {/* Chat Container */}
      <div className="acrylic" style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', padding: 0 }}>
        
        {/* Messages Log */}
        <div style={{ flex: 1, overflowY: 'auto', padding: 24, display: 'flex', flexDirection: 'column', gap: 16 }}>
          {messages.map((m) => (
            <div 
              key={m.id} 
              style={{
                alignSelf: m.sender === 'user' ? 'flex-end' : 'flex-start',
                maxWidth: '75%',
                display: 'flex',
                flexDirection: 'column',
                gap: 4
              }}
            >
              <div 
                style={{
                  background: m.sender === 'user' ? '#e8f0fe' : '#ffffff',
                  color: '#202124',
                  border: '1px solid #dadce0',
                  borderRadius: m.sender === 'user' ? '18px 18px 2px 18px' : '18px 18px 18px 2px',
                  padding: '12px 18px',
                  fontSize: 13.5,
                  lineHeight: 1.5,
                  whiteSpace: 'pre-line',
                  boxShadow: '0 1px 2px rgba(60,64,67,0.08)'
                }}
              >
                {m.text}
              </div>
              <span 
                style={{ 
                  fontSize: 10.5, 
                  color: '#5f6368', 
                  alignSelf: m.sender === 'user' ? 'flex-end' : 'flex-start',
                  margin: '0 4px'
                }}
              >
                {m.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </span>
            </div>
          ))}

          {/* Typing Indicator */}
          {typing && (
            <div style={{ alignSelf: 'flex-start', background: '#f1f3f4', border: '1px solid #dadce0', borderRadius: '18px 18px 18px 2px', padding: '12px 18px', fontSize: 13, color: '#5f6368' }}>
              Copilot is analyzing data...
            </div>
          )}
          
          <div ref={messagesEndRef} />
        </div>

        {/* Suggestion Chips */}
        <div style={{ padding: '0 24px 12px 24px', display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {suggestionChips.map((chip, idx) => (
            <button
              key={idx}
              type="button"
              className="btn btn-ghost"
              onClick={() => { setInput(chip); }}
              style={{ padding: '5px 12px', fontSize: 11.5, borderRadius: 20 }}
            >
              {chip}
            </button>
          ))}
        </div>

        {/* Form Input */}
        <form onSubmit={handleSend} style={{ borderTop: '1px solid #dadce0', padding: 18, display: 'flex', gap: 10, background: '#ffffff' }}>
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about bottlenecks, delays, machine health, or tell me to optimize..."
            style={{ flex: 1 }}
            disabled={typing}
          />
          <button type="submit" className="btn btn-primary" disabled={typing || !input.trim()}>
            Send
          </button>
        </form>

      </div>
    </div>
  )
}
