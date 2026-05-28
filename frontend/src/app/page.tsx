'use client'
import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Activity, Cpu, Database, Shield, Zap, ChevronRight, Brain } from 'lucide-react'
import dynamic from 'next/dynamic'
import FileUpload from '@/components/FileUpload'
import ResultsDashboard from '@/components/ResultsDashboard'
import { CodingResult } from '@/lib/api'

// Dynamic import for canvas (SSR-safe)
const ParticleBackground = dynamic(() => import('@/components/ParticleBackground'), { ssr: false })

const FEATURES = [
  { icon: Brain, label: 'NLP Extraction', desc: 'Section-aware clinical entity extraction', color: '#b347ff' },
  { icon: Activity, label: 'CPT + ICD + HCPCS', desc: 'Multi-code type generation with MDM scoring', color: '#00d4ff' },
  { icon: Database, label: 'SNOMED Mapping', desc: 'Automated clinical concept normalization', color: '#00ff88' },
  { icon: Shield, label: 'NCCI / MUE Validation', desc: 'PTP edits and unit limit enforcement', color: '#ff8c00' },
]

const CODE_TYPES = [
  { label: 'CPT', color: '#00d4ff', desc: '11,574 codes indexed' },
  { label: 'ICD-10-CM', color: '#00ff88', desc: '74,719 codes indexed' },
  { label: 'HCPCS', color: '#ffcc00', desc: '9,748 codes indexed' },
  { label: 'SNOMED', color: '#ff00aa', desc: 'Curated podiatry mapping' },
  { label: 'NCCI', color: '#ff8c00', desc: '6,773 PTP edit pairs' },
]

