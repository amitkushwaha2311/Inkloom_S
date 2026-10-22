import React from 'react'
import { Link } from 'react-router-dom'
import { ASSETS, CORNER_MASKS } from '@/config/assets'
import { FadingVideo } from '@/components/common/FadingVideo'
import { BlurText } from '@/components/common/BlurText'
import { ShieldCheck, FileCheck, ArrowRight, CheckCircle2, Lock } from 'lucide-react'

export const Hero: React.FC = () => {
  return (
    <section className="relative w-full min-h-[100svh] md:min-h-[700px] flex items-center justify-center overflow-hidden bg-obsidian text-ivory pt-24 pb-16 px-6 md:px-12">
      {/* Background Video with manual loop crossfading */}
      <div className="absolute inset-0 w-full h-full z-0 overflow-hidden">
        <FadingVideo
          src={ASSETS.PALOMAR_HERO_VIDEO}
          className="w-full h-full object-cover object-bottom"
          fallbackBg="bg-gradient-to-b from-obsidian via-charcoal to-obsidian"
        />
        {/* Subtle warm vignette without heavy blue overlay */}
        <div className="absolute inset-0 bg-gradient-to-t from-obsidian via-obsidian/40 to-transparent pointer-events-none" />
        <div className="absolute inset-0 bg-gradient-to-r from-obsidian/70 via-transparent to-obsidian/40 pointer-events-none" />
      </div>

      <div className="relative z-10 max-w-7xl w-full mx-auto grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
        {/* Left Editorial Copy */}
        <div className="lg:col-span-7 flex flex-col items-start text-left space-y-6">
          {/* Announcement Pill */}
          <div className="liquid-glass inline-flex items-center space-x-2.5 px-4 py-1.5 rounded-full border border-white/10 text-xs font-medium text-ivory/90 tracking-wide animate-fade-down">
            <span className="w-2 h-2 rounded-full bg-chartreuse animate-pulse" />
            <span className="text-ivory/80">Inkloom Sentinel</span>
            <span className="text-secondary-text">·</span>
            <span className="text-copper-highlight font-semibold">Continuous Brand Governance</span>
          </div>

          {/* Headline using BlurText */}
          <BlurText
            text="Brand integrity, verified against truth."
            className="font-serif text-4xl sm:text-5xl md:text-6xl lg:text-7xl leading-[1.08] tracking-tight text-paper-white"
          />

          <p className="text-base sm:text-lg md:text-xl text-ivory/70 max-w-2xl font-light leading-relaxed animate-fade-up stagger-2">
            Every claim, guideline, and correction connected to authoritative evidence.
            Deterministic compliance engines and conservative claim verification protect your
            reputation before publication.
          </p>

          {/* Action CTAs */}
          <div className="flex flex-wrap items-center gap-4 pt-2 animate-fade-up stagger-3">
            <Link
              to="/signup"
              className="px-8 py-4 rounded-full bg-copper hover:bg-copper-highlight text-white text-sm font-semibold tracking-wider uppercase transition-all duration-300 shadow-xl hover:shadow-copper/20 flex items-center space-x-3 group"
            >
              <span>Explore Workspace</span>
              <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
            </Link>

            <a
              href="#workflow"
              className="liquid-glass hover:bg-white/10 px-6 py-4 rounded-full border border-white/20 text-ivory text-sm font-medium tracking-wide transition-all duration-300 flex items-center space-x-2"
            >
              <span>View Audit Provenance</span>
            </a>
          </div>

          {/* Trust and Key Capabilities row */}
          <div className="pt-8 border-t border-white/10 grid grid-cols-3 gap-6 w-full max-w-xl text-left animate-fade-up stagger-4">
            <div>
              <div className="text-2xl font-serif text-paper-white">100%</div>
              <div className="text-xs text-secondary-text uppercase tracking-wider font-medium mt-1">
                Deterministic
              </div>
            </div>
            <div>
              <div className="text-2xl font-serif text-paper-white">RFC 6819</div>
              <div className="text-xs text-secondary-text uppercase tracking-wider font-medium mt-1">
                Zero Replay Auth
              </div>
            </div>
            <div>
              <div className="text-2xl font-serif text-paper-white">Append-Only</div>
              <div className="text-xs text-secondary-text uppercase tracking-wider font-medium mt-1">
                Audit Trail
              </div>
            </div>
          </div>
        </div>

        {/* Right Floating Glass Card (RIVR-inspired with corner cutout) */}
        <div className="lg:col-span-5 relative w-full flex justify-center lg:justify-end animate-fade-up stagger-3">
          <div className="liquid-glass-strong w-full max-w-md p-6 rounded-3xl border border-white/15 text-left space-y-5 shadow-2xl relative">
            <div className="flex items-center justify-between pb-4 border-b border-white/10">
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 rounded-xl bg-copper/20 border border-copper/40 flex items-center justify-center text-copper-highlight">
                  <ShieldCheck className="w-5 h-5" />
                </div>
                <div>
                  <h2 className="text-sm font-semibold text-paper-white">Policy Verification Run</h2>
                  <p className="text-xs text-secondary-text">Submission Rev #4 · Active Policy v2</p>
                </div>
              </div>
              <span className="px-2.5 py-1 rounded-full text-[10px] font-semibold uppercase tracking-wider bg-chartreuse/20 text-chartreuse border border-chartreuse/30">
                Verified Pass
              </span>
            </div>

            {/* Findings preview */}
            <div className="space-y-3">
              <div className="p-3.5 rounded-xl bg-white/5 border border-white/10 flex items-start space-x-3">
                <CheckCircle2 className="w-4 h-4 text-chartreuse mt-0.5 shrink-0" />
                <div className="text-xs">
                  <div className="font-medium text-paper-white">Claim Provenance Linked</div>
                  <div className="text-secondary-text mt-0.5">
                    "2.4x improvement" supported by SEC 10-K filing #REF-2026-Q3
                  </div>
                </div>
              </div>

              <div className="p-3.5 rounded-xl bg-white/5 border border-white/10 flex items-start space-x-3">
                <FileCheck className="w-4 h-4 text-copper-highlight mt-0.5 shrink-0" />
                <div className="text-xs">
                  <div className="font-medium text-paper-white">Separation of Duties Enforced</div>
                  <div className="text-secondary-text mt-0.5">
                    Reviewer distinct from content author. Approved by Compliance Lead.
                  </div>
                </div>
              </div>

              <div className="p-3.5 rounded-xl bg-white/5 border border-white/10 flex items-start space-x-3">
                <Lock className="w-4 h-4 text-secondary-text mt-0.5 shrink-0" />
                <div className="text-xs">
                  <div className="font-medium text-paper-white">Immutable Hash Sealed</div>
                  <div className="text-secondary-text font-mono text-[10px] mt-0.5">
                    sha256:8f4c1e...92b4
                  </div>
                </div>
              </div>
            </div>

            {/* Floating pill badge */}
            <div className="pt-2 flex items-center justify-between text-[11px] text-secondary-text">
              <span>Tenant Isolation: Active</span>
              <span className="text-copper-highlight font-medium">Deterministic Engine v1.0</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
