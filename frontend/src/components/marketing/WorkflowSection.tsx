import React, { useState } from 'react'
import { FileText, Cpu, Search, Sparkles, CheckCircle, ShieldAlert } from 'lucide-react'

export const WorkflowSection: React.FC = () => {
  const [activeStep, setActiveStep] = useState(0)

  const steps = [
    {
      num: '01',
      title: 'Policy Ingestion & Versioning',
      icon: <FileText className="w-5 h-5 text-copper-highlight" />,
      tag: 'Brand & Legal Foundations',
      description:
        'Legal, brand voice, and regulatory guidelines are registered into versioned brand policies. Every rule has an explicit severity, category, and deterministic matching specification.',
      detailCode: 'BrandPolicy.version: 3 -> status: ACTIVE -> 24 Guidelines Registered',
    },
    {
      num: '02',
      title: 'Content Submission & Claim Discovery',
      icon: <Search className="w-5 h-5 text-chartreuse" />,
      tag: 'Automated Extraction',
      description:
        'When marketing copy or product documentation is submitted, Sentinel automatically scans and indexes factual assertions, statistical metrics, and comparative claims with character coordinates.',
      detailCode: 'ContentRevision.char_offsets: [142, 198] -> Claim: "2.4x throughput"',
    },
    {
      num: '03',
      title: 'Deterministic & Semantic Verification',
      icon: <Cpu className="w-5 h-5 text-copper" />,
      tag: 'Zero-Hallucination Execution',
      description:
        'Deterministic regex and keyword engines execute against the text without generative deviation. Simultaneously, the semantic engine evaluates tone and superlative modesty.',
      detailCode: 'VerificationRun.findings: 1 Violation (Unsubstantiated Superlative)',
    },
    {
      num: '04',
      title: 'Authoritative Evidence Matching',
      icon: <CheckCircle className="w-5 h-5 text-chartreuse" />,
      tag: 'Conservative Proof',
      description:
        'Discovered claims are evaluated against approved Evidence Sources. A claim is only marked Supported when matched against approved filing citations; otherwise it flags for human review.',
      detailCode: 'ClaimAssessment.status: SUPPORTED -> Source: SEC_10K_FY25.pdf',
    },
    {
      num: '05',
      title: 'Non-Destructive Corrections',
      icon: <Sparkles className="w-5 h-5 text-copper-highlight" />,
      tag: 'Revision Integrity',
      description:
        'Reviewers propose structured text replacements with rationale. Accepting a suggestion generates a brand-new content revision rather than overwriting historical submissions.',
      detailCode: 'CorrectionApplied -> Generated Revision #5 (Previous #4 preserved)',
    },
    {
      num: '06',
      title: 'Separation of Duties & Audit Trail',
      icon: <ShieldAlert className="w-5 h-5 text-copper" />,
      tag: 'Governance Certification',
      description:
        'Authors cannot approve their own submissions. Once a designated reviewer approves, the entire decision lineage is cryptographically hashed into an append-only audit log.',
      detailCode: 'AuditEvent.USER_LOGGED -> actor_id: reviewer_4 -> status: APPROVED',
    },
  ]

  return (
    <section id="workflow" className="w-full py-28 px-6 md:px-12 bg-ivory text-obsidian">
      <div className="max-w-7xl mx-auto space-y-16">
        {/* Header */}
        <div className="max-w-2xl text-left space-y-4">
          <span className="text-xs font-semibold uppercase tracking-widest text-copper">
            Lifecycle Workflow
          </span>
          <h2 className="font-serif text-3xl sm:text-4xl md:text-5xl text-obsidian tracking-tight">
            How truth travels through Sentinel.
          </h2>
          <p className="text-secondary-text text-base md:text-lg font-light leading-relaxed">
            From raw draft to certified publication, every stage preserves complete provenance
            and requires affirmative verification.
          </p>
        </div>

        {/* Interactive Step Explorer */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          {/* Step list navigation */}
          <div className="lg:col-span-5 space-y-3">
            {steps.map((step, idx) => {
              const isActive = activeStep === idx
              return (
                <button
                  key={step.num}
                  onClick={() => setActiveStep(idx)}
                  className={`w-full p-5 rounded-2xl text-left transition-all duration-300 flex items-center justify-between border cursor-pointer ${
                    isActive
                      ? 'bg-paper-white border-copper/30 shadow-md ring-1 ring-copper/10'
                      : 'bg-transparent border-border hover:bg-paper-white/50'
                  }`}
                >
                  <div className="flex items-center space-x-4">
                    <span
                      className={`font-serif text-lg ${
                        isActive ? 'text-copper font-bold' : 'text-secondary-text'
                      }`}
                    >
                      {step.num}
                    </span>
                    <div>
                      <div className="text-xs uppercase tracking-wider text-secondary-text font-medium">
                        {step.tag}
                      </div>
                      <div
                        className={`text-sm md:text-base font-semibold ${
                          isActive ? 'text-obsidian' : 'text-charcoal'
                        }`}
                      >
                        {step.title}
                      </div>
                    </div>
                  </div>
                  <div
                    className={`p-2 rounded-xl transition-colors ${
                      isActive ? 'bg-copper/10' : 'bg-transparent'
                    }`}
                  >
                    {step.icon}
                  </div>
                </button>
              )
            })}
          </div>

          {/* Active Step Showcase Card */}
          <div className="lg:col-span-7">
            <div className="liquid-glass-paper p-8 md:p-12 rounded-3xl border border-charcoal/10 shadow-xl space-y-6 text-left">
              <div className="flex items-center justify-between border-b border-border pb-4">
                <div className="flex items-center space-x-3">
                  <div className="w-10 h-10 rounded-xl bg-copper/10 flex items-center justify-center text-copper">
                    {steps[activeStep].icon}
                  </div>
                  <div>
                    <span className="text-xs font-semibold uppercase tracking-wider text-copper">
                      Stage {steps[activeStep].num} of 06
                    </span>
                    <h3 className="text-xl md:text-2xl font-serif text-obsidian">
                      {steps[activeStep].title}
                    </h3>
                  </div>
                </div>
              </div>

              <p className="text-base md:text-lg text-charcoal/80 font-light leading-relaxed">
                {steps[activeStep].description}
              </p>

              {/* Provenance Terminal Box */}
              <div className="p-4 rounded-xl bg-obsidian text-ivory text-xs font-mono space-y-2 border border-border-dark">
                <div className="text-secondary-text text-[10px] uppercase tracking-wider">
                  Engine Telemetry & Provenance Log
                </div>
                <div className="text-chartreuse font-medium">
                  &gt; {steps[activeStep].detailCode}
                </div>
              </div>

              <div className="pt-4 border-t border-border flex items-center justify-between text-xs text-secondary-text">
                <span>Cryptographic state: VERIFIED</span>
                <span className="text-copper font-medium">Workspace-Scoped RBAC Active</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
