import React from 'react'
import { ASSETS } from '@/config/assets'
import { FadingVideo } from '@/components/common/FadingVideo'
import { ShieldCheck, Database, Layers, ArrowUpRight } from 'lucide-react'
import { Link } from 'react-router-dom'

export const Capabilities: React.FC = () => {
  const capabilities = [
    {
      icon: <ShieldCheck className="w-6 h-6 text-copper-highlight" />,
      title: 'Deterministic Policy Engine',
      category: 'Rule Verification',
      description:
        'Eliminates AI hallucinations with deterministic rule execution. Flags forbidden claims, trademark infringements, and required regulatory disclosures at exact character spans with zero guesswork.',
      linkText: 'Policy Rules',
    },
    {
      icon: <Database className="w-6 h-6 text-chartreuse" />,
      title: 'Evidence-Backed Claim Proof',
      category: 'Fact Verification',
      description:
        'Every factual statistic and superiority claim is anchored to approved external evidence sources. Distinguishes supported facts from insufficient evidence and detects direct factual contradictions.',
      linkText: 'Evidence Registry',
    },
    {
      icon: <Layers className="w-6 h-6 text-copper" />,
      title: 'Auditable Review & Governance',
      category: 'Workflow Integrity',
      description:
        'Propose structured corrections that apply cleanly as new content revisions. Enforces strict separation of duties preventing self-approvals, backed by an immutable SHA-256 audit log.',
      linkText: 'Governance Workspace',
    },
  ]

  return (
    <section id="capabilities" className="relative w-full py-28 px-6 md:px-12 bg-charcoal text-ivory overflow-hidden">
      {/* Background Capabilities Video (Asset D) */}
      <div className="absolute inset-0 w-full h-full z-0 opacity-25 overflow-hidden">
        <FadingVideo
          src={ASSETS.CINEMATIC_CAPABILITIES_VIDEO}
          className="w-full h-full object-cover"
          fallbackBg="bg-charcoal"
        />
        <div className="absolute inset-0 bg-gradient-to-b from-charcoal via-transparent to-charcoal" />
      </div>

      <div className="relative z-10 max-w-7xl mx-auto space-y-16">
        {/* Section Header */}
        <div className="max-w-3xl space-y-4 text-left">
          <div className="inline-flex items-center space-x-2 text-xs font-semibold uppercase tracking-widest text-copper-highlight">
            <span className="w-1.5 h-1.5 rounded-full bg-copper-highlight" />
            <span>Three Pillars of Sentinel Governance</span>
          </div>
          <h2 className="font-serif text-3xl sm:text-4xl md:text-5xl text-paper-white tracking-tight">
            Governance with mathematical certainty.
          </h2>
          <p className="text-secondary-text text-base md:text-lg font-light leading-relaxed">
            Unlike probabilistic chatbots that invent answers, Inkloom Sentinel combines
            deterministic guideline rule execution with conservative evidence provenance.
          </p>
        </div>

        {/* 3 Restrained Capabilities Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {capabilities.map((cap, idx) => (
            <div
              key={cap.title}
              className="liquid-glass-strong p-8 rounded-3xl border border-white/10 hover:border-copper/40 transition-all duration-500 flex flex-col justify-between space-y-8 group"
            >
              <div className="space-y-6">
                <div className="w-12 h-12 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center group-hover:scale-110 transition-transform">
                  {cap.icon}
                </div>

                <div className="space-y-2">
                  <span className="text-[11px] font-semibold uppercase tracking-wider text-secondary-text">
                    {cap.category}
                  </span>
                  <h3 className="font-serif text-2xl text-paper-white group-hover:text-copper-highlight transition-colors">
                    {cap.title}
                  </h3>
                  <p className="text-sm text-ivory/70 font-light leading-relaxed pt-2">
                    {cap.description}
                  </p>
                </div>
              </div>

              <div className="pt-4 border-t border-white/10 flex items-center justify-between text-xs font-medium text-copper-highlight group-hover:text-white transition-colors">
                <span>{cap.linkText}</span>
                <ArrowUpRight className="w-4 h-4 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-transform" />
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
