import React, { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import { Shield, ArrowRight, AlertCircle, Loader2 } from 'lucide-react'

export const LoginPage: React.FC = () => {
  const { login, error, clearError } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setFormError(null)
    clearError()

    if (!email.trim() || !password) {
      setFormError('Please enter both email and password.')
      return
    }

    setSubmitting(true)
    try {
      await login({ email: email.trim(), password })
      navigate('/app')
    } catch (err: any) {
      setFormError(err.message || 'Invalid email or password.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen bg-obsidian text-ivory flex flex-col justify-between p-6 sm:p-12 relative overflow-hidden font-body">
      {/* Background ambient gradient */}
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
          to="/"
          className="text-xs uppercase tracking-wider text-secondary-text hover:text-white transition-colors"
        >
          Return to Overview
        </Link>
      </div>

      {/* Center Auth Card */}
      <div className="relative z-10 max-w-md w-full mx-auto my-12">
        <div className="liquid-glass-strong p-8 sm:p-10 rounded-3xl border border-white/10 shadow-2xl space-y-6 text-left">
          <div className="space-y-2">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-copper-highlight">
              Secure Access
            </span>
            <h1 className="font-serif text-3xl text-paper-white tracking-tight">
              Sign in to Sentinel
            </h1>
            <p className="text-secondary-text text-xs leading-relaxed">
              Enter your credentials to access verified workspace policies and audit trails.
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
                Work Email
              </label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="alice@example.com"
                className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder-secondary-text text-sm focus:outline-none focus:ring-2 focus:ring-copper focus:border-transparent transition-all"
              />
            </div>

            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <label className="text-xs font-medium text-ivory/80 uppercase tracking-wider">
                  Password
                </label>
              </div>
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••"
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
                  <span>Verifying Credentials...</span>
                </>
              ) : (
                <>
                  <span>Sign In</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </form>

          <div className="pt-4 border-t border-white/10 text-center text-xs text-secondary-text">
            <span>Don't have an enterprise account? </span>
            <Link to="/signup" className="text-copper-highlight hover:underline font-medium">
              Create an account
            </Link>
          </div>
        </div>
      </div>

      {/* Footer Note */}
      <div className="relative z-10 text-center text-xs text-secondary-text">
        <span>Protected by RFC 6819 Token Security · Multi-Tenant Isolation</span>
      </div>
    </div>
  )
}
