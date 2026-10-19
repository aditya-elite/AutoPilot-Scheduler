import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'
import ForgotPasswordModal from '../components/ForgotPasswordModal.jsx'

export default function Login() {
  const { login, signup, googleAuth } = useAuth()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()

  const [isSignUp, setIsSignUp] = useState(false)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [role, setRole] = useState('factory_manager')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  // Forgot Password modal state
  const [showForgotModal, setShowForgotModal] = useState(false)

  // Google OAuth role prompt state for new user
  const [googlePrompt, setGooglePrompt] = useState(null) // { email, google_id, full_name, idToken }
  const [googleRole, setGoogleRole] = useState('factory_manager')

  // Align mode with query parameters
  useEffect(() => {
    const mode = searchParams.get('mode')
    setIsSignUp(mode === 'signup')
    setError('')
  }, [searchParams])

  // Load Google Identity Services script
  useEffect(() => {
    const script = document.createElement('script')
    script.src = 'https://accounts.google.com/gsi/client'
    script.async = true
    script.defer = true
    document.body.appendChild(script)
    return () => {
      document.body.removeChild(script)
    }
  }, [])

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      if (isSignUp) {
        await signup(username, password, fullName, role)
      } else {
        await login(username, password)
      }
      navigate('/')
    } catch (err) {
      setError(err.response?.data?.detail || 'Authentication failed. Check your input.')
    } finally {
      setLoading(false)
    }
  }

  async function handleGoogleSignIn(idToken = 'google_demo_account') {
    setError('')
    setLoading(true)
    try {
      const res = await googleAuth(idToken)
      if (res.is_new_user) {
        // Prompt role assignment for new Google user
        setGooglePrompt({
          idToken,
          email: res.email,
          google_id: res.google_id,
          full_name: res.full_name,
        })
      } else {
        navigate('/')
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Google sign-in failed. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  async function handleCompleteGoogleRegistration(e) {
    e.preventDefault()
    if (!googlePrompt) return
    setError('')
    setLoading(true)
    try {
      await googleAuth(googlePrompt.idToken, googleRole)
      setGooglePrompt(null)
      navigate('/')
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to complete registration.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      style={{
        position: 'relative',
        zIndex: 1,
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: '#f8f9fa',
      }}
    >
      <form
        onSubmit={handleSubmit}
        className="acrylic"
        style={{
          width: 400,
          padding: '36px 36px',
          display: 'flex',
          flexDirection: 'column',
          gap: 14,
          background: '#ffffff',
        }}
      >
        <div style={{ textAlign: 'center', marginBottom: 4 }}>
          <div 
            onClick={() => navigate('/')} 
            style={{ 
              fontFamily: 'var(--font-display)', 
              fontWeight: 700, 
              fontSize: 22, 
              color: '#1a73e8', 
              cursor: 'pointer',
              marginBottom: 4 
            }}
          >
            AutoPilot Scheduler
          </div>
          <p className="text-secondary" style={{ fontSize: 13.5, margin: 0 }}>
            {isSignUp ? 'Create your manager account' : 'Sign in to access your dashboard'}
          </p>
        </div>

        {/* Continue with Google Option */}
        <button
          type="button"
          onClick={() => handleGoogleSignIn('google_oauth_user_token_' + Date.now())}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 10,
            padding: '10px 16px',
            borderRadius: 8,
            border: '1px solid #dadce0',
            background: '#ffffff',
            color: '#3c4043',
            fontSize: 13.5,
            fontWeight: 600,
            cursor: 'pointer',
            boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
            transition: 'background 0.15s ease',
          }}
        >
          <svg width="18" height="18" viewBox="0 0 24 24">
            <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
            <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
            <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z" fill="#FBBC05"/>
            <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z" fill="#EA4335"/>
          </svg>
          Continue with Google
        </button>

        <div style={{ display: 'flex', alignItems: 'center', gap: 12, margin: '4px 0' }}>
          <div style={{ flex: 1, height: 1, background: '#dadce0' }} />
          <span style={{ fontSize: 12, color: '#70757a', fontWeight: 500 }}>or with username</span>
          <div style={{ flex: 1, height: 1, background: '#dadce0' }} />
        </div>

        {isSignUp && (
          <label className="flex-col gap-6" style={{ display: 'flex' }}>
            <span className="text-secondary" style={{ fontSize: 12.5, fontWeight: 500 }}>Full Name</span>
            <input 
              value={fullName} 
              onChange={(e) => setFullName(e.target.value)} 
              placeholder="Alex Mercer" 
              required 
              autoFocus 
            />
          </label>
        )}

        <label className="flex-col gap-6" style={{ display: 'flex' }}>
          <span className="text-secondary" style={{ fontSize: 12.5, fontWeight: 500 }}>Username or Email</span>
          <input 
            value={username} 
            onChange={(e) => setUsername(e.target.value)} 
            placeholder="manager" 
            required 
            autoFocus={!isSignUp} 
          />
        </label>

        <label className="flex-col gap-6" style={{ display: 'flex' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span className="text-secondary" style={{ fontSize: 12.5, fontWeight: 500 }}>Password</span>
            {!isSignUp && (
              <span
                onClick={() => setShowForgotModal(true)}
                style={{ fontSize: 12, color: '#1a73e8', cursor: 'pointer', fontWeight: 500 }}
              >
                Forgot Password?
              </span>
            )}
          </div>
          <input 
            type="password" 
            value={password} 
            onChange={(e) => setPassword(e.target.value)} 
            placeholder="••••••••" 
            required 
          />
        </label>

        {isSignUp && (
          <label className="flex-col gap-6" style={{ display: 'flex' }}>
            <span className="text-secondary" style={{ fontSize: 12.5, fontWeight: 500 }}>Role Assignment</span>
            <select value={role} onChange={(e) => setRole(e.target.value)} style={{ width: '100%' }}>
              <option value="factory_manager">Factory Manager (Full access)</option>
              <option value="machine_operator">Machine Operator (Operator queues)</option>
            </select>
          </label>
        )}

        {error && (
          <div style={{ color: 'var(--color-danger)', fontSize: 12.5, textAlign: 'center' }}>
            {error}
          </div>
        )}

        <button type="submit" className="btn btn-primary" disabled={loading} style={{ marginTop: 4, padding: '10px 16px', fontSize: 14 }}>
          {loading ? (isSignUp ? 'Registering…' : 'Signing in…') : (isSignUp ? 'Create Account' : 'Sign In')}
        </button>

        <div style={{ textAlign: 'center', marginTop: 6, fontSize: 13 }}>
          {isSignUp ? (
            <>
              Already have an account?{' '}
              <span 
                onClick={() => navigate('/login?mode=login')} 
                style={{ color: '#1a73e8', cursor: 'pointer', fontWeight: 600 }}
              >
                Sign In
              </span>
            </>
          ) : (
            <>
              New to AutoPilot?{' '}
              <span 
                onClick={() => navigate('/login?mode=signup')} 
                style={{ color: '#1a73e8', cursor: 'pointer', fontWeight: 600 }}
              >
                Create Account
              </span>
            </>
          )}
        </div>

        {!isSignUp && (
          <div className="text-tertiary" style={{ fontSize: 11.5, marginTop: 10, borderTop: '1px solid #dadce0', paddingTop: 10, lineHeight: 1.5 }}>
            <strong>Demo credentials:</strong><br />
            manager / manager123 (Factory Manager)<br />
            operator / operator123 (Machine Operator)
          </div>
        )}
      </form>

      {/* Role Assignment Modal for New Google Sign-In */}
      {googlePrompt && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(0,0,0,0.5)',
            backdropFilter: 'blur(4px)',
            zIndex: 9999,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <form
            onSubmit={handleCompleteGoogleRegistration}
            style={{
              width: 400,
              background: '#ffffff',
              borderRadius: 16,
              padding: '32px 28px',
              boxShadow: '0 12px 36px rgba(0,0,0,0.2)',
              display: 'flex',
              flexDirection: 'column',
              gap: 16,
            }}
          >
            <div style={{ textAlign: 'center' }}>
              <h3 style={{ margin: '0 0 6px 0', fontSize: 18, color: '#1a73e8', fontWeight: 700 }}>
                Role Assignment Required
              </h3>
              <p className="text-secondary" style={{ fontSize: 13, margin: 0 }}>
                Welcome, <strong>{googlePrompt.full_name}</strong>! Email verified ({googlePrompt.email}). Please select your workspace role to complete account creation.
              </p>
            </div>

            <label className="flex-col gap-6" style={{ display: 'flex' }}>
              <span className="text-secondary" style={{ fontSize: 12.5, fontWeight: 500 }}>Select System Role</span>
              <select value={googleRole} onChange={(e) => setGoogleRole(e.target.value)} style={{ width: '100%' }}>
                <option value="factory_manager">Factory Manager (Full access to scheduling & tools)</option>
                <option value="machine_operator">Machine Operator (Operator shift queue view)</option>
              </select>
            </label>

            <button type="submit" className="btn btn-primary" disabled={loading} style={{ padding: '10px 16px', fontSize: 14, marginTop: 8 }}>
              {loading ? 'Completing Sign-In…' : 'Confirm Role & Access Dashboard'}
            </button>
          </form>
        </div>
      )}

      {/* Forgot Password OTP Modal */}
      <ForgotPasswordModal
        isOpen={showForgotModal}
        onClose={() => setShowForgotModal(false)}
      />
    </div>
  )
}