export default function Home() {
  const [result, setResult] = useState<CodingResult | null>(null)
  const [loading, setLoading] = useState(false)

  const reset = () => setResult(null)

  return (
    <div className="relative min-h-screen bg-grid bg-[size:50px_50px]" style={{ background: '#020409' }}>
      <ParticleBackground />

      {/* Radial glow blobs */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden" style={{ zIndex: 1 }}>
        <div className="absolute top-0 left-1/4 w-96 h-96 rounded-full opacity-8"
          style={{ background: 'radial-gradient(circle, rgba(0,212,255,0.15) 0%, transparent 70%)', filter: 'blur(40px)' }} />
        <div className="absolute bottom-1/4 right-1/4 w-80 h-80 rounded-full opacity-8"
          style={{ background: 'radial-gradient(circle, rgba(179,71,255,0.15) 0%, transparent 70%)', filter: 'blur(40px)' }} />
        <div className="absolute top-1/2 left-0 w-64 h-64 rounded-full opacity-6"
          style={{ background: 'radial-gradient(circle, rgba(0,255,136,0.1) 0%, transparent 70%)', filter: 'blur(40px)' }} />
      </div>

      <div className="relative" style={{ zIndex: 2 }}>
        {/* ── Header ─────────────────────────────────────────────── */}
        <header className="border-b border-slate-800/60 backdrop-blur-md sticky top-0" style={{ zIndex: 10 }}>
          <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
            <motion.div initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} className="flex items-center gap-3">
              <div className="relative">
                <motion.div animate={{ rotate: 360 }} transition={{ duration: 10, repeat: Infinity, ease: 'linear' }}
                  className="w-9 h-9 rounded-xl border border-cyan-500/40 flex items-center justify-center"
                  style={{ background: 'linear-gradient(135deg, rgba(0,212,255,0.2), rgba(179,71,255,0.2))' }}>
                  <Cpu size={18} style={{ color: '#00d4ff' }} />
                </motion.div>
                <span className="absolute -top-1 -right-1 w-2.5 h-2.5 rounded-full bg-green-400 border-2 border-slate-900 animate-pulse" />
              </div>
              <div>
                <h1 className="font-bold text-white text-lg leading-none">PodiaCode AI</h1>
                <p className="text-slate-500 text-xs">Medical Coding Engine v1.0</p>
              </div>
            </motion.div>

            <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} className="flex items-center gap-3">
              {CODE_TYPES.map((ct, i) => (
                <motion.span key={ct.label}
                  initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.08 }}
                  className="hidden sm:flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full border border-slate-800 text-slate-400">
                  <span className="w-1.5 h-1.5 rounded-full" style={{ background: ct.color }} />
                  {ct.label}
                </motion.span>
              ))}
            </motion.div>
          </div>
        </header>

        <main className="max-w-7xl mx-auto px-6 py-10">
          <AnimatePresence mode="wait">
            {!result ? (
              <motion.div key="upload" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0, y: -20 }}>
                {/* Hero */}
                {!loading && (
                  <motion.div initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} className="text-center mb-12">
                    <motion.div animate={{ float: [0, -8, 0] } as any}
                      transition={{ duration: 4, repeat: Infinity, ease: 'easeInOut' }}
                      className="inline-flex items-center gap-2 px-4 py-2 rounded-full border border-cyan-500/30 bg-cyan-500/10 text-cyan-400 text-xs font-semibold mb-6">
                      <Zap size={12} className="animate-pulse" />
                      Fully Automated · NCCI-Validated · SNOMED-Mapped
                    </motion.div>

                    <h2 className="text-4xl sm:text-5xl font-black text-white mb-4 leading-tight">
                      Podiatry Notes →{' '}
                      <span className="bg-gradient-to-r from-cyan-400 via-purple-400 to-green-400 bg-clip-text text-transparent">
                        Medical Codes
                      </span>
                    </h2>
                    <p className="text-slate-400 text-lg max-w-xl mx-auto">
                      Upload any podiatry clinical note and receive accurate CPT, ICD-10-CM, HCPCS,
                      and SNOMED codes with full NCCI/MUE compliance — in under one second.
                    </p>

                    {/* Feature pills */}
                    <div className="flex flex-wrap justify-center gap-3 mt-8">
                      {FEATURES.map((f, i) => (
                        <motion.div key={f.label}
                          initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }}
                          transition={{ delay: 0.3 + i * 0.1 }}
                          className="glass-card flex items-center gap-2.5 px-4 py-2.5 rounded-2xl border border-slate-800 hover:border-slate-700 transition-all">
                          <f.icon size={16} style={{ color: f.color }} />
                          <div className="text-left">
                            <p className="text-white text-sm font-semibold">{f.label}</p>
                            <p className="text-slate-500 text-xs">{f.desc}</p>
                          </div>
                        </motion.div>
                      ))}
                    </div>
                  </motion.div>
                )}

                {/* Upload panel */}
                <motion.div
                  initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: loading ? 0 : 0.4 }}
                  className="glass-card p-8 rounded-3xl border border-slate-800 max-w-3xl mx-auto"
                  style={{ boxShadow: '0 0 80px rgba(0,212,255,0.05), 0 0 0 1px rgba(0,212,255,0.08)' }}>
                  {!loading && (
                    <div className="flex items-center gap-3 mb-6">
                      <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-cyan-500/20 to-purple-500/20 border border-cyan-500/30 flex items-center justify-center">
                        <Brain size={18} style={{ color: '#00d4ff' }} />
                      </div>
                      <div>
                        <h3 className="text-white font-semibold">Submit Clinical Note</h3>
                        <p className="text-slate-500 text-sm">PDF upload or paste text directly</p>
                      </div>
                    </div>
                  )}

                  <FileUpload onResult={setResult} onLoading={setLoading} loading={loading} />
                </motion.div>

                {/* DB stats strip */}
                {!loading && (
                  <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.7 }}
                    className="flex flex-wrap justify-center gap-6 mt-10">
                    {CODE_TYPES.map((ct) => (
                      <div key={ct.label} className="text-center">
                        <p className="font-bold font-mono text-sm" style={{ color: ct.color }}>{ct.label}</p>
                        <p className="text-slate-600 text-xs">{ct.desc}</p>
                      </div>
                    ))}
                  </motion.div>
                )}
              </motion.div>
            ) : (
              <motion.div key="results" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
                <ResultsDashboard result={result} onReset={reset} />
              </motion.div>
            )}
          </AnimatePresence>
        </main>

        {/* Footer */}
        {!result && !loading && (
          <footer className="border-t border-slate-900 mt-16 py-6 text-center">
            <p className="text-slate-600 text-sm">
              PodiaCode AI · CPT, ICD-10-CM, HCPCS, SNOMED, NCCI · Advanced Foot & Ankle Coding Engine
            </p>
          </footer>
        )}
      </div>
    </div>
  )
}
