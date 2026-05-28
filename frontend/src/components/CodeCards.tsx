'use client'
import { motion } from 'framer-motion'
import { AlertTriangle, CheckCircle, Info, Link, Shield } from 'lucide-react'
import ConfidenceBar from './ConfidenceBar'
import { CPTCode, HCPCSCode, ICDCode, SNOMEDConcept } from '@/lib/api'

const cardVariants = {
  hidden: { opacity: 0, y: 20, scale: 0.97 },
  visible: (i: number) => ({
    opacity: 1, y: 0, scale: 1,
    transition: { delay: i * 0.08, duration: 0.4, ease: 'easeOut' }
  }),
}

// ── CPT Card ────────────────────────────────────────────────────────────────

export function CPTCard({ code, index }: { code: CPTCode; index: number }) {
  const isEM = code.source === 'mdm_based'
  const color = isEM ? 'purple' : 'cyan'
  const borderColor = isEM ? 'border-purple-500/30' : 'border-cyan-500/20'
  const bgColor = isEM ? 'bg-purple-500/5' : 'bg-cyan-500/3'
  const badgeColor = isEM ? 'bg-purple-500/20 text-purple-300 border-purple-500/30' : 'bg-cyan-500/20 text-cyan-300 border-cyan-500/30'

  return (
    <motion.div custom={index} initial="hidden" animate="visible" variants={cardVariants}
      className={`glass-card p-4 rounded-xl border ${borderColor} ${bgColor} hover:border-opacity-60 transition-all`}>
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex items-center gap-2 flex-wrap">
          <span className={`code-badge border ${badgeColor}`}>{code.code}</span>
          {code.modifiers.map(m => (
            <span key={m} className="code-badge bg-yellow-500/15 text-yellow-300 border border-yellow-500/30 text-xs">{m}</span>
          ))}
          {isEM && <span className="text-xs bg-purple-500/20 text-purple-300 px-2 py-0.5 rounded-full border border-purple-500/30">E/M</span>}
          {code.procedure_status === 'planned' && (
            <span className="text-xs bg-orange-500/20 text-orange-300 px-2 py-0.5 rounded-full border border-orange-500/30">Planned</span>
          )}
        </div>
        <StatusIcon needs_review={code.needs_review} confidence={code.confidence} />
      </div>

      <p className="text-slate-300 text-sm leading-relaxed mb-3 line-clamp-2">{code.description}</p>

      {/* MDM details */}
      {isEM && code.mdm_details && (
        <div className="grid grid-cols-3 gap-2 mb-3">
          {(['problem', 'data', 'risk'] as const).map(k => (
            <div key={k} className="bg-slate-800/50 rounded-lg p-2 text-center">
              <p className="text-slate-500 text-xs capitalize">{k}</p>
              <p className="text-purple-300 font-bold font-mono">{code.mdm_details![`${k}_score` as keyof typeof code.mdm_details]}/4</p>
            </div>
          ))}
        </div>
      )}

      {/* Laterality & units */}
      <div className="flex gap-3 mb-3 text-xs text-slate-500">
        {code.laterality && <span>📍 {code.laterality}</span>}
        {code.units && code.units > 1 && <span>× {code.units} units</span>}
        {code.medical_necessity && <span className="text-green-500">✓ Medical necessity</span>}
      </div>

      {/* Linked diagnoses */}
      {code.linked_diagnoses?.length > 0 && (
        <div className="flex items-center gap-1.5 flex-wrap">
          <Link size={11} className="text-slate-600" />
          {code.linked_diagnoses.map(ld => (
            <span key={ld.code} className="text-xs bg-slate-800 text-slate-400 px-2 py-0.5 rounded-md border border-slate-700 font-mono">
              {ld.code}
            </span>
          ))}
        </div>
      )}

      {/* Evidence */}
      {code.evidence_spans && code.evidence_spans.length > 0 && (
        <div className="mt-2 p-2 rounded-lg bg-slate-900/60 border border-slate-800">
          <p className="text-xs text-slate-500 italic truncate">"{code.evidence_spans[0]}"</p>
        </div>
      )}

      <div className="mt-3">
        <ConfidenceBar value={code.confidence} delay={index * 0.08} />
      </div>

      {code.needs_review && code.review_reason && (
        <div className="mt-2 flex items-start gap-1.5 text-xs text-orange-400 bg-orange-500/8 rounded-lg p-2 border border-orange-500/20">
          <AlertTriangle size={12} className="flex-shrink-0 mt-0.5" />
          <span>{code.review_reason}</span>
        </div>
      )}
    </motion.div>
  )
}

// ── ICD Card ─────────────────────────────────────────────────────────────────

