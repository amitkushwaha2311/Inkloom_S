import React from 'react'
import { Check, X, AlertTriangle, Shield, ExternalLink } from 'lucide-react'

export const EvidenceSection: React.FC = () => {
  return (
    <section id="evidence" className="w-full py-28 px-6 md:px-12 bg-obsidian text-ivory">
      <div className="max-w-7xl mx-auto space-y-16">
        {/* Header */}
        <div className="max-w-3xl text-left space-y-4">
          <span className="text-xs font-semibold uppercase tracking-widest text-chartreuse">
            Ground Truth Verification
          </span>
          <h2 className="font-serif text-3xl sm:text-4xl md:text-5xl text-paper-white tracking-tight">
            No claim stands without proof.
          </h2>
          <p className="text-secondary-text text-base md:text-lg font-light leading-relaxed">
            Marketing copy often makes unverified claims like "industry-leading" or "99.9% uptime".
            Sentinel checks every assertion against an authorized, SSRF-guarded registry of
            evidence sources.
          </p>
        </div>

        {/* Comparison grid: Unverified Claim vs Verified Evidence */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 text-left">
          {/* Card A: Unverified / Contradicted Claim */}
          <div className="liquid-glass p-8 rounded-3xl border border-red-500/20 bg-charcoal/50 space-y-6">
            <div className="flex items-center justify-between">
              <span className="px-3 py-1 rounded-full text-xs font-semibold uppercase tracking-wider bg-red-500/10 text-red-400 border border-red-500/20 flex items-center space-x-1.5">
                <AlertTriangle className="w-3.5 h-3.5" />
                <span>Flagged Claim</span>
              </span>
              <span className="text-xs text-secondary-text">Submission #SUB-091 · Rev 2</span>
            </div>

            <div className="space-y-2">
              <h3 className="text-sm font-semibold text-paper-white uppercase tracking-wider">
                Unsubstantiated Copy Excerpt:
              </h3>
              <p className="p-4 rounded-xl bg-black/40 text-red-200/90 text-sm italic font-serif leading-relaxed border-l-2 border-red-400">
                "Our revolutionary platform cuts compliance review costs by over 90% guaranteed
                for any enterprise size."
              </p>
            </div>

            <div className="space-y-3 pt-2 text-xs">
              <div className="flex items-start space-x-2 text-red-300">
                <X className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
                <span>
                  <strong>Contradiction Detected:</strong> SEC filings cite maximum historical cost
                  reduction at 44%, not 90%.
                </span>
              </div>
              <div className="flex items-start space-x-2 text-secondary-text">
                <X className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
                <span>
                  <strong>Forbidden Wordmark:</strong> "Guaranteed" explicitly prohibited under Rule
                  REG-301.
                </span>
              </div>
            </div>
          </div>

          {/* Card B: Supported with Provenance Citation */}
          <div className="liquid-glass p-8 rounded-3xl border border-chartreuse/30 bg-charcoal/50 space-y-6">
            <div className="flex items-center justify-between">
              <span className="px-3 py-1 rounded-full text-xs font-semibold uppercase tracking-wider bg-chartreuse/10 text-chartreuse border border-chartreuse/30 flex items-center space-x-1.5">
                <Check className="w-3.5 h-3.5" />
                <span>Evidence Supported</span>
              </span>
              <span className="text-xs text-secondary-text">Submission #SUB-091 · Rev 3 (Corrected)</span>
            </div>

            <div className="space-y-2">
              <h3 className="text-sm font-semibold text-paper-white uppercase tracking-wider">
                Verified Copy Excerpt:
              </h3>
              <p className="p-4 rounded-xl bg-black/40 text-chartreuse/90 text-sm italic font-serif leading-relaxed border-l-2 border-chartreuse">
                "Our platform delivers up to 44% compliance review efficiency according to our
                audited FY2025 customer operational benchmark study."
              </p>
            </div>

            <div className="space-y-3 pt-2 text-xs">
              <div className="flex items-start space-x-2 text-chartreuse">
                <Check className="w-4 h-4 text-chartreuse shrink-0 mt-0.5" />
                <span>
                  <strong>Authoritative Citation Linked:</strong> Benchmark Report #BMK-2025-08
                  (Status: APPROVED).
                </span>
              </div>
              <div className="flex items-start space-x-2 text-secondary-text">
                <Shield className="w-4 h-4 text-copper-highlight shrink-0 mt-0.5" />
                <span>
                  <strong>Confidence Score:</strong> 0.98 · Evidence verified by Compliance Officer.
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
