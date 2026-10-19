import { createContext, useContext, useState } from 'react'
import client from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    const stored = localStorage.getItem('autopilot_user')
    return stored ? JSON.parse(stored) : null
  })

  async function login(username, password) {
    const form = new URLSearchParams()
    form.append('username', username)
    form.append('password', password)
    const res = await client.post('/auth/login', form, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    })
    const { access_token, role, full_name } = res.data
    localStorage.setItem('autopilot_token', access_token)
    const userObj = { role, full_name, username }
    localStorage.setItem('autopilot_user', JSON.stringify(userObj))
    setUser(userObj)
    return userObj
  }

  async function signup(username, password, fullName, role) {
    const res = await client.post('/auth/signup', {
      username,
      password,
      full_name: fullName,
      role,
    })
    const { access_token, role: userRole, full_name } = res.data
    localStorage.setItem('autopilot_token', access_token)
    const userObj = { role: userRole, full_name, username }
    localStorage.setItem('autopilot_user', JSON.stringify(userObj))
    setUser(userObj)
    return userObj
  }

  async function googleAuth(idToken, role = null) {
    const res = await client.post('/auth/google', {
      id_token: idToken,
      role: role,
    })

    if (res.data.is_new_user) {
      return { is_new_user: true, email: res.data.email, google_id: res.data.google_id, full_name: res.data.full_name }
    }

    const { access_token, role: userRole, full_name, email, google_id } = res.data
    localStorage.setItem('autopilot_token', access_token)
    const userObj = { role: userRole, full_name, email, google_id, username: email || full_name }
    localStorage.setItem('autopilot_user', JSON.stringify(userObj))
    setUser(userObj)
    return { is_new_user: false, user: userObj }
  }

  async function changePassword(currentPassword, newPassword) {
    const res = await client.post('/auth/change-password', {
      current_password: currentPassword,
      new_password: newPassword,
    })
    return res.data
  }

  async function forgotPassword(email) {
    const res = await client.post('/auth/forgot-password', { email })
    return res.data
  }

  async function verifyOTP(email, otpCode) {
    const res = await client.post('/auth/verify-otp', {
      email,
      otp_code: otpCode,
    })
    return res.data
  }

  async function resetPasswordWithOTP(email, otpCode, newPassword) {
    const res = await client.post('/auth/reset-password', {
      email,
      otp_code: otpCode,
      new_password: newPassword,
    })
    return res.data
  }

  function logout() {
    localStorage.removeItem('autopilot_token')
    localStorage.removeItem('autopilot_user')
    setUser(null)
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        login,
        signup,
        googleAuth,
        changePassword,
        forgotPassword,
        verifyOTP,
        resetPasswordWithOTP,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}

