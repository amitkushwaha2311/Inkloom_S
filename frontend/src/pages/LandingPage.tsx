import React from 'react'
import { Link } from 'react-router-dom'
import { Navbar } from '@/components/marketing/Navbar'
import { Hero } from '@/components/marketing/Hero'
import { Capabilities } from '@/components/marketing/Capabilities'
import { WorkflowSection } from '@/components/marketing/WorkflowSection'
import { EvidenceSection } from '@/components/marketing/EvidenceSection'
import { Footer } from '@/components/marketing/Footer'
import { ArrowRight, ShieldCheck } from 'lucide-react'

export const LandingPage: React.FC = () => {
  return (
    <div className="min-h-screen bg-obsidian text-ivory flex flex-col font-body selection:bg-copper selection:text-white">
      {/* Editorial Fixed Navbar */}
      <Navbar />

      {/* Main Sections */}
      <main className="flex-1">
        <Hero />
        <Capabilities />
        <WorkflowSection />
        <EvidenceSection />

        {/* Final Restrained CTA Section */}
        <section id="governance" className="relative py-28 px-6 md:px-12 bg-charcoal text-ivory text-center border-t border-border-dark overflow-hidden">
          <div className="max-w-4xl mx-auto space-y-8 relative z-10">
            <div className="w-12 h-12 rounded-2xl bg-copper/20 border border-copper/40 flex items-center justify-center text-copper-highlight mx-auto shadow-md">
              <ShieldCheck className="w-6 h-6" />
            </div>

            <h2 className="font-serif text-3xl sm:text-4xl md:text-5xl text-paper-white tracking-tight">
              Ready to automate evidence-backed brand compliance?
            </h2>

            <p className="text-secondary-text text-base sm:text-lg max-w-xl mx-auto font-light leading-relaxed">
              Join enterprise governance teams who deploy Inkloom Sentinel to protect their
              reputation, satisfy regulators, and maintain uncompromising brand integrity.
            </p>

            <div className="flex flex-wrap items-center justify-center gap-4 pt-4">
              <Link
                to="/signup"
                className="px-8 py-4 rounded-full bg-copper hover:bg-copper-highlight text-white text-sm font-semibold tracking-wider uppercase transition-all duration-300 shadow-xl flex items-center space-x-2"
              >
                <span>Launch Sentinel Console</span>
                <ArrowRight className="w-4 h-4" />
              </Link>
              <Link
                to="/login"
                className="liquid-glass hover:bg-white/10 px-8 py-4 rounded-full text-ivory text-sm font-semibold tracking-wider uppercase transition-all duration-300 border border-white/20"
              >
                <span>Existing Member Sign In</span>
              </Link>
            </div>
          </div>
        </section>
      </main>

      {/* Driftbar-inspired Footer */}
      <Footer />
    </div>
  )
}
