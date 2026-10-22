import React, { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import { Shield, ArrowRight, AlertCircle, Loader2 } from 'lucide-react'

export const SignupPage: React.FC = () => {
  const { register, error, clearError } = useAuth()
  const navigate = useNavigate()
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setFormError(null)
    clearError()

    if (!fullName.trim() || !email.trim() || !password) {
      setFormError('Please fill in all required fields.')
      return
    }

    if (password.length < 8) {
      setFormError('Password must be at least 8 characters with letters and numbers.')
      return
    }

    setSubmitting(true)
    try {
      await register({
        full_name: fullName.trim(),
        email: email.trim(),
        password,
      })
      navigate('/app')
    } catch (err: any) {
      setFormError(err.message || 'Registration failed. Email may already be in use.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen bg-obsidian text-ivory flex flex-col justify-between p-6 sm:p-12 relative overflow-hidden font-body">
      <div className="absolute inset-0 bg-gradient-to-br from-charcoal via-obsidian to-charcoal pointer-events-none" />

      {/* Top Navbar Header */}
      <div className="relative z-10 max-w-7xl w-full mx-auto flex items-center justify-between">
        <Link to="/" className="flex items-center space-x-2.5">
          <div className="w-8 h-8 rounded-lg bg-copper flex items-center justify-center text-white">
            <Shield className="w-4 h-4" />
          </div>
          <span className="font-serif text-xl tracking-tight text-paper-white">
            Inkloom Sentinel
          </span>
        </Link>
        <Link
          to="/login"
          className="text-xs uppercase tracking-wider text-secondary-text hover:text-white transition-colors"
        >
          Sign In Instead
        </Link>
      </div>

      {/* Center Auth Card */}
      <div className="relative z-10 max-w-md w-full mx-auto my-12">
        <div className="liquid-glass-strong p-8 sm:p-10 rounded-3xl border border-white/10 shadow-2xl space-y-6 text-left">
          <div className="space-y-2">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-copper-highlight">
              Enterprise Registration
            </span>
            <h1 className="font-serif text-3xl text-paper-white tracking-tight">
              Create Sentinel Account
            </h1>
            <p className="text-secondary-text text-xs leading-relaxed">
              Initialize your organization profile to start creating policies and verifying content.
            </p>
          </div>

          {(formError || error) && (
            <div className="p-3.5 rounded-xl bg-red-500/10 border border-red-500/20 text-red-300 text-xs flex items-start space-x-2.5">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5 text-red-400" />
              <span>{formError || error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-ivory/80 uppercase tracking-wider">
                Full Name
              </label>
              <input
                type="text"
                required
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Dr. Eleanor Vance"
                className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder-secondary-text text-sm focus:outline-none focus:ring-2 focus:ring-copper focus:border-transparent transition-all"
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-medium text-ivory/80 uppercase tracking-wider">
                Work Email
              </label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="eleanor@enterprise.com"
                className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder-secondary-text text-sm focus:outline-none focus:ring-2 focus:ring-copper focus:border-transparent transition-all"
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-medium text-ivory/80 uppercase tracking-wider">
                Password
              </label>
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="At least 8 chars with letter & digit"
                className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder-secondary-text text-sm focus:outline-none focus:ring-2 focus:ring-copper focus:border-transparent transition-all"
              />
            </div>

            <button
              type="submit"
              disabled={submitting}
              className="w-full py-3.5 rounded-xl bg-copper hover:bg-copper-highlight disabled:opacity-50 text-white font-semibold text-xs uppercase tracking-wider transition-all duration-300 flex items-center justify-center space-x-2 shadow-lg cursor-pointer mt-6"
            >
              {submitting ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Registering Account...</span>
                </>
              ) : (
                <>
                  <span>Create Account</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </form>

          <div className="pt-4 border-t border-white/10 text-center text-xs text-secondary-text">
            <span>Already have an account? </span>
            <Link to="/login" className="text-copper-highlight hover:underline font-medium">
              Sign in
            </Link>
          </div>
        </div>
      </div>

      <div className="relative z-10 text-center text-xs text-secondary-text">
        <span>Protected by RFC 6819 Token Security · Multi-Tenant Isolation</span>
      </div>
    </div>
  )
}
