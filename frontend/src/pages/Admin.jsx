import { useEffect, useState, useCallback, useRef } from 'react'
import client from '../api/client'

const ROLES = ['machine_operator', 'factory_manager', 'admin']

export default function Admin() {
  const [users, setUsers] = useState([])
  const [error, setError] = useState('')
  const [form, setForm] = useState({ username: '', password: '', full_name: '', role: 'machine_operator' })
  const [creating, setCreating] = useState(false)
  const mountedRef = useRef(true)

  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
    }
  }, [])

  const load = useCallback(async () => {
    const res = await client.get('/admin/users')
    if (!mountedRef.current) return
    setUsers(res.data)
  }, [])

  useEffect(() => {
    load()
  }, [load])

  async function handleCreate(e) {
    e.preventDefault()
    setError('')
    setCreating(true)
    try {
      await client.post('/admin/users', form)
      setForm({ username: '', password: '', full_name: '', role: 'machine_operator' })
      await load()
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create user')
    } finally {
      setCreating(false)
    }
  }

  async function toggleActive(user) {
    try {
      await client.patch(`/admin/users/${user.user_id}`, { is_active: !user.is_active })
      await load()
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update user')
    }
  }

  async function changeRole(user, role) {
    await client.patch(`/admin/users/${user.user_id}`, { role })
    await load()
  }

  return (
    <div style={{ maxWidth: 760 }}>
      <h1 style={{ fontSize: 22, marginBottom: 4 }}>Admin — Users</h1>
      <p className="text-secondary" style={{ fontSize: 13, marginBottom: 24 }}>
        Create accounts and manage roles. Only admins can see this page.
      </p>

      <form onSubmit={handleCreate} className="acrylic" style={{ padding: 20, marginBottom: 24, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <label className="flex-col gap-8" style={{ display: 'flex' }}>
          <span className="text-secondary" style={{ fontSize: 12 }}>Username</span>
          <input value={form.username} onChange={(e) => setForm((f) => ({ ...f, username: e.target.value }))} required />
        </label>
        <label className="flex-col gap-8" style={{ display: 'flex' }}>
          <span className="text-secondary" style={{ fontSize: 12 }}>Full name</span>
          <input value={form.full_name} onChange={(e) => setForm((f) => ({ ...f, full_name: e.target.value }))} required />
        </label>
        <label className="flex-col gap-8" style={{ display: 'flex' }}>
          <span className="text-secondary" style={{ fontSize: 12 }}>Password</span>
          <input type="password" minLength={8} value={form.password} onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))} required />
        </label>
        <label className="flex-col gap-8" style={{ display: 'flex' }}>
          <span className="text-secondary" style={{ fontSize: 12 }}>Role</span>
          <select value={form.role} onChange={(e) => setForm((f) => ({ ...f, role: e.target.value }))}>
            {ROLES.map((r) => (
              <option key={r} value={r}>{r.replace('_', ' ')}</option>
            ))}
          </select>
        </label>
        {error && <div style={{ gridColumn: '1 / -1', color: 'var(--color-danger)', fontSize: 12.5 }}>{error}</div>}
        <button type="submit" className="btn btn-primary" disabled={creating} style={{ gridColumn: '1 / -1' }}>
          {creating ? 'Creating…' : '+ Create user'}
        </button>
      </form>

      <div className="acrylic" style={{ padding: 0, overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12.5 }}>
          <thead>
            <tr style={{ textAlign: 'left', borderBottom: '1px solid var(--color-acrylic-border)' }}>
              <th style={th}>Username</th>
              <th style={th}>Name</th>
              <th style={th}>Role</th>
              <th style={th}>Status</th>
              <th style={th}></th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.user_id} style={{ borderBottom: '1px solid rgba(255,255,255,0.03)' }}>
                <td style={td} className="mono">{u.username}</td>
                <td style={td}>{u.full_name}</td>
                <td style={td}>
                  <select value={u.role} onChange={(e) => changeRole(u, e.target.value)} style={{ fontSize: 12 }}>
                    {ROLES.map((r) => (
                      <option key={r} value={r}>{r.replace('_', ' ')}</option>
                    ))}
                  </select>
                </td>
                <td style={td}>
                  <span className={u.is_active ? 'badge badge-online' : 'badge badge-offline'}>
                    <span className="badge-dot" /> {u.is_active ? 'active' : 'deactivated'}
                  </span>
                </td>
                <td style={td}>
                  <button className="btn" style={{ padding: '5px 10px', fontSize: 11.5 }} onClick={() => toggleActive(u)}>
                    {u.is_active ? 'Deactivate' : 'Reactivate'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

const th = { padding: '10px 16px', fontWeight: 600, color: 'var(--color-text-secondary)' }
const td = { padding: '10px 16px' }
