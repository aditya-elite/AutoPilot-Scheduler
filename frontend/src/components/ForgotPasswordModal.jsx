import { useState, useEffect } from 'react'
import { useAuth } from '../context/AuthContext.jsx'

export default function ForgotPasswordModal({ isOpen, onClose }) {
  const { forgotPassword, verifyOTP, resetPasswordWithOTP } = useAuth()

  const [step, setStep] = useState(1) // 1: Email, 2: OTP, 3: New Password, 4: Done
  const [email, setEmail] = useState('')
  const [otpCode, setOtpCode] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')
  const [cooldown, setCooldown] = useState(0)

  useEffect(() => {
    let timer
    if (cooldown > 0) {
      timer = setInterval(() => {
        setCooldown((prev) => prev - 1)
      }, 1000)
    }
    return () => clearInterval(timer)
  }, [cooldown])

  if (!isOpen) return null

  function resetState() {
    setStep(1)
    setEmail('')
    setOtpCode('')
    setNewPassword('')
    setConfirmPassword('')
    setError('')
    setInfo('')
    setCooldown(0)
    onClose()
  }

  async function handleSendOTP(e) {
    if (e) e.preventDefault()
    if (!email) {
      setError('Please enter your registered email address.')
      return
    }

    setError('')
    setInfo('')
    setLoading(true)

    try {
      const res = await forgotPassword(email)
      setInfo(res.message || 'OTP code sent to your email!')
      setCooldown(60)
      setStep(2)
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to send OTP code. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  async function handleVerifyOTP(e) {
    e.preventDefault()
    if (otpCode.length !== 6) {
      setError('Please enter a valid 6-digit OTP code.')
      return
    }

    setError('')
    setLoading(true)

    try {
      await verifyOTP(email, otpCode)
      setStep(3)
      setError('')
      setInfo('OTP verified! Please set your new password.')
    } catch (err) {
      setError(err.response?.data?.detail || 'Invalid or expired OTP code.')
    } finally {
      setLoading(false)
    }
  }

  async function handleResetPassword(e) {
    e.preventDefault()
    setError('')

    if (newPassword.length < 8) {
      setError('Password must be at least 8 characters long.')
      return
    }

    if (newPassword !== confirmPassword) {
      setError('Passwords do not match.')
      return
    }

    setLoading(true)
    try {
      await resetPasswordWithOTP(email, otpCode, newPassword)
      setStep(4)
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to reset password.')
    } finally {
      setLoading(false)
    }
  }

  return (
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
      <div
        style={{
          width: 420,
          background: '#ffffff',
          borderRadius: 16,
          padding: '32px 28px',
          boxShadow: '0 12px 36px rgba(0,0,0,0.2)',
          display: 'flex',
          flexDirection: 'column',
          gap: 16,
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h3 style={{ margin: 0, fontSize: 18, fontWeight: 700, color: '#1a73e8' }}>
            {step === 1 && 'Reset Password'}
            {step === 2 && 'Enter 6-Digit OTP'}
            {step === 3 && 'Set New Password'}
            {step === 4 && 'Password Reset Complete'}
          </h3>
          <button
            onClick={resetState}
            style={{ background: 'none', border: 'none', fontSize: 18, cursor: 'pointer', color: '#5f6368' }}
          >
            ✕
          </button>
        </div>

        {error && (
          <div style={{ padding: '8px 12px', borderRadius: 8, background: '#fce8e6', color: '#c5221f', fontSize: 12.5 }}>
            {error}
          </div>
        )}

        {info && (
          <div style={{ padding: '8px 12px', borderRadius: 8, background: '#e8f0fe', color: '#1a73e8', fontSize: 12.5 }}>
            {info}
          </div>
        )}

        {step === 1 && (
          <form onSubmit={handleSendOTP} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <p className="text-secondary" style={{ fontSize: 13, margin: 0 }}>
              Enter your registered email address or username to receive a 6-digit OTP reset code.
            </p>
            <label className="flex-col gap-6" style={{ display: 'flex' }}>
              <span className="text-secondary" style={{ fontSize: 12.5, fontWeight: 500 }}>Email / Username</span>
              <input
                type="text"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="manager@example.com"
                required
                autoFocus
              />
            </label>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={loading || cooldown > 0}
              style={{ padding: '10px 16px', fontSize: 14, marginTop: 4 }}
            >
              {loading ? 'Sending OTP…' : cooldown > 0 ? `Wait ${cooldown}s` : 'Send OTP Code'}
            </button>
          </form>
        )}

        {step === 2 && (
          <form onSubmit={handleVerifyOTP} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <p className="text-secondary" style={{ fontSize: 13, margin: 0 }}>
              We sent a 6-digit OTP code to <strong>{email}</strong>. Code expires in 10 minutes.
            </p>
            <label className="flex-col gap-6" style={{ display: 'flex' }}>
              <span className="text-secondary" style={{ fontSize: 12.5, fontWeight: 500 }}>6-Digit OTP</span>
              <input
                type="text"
                maxLength={6}
                value={otpCode}
                onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, ''))}
                placeholder="123456"
                required
                style={{ textAlign: 'center', letterSpacing: 8, fontSize: 18, fontWeight: 700 }}
                autoFocus
              />
            </label>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <button
                type="button"
                onClick={handleSendOTP}
                disabled={cooldown > 0 || loading}
                style={{ background: 'none', border: 'none', color: cooldown > 0 ? '#9aa0a6' : '#1a73e8', fontSize: 12.5, cursor: cooldown > 0 ? 'not-allowed' : 'pointer' }}
              >
                {cooldown > 0 ? `Resend code in ${cooldown}s` : 'Resend OTP'}
              </button>
              <button type="submit" className="btn btn-primary" disabled={loading} style={{ padding: '8px 16px', fontSize: 13.5 }}>
                {loading ? 'Verifying…' : 'Verify Code'}
              </button>
            </div>
          </form>
        )}

        {step === 3 && (
          <form onSubmit={handleResetPassword} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <p className="text-secondary" style={{ fontSize: 13, margin: 0 }}>
              Create a new password for your account.
            </p>
            <label className="flex-col gap-6" style={{ display: 'flex' }}>
              <span className="text-secondary" style={{ fontSize: 12.5, fontWeight: 500 }}>New Password</span>
              <input
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="At least 8 characters"
                required
                minLength={8}
                autoFocus
              />
            </label>
            <label className="flex-col gap-6" style={{ display: 'flex' }}>
              <span className="text-secondary" style={{ fontSize: 12.5, fontWeight: 500 }}>Confirm New Password</span>
              <input
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="Re-enter new password"
                required
                minLength={8}
              />
            </label>
            <button type="submit" className="btn btn-primary" disabled={loading} style={{ padding: '10px 16px', fontSize: 14, marginTop: 4 }}>
              {loading ? 'Resetting Password…' : 'Reset Password'}
            </button>
          </form>
        )}

        {step === 4 && (
          <div style={{ textAlign: 'center', display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div style={{ fontSize: 36, color: '#34a853' }}>✓</div>
            <p style={{ fontSize: 14, color: '#202124', margin: 0 }}>
              Your password has been successfully reset! You can now sign in with your new password.
            </p>
            <button onClick={resetState} className="btn btn-primary" style={{ padding: '10px 16px', fontSize: 14, marginTop: 8 }}>
              Back to Sign In
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