export function ICDCard({ code, index }: { code: ICDCode; index: number }) {
  return (
    <motion.div custom={index} initial="hidden" animate="visible" variants={cardVariants}
      className="glass-card p-4 rounded-xl border border-green-500/20 bg-green-500/3 hover:border-green-500/40 transition-all">
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="code-badge bg-green-500/20 text-green-300 border border-green-500/30">{code.code}</span>
          {code.laterality && (
            <span className="text-xs bg-slate-800 text-slate-400 px-2 py-0.5 rounded-full border border-slate-700">{code.laterality}</span>
          )}
          {code.resolver_injected && (
            <span className="text-xs bg-blue-500/15 text-blue-300 px-2 py-0.5 rounded-full border border-blue-500/30">Injected</span>
          )}
        </div>
        <StatusIcon needs_review={code.needs_review} confidence={code.confidence} />
      </div>

      <p className="text-slate-300 text-sm leading-relaxed mb-2">{code.description}</p>

      <div className="text-xs text-slate-600 mb-3">
        Source: <span className="text-slate-500 font-mono">{code.source}</span>
      </div>

      {code.evidence_spans && code.evidence_spans.length > 0 && (
        <div className="mb-3 p-2 rounded-lg bg-slate-900/60 border border-slate-800">
          <p className="text-xs text-slate-500 italic truncate">"{code.evidence_spans[0]}"</p>
        </div>
      )}

      <ConfidenceBar value={code.confidence} delay={index * 0.08} />

      {code.needs_review && code.review_reason && (
        <div className="mt-2 flex items-start gap-1.5 text-xs text-orange-400 bg-orange-500/8 rounded-lg p-2 border border-orange-500/20">
          <AlertTriangle size={12} className="flex-shrink-0 mt-0.5" />
          <span>{code.review_reason}</span>
        </div>
      )}
    </motion.div>
  )
}

// ── HCPCS Card ───────────────────────────────────────────────────────────────

export function HCPCSCard({ code, index }: { code: HCPCSCode; index: number }) {
  return (
    <motion.div custom={index} initial="hidden" animate="visible" variants={cardVariants}
      className="glass-card p-4 rounded-xl border border-yellow-500/20 bg-yellow-500/3 hover:border-yellow-500/40 transition-all">
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="code-badge bg-yellow-500/20 text-yellow-300 border border-yellow-500/30">{code.code}</span>
          {code.quantity && code.quantity > 1 && (
            <span className="text-xs bg-slate-800 text-slate-400 px-2 py-0.5 rounded-full border border-slate-700">
              × {code.quantity} units
            </span>
          )}
        </div>
        <StatusIcon needs_review={code.needs_review} confidence={code.confidence} />
      </div>

      <p className="text-slate-300 text-sm leading-relaxed mb-2">{code.description}</p>

      <div className="text-xs text-slate-600 mb-3">
        Source: <span className="text-slate-500 font-mono">{code.source}</span>
      </div>

      {code.linked_diagnoses?.length > 0 && (
        <div className="flex items-center gap-1.5 flex-wrap mb-2">
          <Link size={11} className="text-slate-600" />
          {code.linked_diagnoses.map(ld => (
            <span key={ld.code} className="text-xs bg-slate-800 text-slate-400 px-2 py-0.5 rounded-md border border-slate-700 font-mono">
              {ld.code}
            </span>
          ))}
        </div>
      )}

      <ConfidenceBar value={code.confidence} delay={index * 0.08} />
    </motion.div>
  )
}

// ── SNOMED Card ───────────────────────────────────────────────────────────────

export function SNOMEDCard({ concept, index }: { concept: SNOMEDConcept; index: number }) {
  return (
    <motion.div custom={index} initial="hidden" animate="visible" variants={cardVariants}
      className="glass-card p-3.5 rounded-xl border border-pink-500/20 bg-pink-500/3 hover:border-pink-500/40 transition-all">
      <div className="flex items-start justify-between gap-2 mb-1.5">
        <span className="code-badge bg-pink-500/20 text-pink-300 border border-pink-500/30 text-xs">{concept.concept_id}</span>
        <span className="text-xs text-slate-500 font-mono">{Math.round(concept.score * 100)}%</span>
      </div>
      <p className="text-slate-200 text-sm font-medium mb-0.5">{concept.description}</p>
      <p className="text-slate-500 text-xs italic mb-2">"{concept.entity_text}"</p>
      <ConfidenceBar value={concept.score} size="sm" showLabel={false} delay={index * 0.05} />
    </motion.div>
  )
}

// ── Shared status icon ────────────────────────────────────────────────────────

function StatusIcon({ needs_review, confidence }: { needs_review?: boolean; confidence: number }) {
  if (needs_review) return <AlertTriangle size={15} className="text-orange-400 flex-shrink-0" />
  if (confidence >= 0.90) return <CheckCircle size={15} className="text-green-400 flex-shrink-0" />
  if (confidence >= 0.80) return <Shield size={15} className="text-cyan-400 flex-shrink-0" />
  return <Info size={15} className="text-yellow-400 flex-shrink-0" />
}
