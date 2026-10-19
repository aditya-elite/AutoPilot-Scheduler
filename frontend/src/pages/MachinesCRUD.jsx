import { useEffect, useState, useCallback, useRef } from 'react'
import client from '../api/client'

const MACHINE_TYPES = ['CNC_MILL', 'LATHE', 'WELDING_STATION', 'ASSEMBLY_LINE', 'QUALITY_CHECK']
const STATUSES = ['online', 'offline', 'maintenance', 'degraded']

export default function MachinesCRUD() {
  const [machines, setMachines] = useState([])
  const [error, setError] = useState('')
  const [toast, setToast] = useState('')
  const [editingId, setEditingId] = useState(null)
  
  const [form, setForm] = useState({
    machine_code: '',
    machine_name: '',
    machine_type: 'CNC_MILL',
    cost_per_hour: 40.0,
    status: 'online'
  })
  
  const [saving, setSaving] = useState(false)
  const mountedRef = useRef(true)

  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
    }
  }, [])

  const load = useCallback(async () => {
    try {
      const res = await client.get('/machines')
      if (!mountedRef.current) return
      setMachines(res.data)
    } catch (err) {
      setError('Failed to load machines')
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const showToast = (msg) => {
    setToast(msg)
    setTimeout(() => {
      setToast('')
    }, 3000)
  }

  const handleEditSelect = (m) => {
    setEditingId(m.machine_id)
    setForm({
      machine_code: m.machine_code,
      machine_name: m.machine_name,
      machine_type: m.machine_type,
      cost_per_hour: m.cost_per_hour,
      status: m.status
    })
  }

  const handleCancelEdit = () => {
    setEditingId(null)
    setForm({
      machine_code: '',
      machine_name: '',
      machine_type: 'CNC_MILL',
      cost_per_hour: 40.0,
      status: 'online'
    })
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setSaving(true)
    try {
      if (editingId) {
        await client.put(`/machines/${editingId}`, form)
        showToast('Machine updated successfully!')
      } else {
        await client.post('/machines', form)
        showToast('Machine created successfully!')
      }
      handleCancelEdit()
      await load()
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to save machine')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (machineId) => {
    if (!window.confirm('Are you sure you want to delete this machine? This will also remove any eligibility records and plans associated with it.')) {
      return
    }
    setError('')
    try {
      await client.delete(`/machines/${machineId}`)
      showToast('Machine deleted successfully!')
      if (editingId === machineId) {
        handleCancelEdit()
      }
      await load()
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to delete machine')
    }
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: 20 }}>
      <div>
        <h1 style={{ fontSize: 22, marginBottom: 4 }}>Resources & Machines</h1>
        <p className="text-secondary" style={{ fontSize: 13, marginBottom: 20 }}>
          Manage production line equipment, operating types, and hourly costs.
        </p>

        {toast && (
          <div className="acrylic" style={{ padding: '8px 12px', marginBottom: 16, fontSize: 12.5, color: '#4ade80' }}>
            ✓ {toast}
          </div>
        )}

        <div className="acrylic" style={{ padding: 0, overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12.5 }}>
            <thead>
              <tr style={{ textAlign: 'left', borderBottom: '1px solid var(--color-acrylic-border)' }}>
                <th style={th}>Code</th>
                <th style={th}>Name</th>
                <th style={th}>Type</th>
                <th style={th}>Cost/Hour</th>
                <th style={th}>Status</th>
                <th style={th}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {machines.map((m) => (
                <tr key={m.machine_id} style={{ borderBottom: '1px solid rgba(255,255,255,0.03)' }}>
                  <td style={td} className="mono">{m.machine_code}</td>
                  <td style={td}>{m.machine_name}</td>
                  <td className="mono" style={{ ...td, fontSize: 11 }}>{m.machine_type}</td>
                  <td style={td}>₹{parseFloat(m.cost_per_hour).toFixed(2)}</td>
                  <td style={td}>
                    <span className={`badge badge-${m.status}`}>
                      <span className="badge-dot" /> {m.status}
                    </span>
                  </td>
                  <td style={td}>
                    <div className="flex gap-8">
                      <button className="btn" style={{ padding: '4px 8px', fontSize: 11 }} onClick={() => handleEditSelect(m)}>
                        Edit
                      </button>
                      <button className="btn btn-danger" style={{ padding: '4px 8px', fontSize: 11 }} onClick={() => handleDelete(m.machine_id)}>
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div>
        <div className="acrylic" style={{ padding: 20, position: 'sticky', top: 20 }}>
          <h3 style={{ fontSize: 14, marginBottom: 14 }}>
            {editingId ? 'Edit Resource' : 'Add New Resource'}
          </h3>
          
          <form onSubmit={handleSubmit} className="flex-col gap-12" style={{ display: 'flex' }}>
            <label className="flex-col gap-8" style={{ display: 'flex' }}>
              <span className="text-secondary" style={{ fontSize: 11.5 }}>Machine Code</span>
              <input 
                placeholder="e.g. CNC-03" 
                value={form.machine_code} 
                onChange={(e) => setForm(f => ({ ...f, machine_code: e.target.value }))} 
                required 
              />
            </label>

            <label className="flex-col gap-8" style={{ display: 'flex' }}>
              <span className="text-secondary" style={{ fontSize: 11.5 }}>Machine Name</span>
              <input 
                placeholder="e.g. CNC Router 3" 
                value={form.machine_name} 
                onChange={(e) => setForm(f => ({ ...f, machine_name: e.target.value }))} 
                required 
              />
            </label>

            <label className="flex-col gap-8" style={{ display: 'flex' }}>
              <span className="text-secondary" style={{ fontSize: 11.5 }}>Machine Type</span>
              <select 
                value={form.machine_type} 
                onChange={(e) => setForm(f => ({ ...f, machine_type: e.target.value }))}
              >
                {MACHINE_TYPES.map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
            </label>

            <label className="flex-col gap-8" style={{ display: 'flex' }}>
              <span className="text-secondary" style={{ fontSize: 11.5 }}>Cost Per Hour (₹)</span>
              <input 
                type="number" 
                step="0.01" 
                min="0"
                value={form.cost_per_hour} 
                onChange={(e) => setForm(f => ({ ...f, cost_per_hour: parseFloat(e.target.value) || 0 }))} 
                required 
              />
            </label>

            <label className="flex-col gap-8" style={{ display: 'flex' }}>
              <span className="text-secondary" style={{ fontSize: 11.5 }}>Operational Status</span>
              <select 
                value={form.status} 
                onChange={(e) => setForm(f => ({ ...f, status: e.target.value }))}
              >
                {STATUSES.map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </label>

            {error && <div style={{ color: 'var(--color-danger)', fontSize: 12 }}>{error}</div>}

            <div className="flex gap-8" style={{ display: 'flex', marginTop: 8 }}>
              <button type="submit" className="btn btn-primary" style={{ flex: 1 }} disabled={saving}>
                {saving ? 'Saving…' : editingId ? 'Update' : 'Create'}
              </button>
              {editingId && (
                <button type="button" className="btn" style={{ flex: 1 }} onClick={handleCancelEdit}>
                  Cancel
                </button>
              )}
            </div>
          </form>
        </div>
      </div>
    </div>
  )
}

const th = { padding: '10px 14px', fontWeight: 600, color: 'var(--color-text-secondary)' }
const td = { padding: '10px 14px' }
