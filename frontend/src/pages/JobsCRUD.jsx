import { useEffect, useState, useCallback, useRef } from 'react'
import client from '../api/client'

export default function JobsCRUD() {
  const [jobs, setJobs] = useState([])
  const [machines, setMachines] = useState([])
  const [error, setError] = useState('')
  const [toast, setToast] = useState('')
  const [selectedJob, setSelectedJob] = useState(null)
  
  // Job Form state
  const [jobForm, setJobForm] = useState({
    job_code: '',
    description: '',
    priority_weight: 5,
    profit_value: 1000.0,
    due_date: ''
  })

  // Tasks Recipe state
  const [tasks, setTasks] = useState([]) // array of { sequence_index, task_name, base_duration_minutes, eligible_machines: [{machine_id, processing_minutes}] }

  const [saving, setSaving] = useState(false)
  const mountedRef = useRef(true)

  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
    }
  }, [])

  const loadAll = useCallback(async () => {
    try {
      const [jobsRes, machinesRes] = await Promise.all([
        client.get('/jobs'),
        client.get('/machines')
      ])
      if (!mountedRef.current) return
      setJobs(jobsRes.data)
      setMachines(machinesRes.data)
    } catch (err) {
      setError('Failed to load jobs or machines')
    }
  }, [])

  useEffect(() => {
    loadAll()
  }, [loadAll])

  const showToast = (msg) => {
    setToast(msg)
    setTimeout(() => {
      setToast('')
    }, 3000)
  }

  const formatDateTimeLocal = (dateString) => {
    if (!dateString) return ''
    const d = new Date(dateString)
    const year = d.getFullYear()
    const month = String(d.getMonth() + 1).padStart(2, '0')
    const day = String(d.getDate()).padStart(2, '0')
    const hours = String(d.getHours()).padStart(2, '0')
    const minutes = String(d.getMinutes()).padStart(2, '0')
    return `${year}-${month}-${day}T${hours}:${minutes}`
  }

  const handleJobSelect = (j) => {
    setSelectedJob(j)
    setJobForm({
      job_code: j.job_code,
      description: j.description || '',
      priority_weight: j.priority_weight,
      profit_value: j.profit_value,
      due_date: formatDateTimeLocal(j.due_date)
    })
    
    // Convert backend task shape into local state shape
    const loadedTasks = (j.tasks || []).map(t => ({
      task_id: t.task_id,
      sequence_index: t.sequence_index,
      task_name: t.task_name,
      base_duration_minutes: t.base_duration_minutes,
      eligible_machines: (t.eligible_machines || []).map(e => ({
        machine_id: e.machine_id,
        processing_minutes: e.processing_minutes
      }))
    }))
    setTasks(loadedTasks.sort((a,b) => a.sequence_index - b.sequence_index))
  }

  const handleCancelEdit = () => {
    setSelectedJob(null)
    setJobForm({
      job_code: '',
      description: '',
      priority_weight: 5,
      profit_value: 1000.0,
      due_date: ''
    })
    setTasks([])
  }

  const handleAddStep = () => {
    setTasks(t => [
      ...t,
      {
        sequence_index: t.length,
        task_name: '',
        base_duration_minutes: 30,
        eligible_machines: []
      }
    ])
  }

  const handleRemoveStep = (index) => {
    setTasks(t => t.filter((_, i) => i !== index).map((item, idx) => ({ ...item, sequence_index: idx })))
  }

  const handleTaskFieldChange = (index, field, value) => {
    setTasks(t => t.map((item, idx) => idx === index ? { ...item, [field]: value } : item))
  }

  const handleToggleEligibility = (taskIndex, machineId) => {
    setTasks(t => t.map((item, idx) => {
      if (idx !== taskIndex) return item
      const exists = item.eligible_machines.some(e => e.machine_id === machineId)
      let newEligible
      if (exists) {
        newEligible = item.eligible_machines.filter(e => e.machine_id !== machineId)
      } else {
        newEligible = [...item.eligible_machines, { machine_id: machineId, processing_minutes: item.base_duration_minutes }]
      }
      return { ...item, eligible_machines: newEligible }
    }))
  }

  const handleEligibilityTimeChange = (taskIndex, machineId, time) => {
    setTasks(t => t.map((item, idx) => {
      if (idx !== taskIndex) return item
      const newEligible = item.eligible_machines.map(e => 
        e.machine_id === machineId ? { ...e, processing_minutes: parseInt(time) || 1 } : e
      )
      return { ...item, eligible_machines: newEligible }
    }))
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    
    // Basic validation
    if (tasks.length === 0) {
      setError('Please add at least one step to the process routing.')
      return
    }
    
    for (let i = 0; i < tasks.length; i++) {
      if (!tasks[i].task_name.trim()) {
        setError(`Please enter a name for Step ${i + 1}.`)
        return
      }
      if (tasks[i].eligible_machines.length === 0) {
        setError(`Please assign at least one eligible machine for Step ${i + 1} (${tasks[i].task_name}).`)
        return
      }
    }

    setSaving(true)
    try {
      const payload = {
        ...jobForm,
        due_date: new Date(jobForm.due_date).toISOString()
      }
      
      if (selectedJob) {
        // Update Job info
        await client.put(`/jobs/${selectedJob.job_id}`, payload)
        // Update Job tasks/routes
        await client.put(`/jobs/${selectedJob.job_id}/tasks`, tasks)
        showToast('Job and routing updated successfully!')
      } else {
        // Create Job with tasks in one call
        const fullPayload = {
          ...payload,
          tasks: tasks
        }
        await client.post('/jobs', fullPayload)
        showToast('Job and routing created successfully!')
      }
      
      handleCancelEdit()
      await loadAll()
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to save job routing')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (jobId) => {
    if (!window.confirm('Are you sure you want to delete this job? This will cascade-delete all its tasks, machine eligibilities, and scheduling assignments.')) {
      return
    }
    setError('')
    try {
      await client.delete(`/jobs/${jobId}`)
      showToast('Job deleted successfully!')
      if (selectedJob?.job_id === jobId) {
        handleCancelEdit()
      }
      await loadAll()
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to delete job')
    }
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
      {/* Left panel: list of jobs */}
      <div>
        <h1 style={{ fontSize: 22, marginBottom: 4 }}>Jobs & Process Routing</h1>
        <p className="text-secondary" style={{ fontSize: 13, marginBottom: 20 }}>
          Define production orders, due dates, priorities, and step-by-step routing recipes.
        </p>

        {toast && (
          <div className="acrylic" style={{ padding: '8px 12px', marginBottom: 16, fontSize: 12.5, color: '#4ade80' }}>
            ✓ {toast}
          </div>
        )}

        <div className="flex-col gap-10" style={{ display: 'flex' }}>
          {jobs.map((j) => (
            <div 
              key={j.job_id} 
              className={`acrylic ${selectedJob?.job_id === j.job_id ? 'border-primary' : ''}`}
              style={{ 
                padding: 16, 
                cursor: 'pointer', 
                border: selectedJob?.job_id === j.job_id ? '1px solid var(--color-primary)' : '1px solid var(--color-acrylic-border)' 
              }}
              onClick={() => handleJobSelect(j)}
            >
              <div className="flex justify-between items-center" style={{ marginBottom: 6 }}>
                <span className="mono" style={{ fontSize: 13.5, fontWeight: 700 }}>{j.job_code}</span>
                <span className={`badge badge-${j.priority_weight >= 8 ? 'critical' : j.priority_weight >= 5 ? 'online' : 'offline'}`} style={{ fontSize: 10.5 }}>
                  Priority: {j.priority_weight}
                </span>
              </div>
              <p className="text-secondary" style={{ fontSize: 12, margin: '4px 0' }}>{j.description || 'No description'}</p>
              
              <div className="flex justify-between text-tertiary" style={{ fontSize: 11, marginTop: 10 }}>
                <span>Profit: ₹{parseFloat(j.profit_value).toLocaleString()}</span>
                <span>Due: {new Date(j.due_date).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' })}</span>
              </div>

              {/* Tasks preview */}
              <div style={{ marginTop: 12, display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                {(j.tasks || []).map((t, idx) => (
                  <span key={t.task_id} style={{ fontSize: 10, background: 'rgba(255,255,255,0.05)', padding: '2px 6px', borderRadius: 4 }}>
                    {idx + 1}. {t.task_name}
                  </span>
                ))}
              </div>

              <div className="flex justify-end" style={{ marginTop: 10 }}>
                <button 
                  className="btn btn-danger" 
                  style={{ padding: '3px 8px', fontSize: 11 }} 
                  onClick={(e) => {
                    e.stopPropagation()
                    handleDelete(j.job_id)
                  }}
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Right panel: CRUD Form + Routing Recipe Builder */}
      <div>
        <div className="acrylic" style={{ padding: 20, position: 'sticky', top: 20 }}>
          <h3 style={{ fontSize: 14, marginBottom: 14 }}>
            {selectedJob ? `Edit Job & Route: ${selectedJob.job_code}` : 'Create New Job & Route'}
          </h3>

          <form onSubmit={handleSubmit} className="flex-col gap-12" style={{ display: 'flex' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <label className="flex-col gap-8" style={{ display: 'flex' }}>
                <span className="text-secondary" style={{ fontSize: 11.5 }}>Job Code</span>
                <input 
                  placeholder="e.g. SO-2026-1005"
                  value={jobForm.job_code}
                  onChange={(e) => setJobForm(f => ({ ...f, job_code: e.target.value }))}
                  required
                />
              </label>

              <label className="flex-col gap-8" style={{ display: 'flex' }}>
                <span className="text-secondary" style={{ fontSize: 11.5 }}>Due Date</span>
                <input 
                  type="datetime-local"
                  value={jobForm.due_date}
                  onChange={(e) => setJobForm(f => ({ ...f, due_date: e.target.value }))}
                  required
                />
              </label>
            </div>

            <label className="flex-col gap-8" style={{ display: 'flex' }}>
              <span className="text-secondary" style={{ fontSize: 11.5 }}>Description</span>
              <textarea 
                placeholder="e.g. Prototype batch for engineering team"
                value={jobForm.description}
                onChange={(e) => setJobForm(f => ({ ...f, description: e.target.value }))}
                style={{ resize: 'vertical', minHeight: 60 }}
              />
            </label>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <label className="flex-col gap-8" style={{ display: 'flex' }}>
                <span className="text-secondary" style={{ fontSize: 11.5 }}>Priority Weight (1-10)</span>
                <input 
                  type="number"
                  min="1"
                  max="10"
                  value={jobForm.priority_weight}
                  onChange={(e) => setJobForm(f => ({ ...f, priority_weight: parseInt(e.target.value) || 5 }))}
                  required
                />
              </label>

              <label className="flex-col gap-8" style={{ display: 'flex' }}>
                <span className="text-secondary" style={{ fontSize: 11.5 }}>Profit Value (₹)</span>
                <input 
                  type="number"
                  min="0"
                  step="0.01"
                  value={jobForm.profit_value}
                  onChange={(e) => setJobForm(f => ({ ...f, profit_value: parseFloat(e.target.value) || 0 }))}
                  required
                />
              </label>
            </div>

            {/* ROUTING RECIPE BUILDER */}
            <div style={{ marginTop: 14, borderTop: '1px solid var(--color-acrylic-border)', paddingTop: 14 }}>
              <div className="flex justify-between items-center" style={{ marginBottom: 12 }}>
                <h4 style={{ fontSize: 13, margin: 0 }}>Process Routing Recipe</h4>
                <button type="button" className="btn" style={{ padding: '4px 8px', fontSize: 11 }} onClick={handleAddStep}>
                  + Add Step
                </button>
              </div>

              <div className="flex-col gap-12" style={{ display: 'flex', maxHeight: 300, overflowY: 'auto', paddingRight: 6 }}>
                {tasks.map((t, idx) => (
                  <div key={idx} className="acrylic" style={{ padding: 12, background: 'rgba(255,255,255,0.015)' }}>
                    <div className="flex justify-between items-center" style={{ marginBottom: 8 }}>
                      <span style={{ fontSize: 11.5, fontWeight: 700 }}>Step {idx + 1}</span>
                      <button type="button" className="btn btn-ghost text-danger" style={{ padding: '2px 6px', fontSize: 11 }} onClick={() => handleRemoveStep(idx)}>
                        Remove
                      </button>
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 8, marginBottom: 8 }}>
                      <input 
                        placeholder="Step Name (e.g. Cut, Weld)"
                        value={t.task_name}
                        onChange={(e) => handleTaskFieldChange(idx, 'task_name', e.target.value)}
                        style={{ fontSize: 12, padding: '5px 8px' }}
                      />
                      <input 
                        type="number"
                        placeholder="Minutes"
                        min="1"
                        value={t.base_duration_minutes}
                        onChange={(e) => handleTaskFieldChange(idx, 'base_duration_minutes', parseInt(e.target.value) || 30)}
                        style={{ fontSize: 12, padding: '5px 8px' }}
                      />
                    </div>

                    {/* Machine Selector list for this step */}
                    <div style={{ marginTop: 8 }}>
                      <span className="text-secondary" style={{ fontSize: 10.5, display: 'block', marginBottom: 4 }}>Eligible Machines & Processing Times:</span>
                      <div className="flex-col gap-4" style={{ display: 'flex' }}>
                        {machines.map(m => {
                          const eligItem = t.eligible_machines.find(e => e.machine_id === m.machine_id)
                          const isEligible = !!eligItem
                          return (
                            <div key={m.machine_id} className="flex justify-between items-center" style={{ fontSize: 11, padding: '2px 4px' }}>
                              <label className="flex items-center gap-6" style={{ cursor: 'pointer' }}>
                                <input 
                                  type="checkbox" 
                                  checked={isEligible}
                                  onChange={() => handleToggleEligibility(idx, m.machine_id)}
                                />
                                <span>{m.machine_code} ({m.machine_name})</span>
                              </label>
                              {isEligible && (
                                <div className="flex items-center gap-4">
                                  <input 
                                    type="number"
                                    min="1"
                                    value={eligItem.processing_minutes}
                                    onChange={(e) => handleEligibilityTimeChange(idx, m.machine_id, e.target.value)}
                                    style={{ width: 60, fontSize: 10.5, padding: '2px 4px' }}
                                  />
                                  <span className="text-tertiary" style={{ fontSize: 10 }}>min</span>
                                </div>
                              )}
                            </div>
                          )
                        })}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {error && <div style={{ color: 'var(--color-danger)', fontSize: 12, marginTop: 8 }}>{error}</div>}

            <div className="flex gap-8" style={{ display: 'flex', marginTop: 14 }}>
              <button type="submit" className="btn btn-primary" style={{ flex: 1 }} disabled={saving}>
                {saving ? 'Saving…' : selectedJob ? 'Update Job & Route' : 'Create Job & Route'}
              </button>
              <button type="button" className="btn" style={{ flex: 1 }} onClick={handleCancelEdit}>
                Cancel / Clear
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  )
}
