import React, { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import { Shield, Menu, X, ArrowRight } from 'lucide-react'

export const Navbar: React.FC = () => {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [scrolled, setScrolled] = useState(false)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 20)
    }
    window.addEventListener('scroll', handleScroll, { passive: true })
    return () => window.removeEventListener('scroll', handleScroll)
  }, [])

  // Lock mobile body scrolling when menu is open
  useEffect(() => {
    if (mobileMenuOpen) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }
    return () => {
      document.body.style.overflow = ''
    }
  }, [mobileMenuOpen])

  const navLinks = [
    { label: 'Capabilities', href: '#capabilities' },
    { label: 'Workflow', href: '#workflow' },
    { label: 'Evidence Engine', href: '#evidence' },
    { label: 'Governance', href: '#governance' },
  ]

  const handleNavClick = (href: string) => {
    setMobileMenuOpen(false)
    const el = document.querySelector(href)
    if (el) {
      el.scrollIntoView({ behavior: 'smooth' })
    }
  }

  return (
    <>
      <header
        className={`fixed top-0 left-0 right-0 z-50 transition-all duration-500 ${
          scrolled
            ? 'h-16 md:h-20 bg-obsidian/80 backdrop-blur-md border-b border-border-dark text-ivory shadow-lg'
            : 'h-16 md:h-20 bg-transparent text-ivory'
        }`}
      >
        <div className="max-w-7xl mx-auto h-full px-6 md:px-8 flex items-center justify-between">
          {/* Left Navigation */}
          <nav className="hidden md:flex items-center space-x-8 text-sm font-medium tracking-wide text-ivory/80">
            {navLinks.slice(0, 2).map((link) => (
              <button
                key={link.label}
                onClick={() => handleNavClick(link.href)}
                className="hover:text-copper-highlight transition-colors cursor-pointer text-left"
              >
                {link.label}
              </button>
            ))}
          </nav>

          {/* Centered Brand Mark */}
          <Link
            to="/"
            className="flex items-center space-x-2.5 group cursor-pointer"
            aria-label="Inkloom Sentinel Home"
          >
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-copper to-charcoal border border-copper-highlight/30 flex items-center justify-center text-ivory shadow-sm group-hover:scale-105 transition-transform">
              <Shield className="w-4 h-4 text-copper-highlight" />
            </div>
            <div className="flex flex-col text-left">
              <span className="font-serif text-xl tracking-tight leading-none text-ivory">
                Inkloom
              </span>
              <span className="text-[10px] uppercase tracking-widest text-secondary-text font-medium">
                Sentinel
              </span>
            </div>
          </Link>

          {/* Right Navigation & CTAs */}
          <div className="hidden md:flex items-center space-x-8 text-sm font-medium tracking-wide">
            {navLinks.slice(2).map((link) => (
              <button
                key={link.label}
                onClick={() => handleNavClick(link.href)}
                className="text-ivory/80 hover:text-copper-highlight transition-colors cursor-pointer text-left"
              >
                {link.label}
              </button>
            ))}

            {user ? (
              <button
                onClick={() => navigate('/app')}
                className="liquid-glass hover:bg-white/10 text-ivory px-5 py-2 rounded-full text-xs font-semibold tracking-wider uppercase transition-all duration-300 flex items-center space-x-2 cursor-pointer border border-white/20"
              >
                <span>Console</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            ) : (
              <div className="flex items-center space-x-4">
                <Link
                  to="/login"
                  className="text-ivory/90 hover:text-white transition-colors text-xs font-semibold uppercase tracking-wider"
                >
                  Sign in
                </Link>
                <Link
                  to="/signup"
                  className="liquid-glass hover:bg-copper/90 bg-copper text-white px-5 py-2 rounded-full text-xs font-semibold tracking-wider uppercase transition-all duration-300 shadow-md flex items-center space-x-2"
                >
                  <span>Get Started</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </Link>
              </div>
            )}
          </div>

          {/* Mobile Hamburger Toggle */}
          <div className="flex md:hidden items-center">
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="p-2 text-ivory/90 hover:text-white focus:outline-none focus:ring-2 focus:ring-copper"
              aria-expanded={mobileMenuOpen}
              aria-controls="mobile-navigation"
              aria-label="Toggle navigation menu"
            >
              {mobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
            </button>
          </div>
        </div>
      </header>

      {/* Full-screen Mobile Overlay */}
      {mobileMenuOpen && (
        <div
          id="mobile-navigation"
          className="fixed inset-0 z-40 bg-ivory text-obsidian flex flex-col justify-between p-8 pt-28 md:hidden animate-fade-down"
        >
          <div className="flex flex-col space-y-6 text-center">
            {navLinks.map((link) => (
              <button
                key={link.label}
                onClick={() => handleNavClick(link.href)}
                className="font-serif text-3xl hover:text-copper transition-colors cursor-pointer"
              >
                {link.label}
              </button>
            ))}
          </div>

          <div className="flex flex-col space-y-4 pt-8 border-t border-border">
            {user ? (
              <button
                onClick={() => {
                  setMobileMenuOpen(false)
                  navigate('/app')
                }}
                className="w-full py-4 rounded-full bg-copper text-white font-semibold text-sm uppercase tracking-wider flex items-center justify-center space-x-2"
              >
                <span>Open Governance Console</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            ) : (
              <>
                <Link
                  to="/signup"
                  onClick={() => setMobileMenuOpen(false)}
                  className="w-full py-4 rounded-full bg-copper text-white font-semibold text-sm uppercase tracking-wider text-center"
                >
                  Create Account
                </Link>
                <Link
                  to="/login"
                  onClick={() => setMobileMenuOpen(false)}
                  className="w-full py-4 rounded-full border border-charcoal/20 text-charcoal font-semibold text-sm uppercase tracking-wider text-center"
                >
                  Sign In
                </Link>
              </>
            )}
          </div>
        </div>
      )}
    </>
  )
}
