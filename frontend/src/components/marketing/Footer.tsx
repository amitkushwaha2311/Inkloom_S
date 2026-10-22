import React from 'react'
import { Link } from 'react-router-dom'
import { ASSETS } from '@/config/assets'
import { Shield } from 'lucide-react'

export const Footer: React.FC = () => {
  return (
    <footer className="relative w-full bg-paper-white text-obsidian border-t border-border overflow-hidden pt-20 pb-12">
      {/* Meadow Video Ambient Backdrop fanned into warm paper background */}
      <div className="absolute inset-0 w-full h-full pointer-events-none opacity-20 overflow-hidden z-0">
        <video
          src={ASSETS.DRIFTBAR_FOOTER_MEADOW_VIDEO}
          poster={ASSETS.DRIFTBAR_FOOTER_POSTER}
          autoPlay
          muted
          loop
          playsInline
          preload="auto"
          className="w-full h-full object-cover object-[50%_100%] translate-y-[9%]"
        />
        {/* Paper-colored haze gradient above video */}
        <div className="absolute inset-0 bg-gradient-to-t from-paper-white via-paper-white/70 to-transparent" />
      </div>

      <div className="relative z-10 max-w-7xl mx-auto px-6 md:px-12 space-y-16">
        {/* Main Content Grid: 4 columns on wide screens */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-12 gap-12 text-left">
          {/* Brand Block (approx 440u) */}
          <div className="lg:col-span-5 space-y-6">
            <Link to="/" className="flex items-center space-x-3 cursor-pointer">
              <div className="w-8 h-8 rounded-lg bg-obsidian flex items-center justify-center text-ivory">
                <Shield className="w-4 h-4 text-copper-highlight" />
              </div>
              <span className="font-serif text-2xl tracking-tight font-bold text-obsidian">
                Inkloom Sentinel
              </span>
            </Link>
            <p className="text-secondary-text text-sm font-light leading-relaxed max-w-sm">
              Evidence-backed AI brand governance platform. Verifying content against versioned
              brand guidelines and regulatory policies with deterministic accuracy before publication.
            </p>
            <div className="text-xs text-secondary-text font-mono">
              Status: <span className="text-chartreuse font-semibold">All Systems Normal</span> · API v1.0
            </div>
          </div>

          {/* 3 Navigation Columns (Product, Resources, Governance) */}
          <div className="lg:col-span-7 grid grid-cols-2 sm:grid-cols-3 gap-8 text-sm">
            {/* Column 1: Platform */}
            <div className="space-y-4">
              <div className="text-xs font-semibold uppercase tracking-wider text-obsidian">
                Platform
              </div>
              <ul className="space-y-2.5 text-secondary-text text-xs">
                <li>
                  <a href="#capabilities" className="hover:text-copper transition-colors">
                    Deterministic Engine
                  </a>
                </li>
                <li>
                  <a href="#workflow" className="hover:text-copper transition-colors">
                    Claim Discovery
                  </a>
                </li>
                <li>
                  <a href="#evidence" className="hover:text-copper transition-colors">
                    Evidence Registry
                  </a>
                </li>
                <li>
                  <Link to="/app" className="hover:text-copper transition-colors">
                    Governance Console
                  </Link>
                </li>
              </ul>
            </div>

            {/* Column 2: Governance & Compliance */}
            <div className="space-y-4">
              <div className="text-xs font-semibold uppercase tracking-wider text-obsidian">
                Compliance
              </div>
              <ul className="space-y-2.5 text-secondary-text text-xs">
                <li>
                  <a href="#workflow" className="hover:text-copper transition-colors">
                    Separation of Duties
                  </a>
                </li>
                <li>
                  <a href="#workflow" className="hover:text-copper transition-colors">
                    Audit Provenance
                  </a>
                </li>
                <li>
                  <span className="text-secondary-text/70">RFC 6819 Token Security</span>
                </li>
                <li>
                  <span className="text-secondary-text/70">Multi-Tenant RBAC</span>
                </li>
              </ul>
            </div>

            {/* Column 3: Access */}
            <div className="space-y-4 col-span-2 sm:col-span-1">
              <div className="text-xs font-semibold uppercase tracking-wider text-obsidian">
                Access
              </div>
              <ul className="space-y-2.5 text-secondary-text text-xs">
                <li>
                  <Link to="/login" className="hover:text-copper transition-colors">
                    Sign In
                  </Link>
                </li>
                <li>
                  <Link to="/signup" className="hover:text-copper transition-colors">
                    Create Account
                  </Link>
                </li>
                <li>
                  <Link to="/app/settings" className="hover:text-copper transition-colors">
                    Workspace Settings
                  </Link>
                </li>
              </ul>
            </div>
          </div>
        </div>

        {/* Large Translucent Typographic Wordmark (Driftbar-inspired) */}
        <div className="pt-12 border-t border-border flex flex-col items-center justify-center space-y-4">
          <div className="w-full text-center select-none pointer-events-none">
            <span className="font-serif text-[12vw] sm:text-[10vw] md:text-[8vw] font-bold tracking-tight text-charcoal/10 uppercase leading-none block">
              INKLOOM
            </span>
          </div>

          <div className="w-full flex flex-col sm:flex-row items-center justify-between text-xs text-secondary-text pt-4">
            <p>© 2026 Inkloom Sentinel. Evidence-Backed Brand Governance.</p>
            <p className="mt-2 sm:mt-0 font-mono text-[11px]">
              Engine Integrity Hash: sha256:7e362c4d
            </p>
          </div>
        </div>
      </div>
    </footer>
  )
}
