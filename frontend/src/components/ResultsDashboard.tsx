'use client'
import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Download, RefreshCw, AlertTriangle, CheckCircle,
  Shield, Clock, User, FileText, Activity, Eye
} from 'lucide-react'
import { CodingResult } from '@/lib/api'
import { CPTCard, ICDCard, HCPCSCard, SNOMEDCard } from './CodeCards'
import AccuracyRadar from './AccuracyRadar'

type Tab = 'CPT' | 'ICD' | 'HCPCS' | 'SNOMED' | 'AUDIT' | 'JSON'

interface Props {
  result: CodingResult
  onReset: () => void
}

export default function ResultsDashboard({ result, onReset }: Props) {
  const [tab, setTab] = useState<Tab>('CPT')
  const [jsonExpanded, setJsonExpanded] = useState(false)

  const tabs: { id: Tab; label: string; count?: number; color: string }[] = [
    { id: 'CPT', label: 'CPT', count: result.cpt_codes.length, color: 'cyan' },
    { id: 'ICD', label: 'ICD-10-CM', count: result.icd_codes.length, color: 'green' },
    { id: 'HCPCS', label: 'HCPCS', count: result.hcpcs_codes.length, color: 'yellow' },
    { id: 'SNOMED', label: 'SNOMED', count: result.comprehend_snomed.length, color: 'pink' },
    { id: 'AUDIT', label: 'Audit', count: result.pre_submission_audit_findings.length, color: 'orange' },
    { id: 'JSON', label: 'JSON', color: 'purple' },
  ]

  const tabColor: Record<string, string> = {
    cyan: 'border-cyan-500 text-cyan-400 bg-cyan-500/10',
    green: 'border-green-500 text-green-400 bg-green-500/10',
    yellow: 'border-yellow-500 text-yellow-400 bg-yellow-500/10',
    pink: 'border-pink-500 text-pink-400 bg-pink-500/10',
    orange: 'border-orange-500 text-orange-400 bg-orange-500/10',
    purple: 'border-purple-500 text-purple-400 bg-purple-500/10',
  }

  const downloadJSON = () => {
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a'); a.href = url
    a.download = `${result.document_id}.json`; a.click()
    URL.revokeObjectURL(url)
  }

  const tierConfig = result.auto_coding_tier === 'AUTO_APPROVED'
    ? { icon: CheckCircle, color: 'text-green-400', bg: 'bg-green-500/15 border-green-500/30', label: 'Auto Approved' }
    : { icon: AlertTriangle, color: 'text-orange-400', bg: 'bg-orange-500/15 border-orange-500/30', label: 'Review Required' }

  const TierIcon = tierConfig.icon

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="w-full max-w-6xl mx-auto space-y-6">
      {/* Header bar */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <motion.h2 initial={{ x: -20, opacity: 0 }} animate={{ x: 0, opacity: 1 }}
            className="text-xl font-bold text-white">
            Coding Results
          </motion.h2>
          <p className="text-slate-500 text-sm font-mono mt-0.5 truncate max-w-md">{result.document_id}</p>
        </div>
        <div className="flex gap-2">
          <button onClick={downloadJSON}
            className="btn-neon flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium
              bg-slate-800 border border-slate-700 text-slate-300 hover:border-cyan-500/40 hover:text-cyan-400 transition-all">
            <Download size={15} /> Export JSON
          </button>
          <button onClick={onReset}
            className="btn-neon flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium
              bg-slate-800 border border-slate-700 text-slate-300 hover:border-purple-500/40 hover:text-purple-400 transition-all">
            <RefreshCw size={15} /> New Note
          </button>
        </div>
      </div>

      {/* Stats + Radar row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Quick stats */}
        <div className="lg:col-span-2 grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[
            { label: 'CPT Codes', value: result.cpt_codes.length, color: '#00d4ff', icon: Activity },
            { label: 'ICD-10-CM', value: result.icd_codes.length, color: '#00ff88', icon: FileText },
            { label: 'HCPCS', value: result.hcpcs_codes.length, color: '#ffcc00', icon: Shield },
            { label: 'SNOMED', value: result.comprehend_snomed.length, color: '#ff00aa', icon: Eye },
          ].map((stat, i) => (
            <motion.div key={stat.label}
              initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.1 }}
              className="glass-card p-4 rounded-xl border border-slate-800 text-center">
              <stat.icon size={20} className="mx-auto mb-2" style={{ color: stat.color }} />
              <motion.p className="text-2xl font-bold font-mono" style={{ color: stat.color }}
                initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: i * 0.1 + 0.3 }}>
                {stat.value}
              </motion.p>
              <p className="text-slate-500 text-xs mt-0.5">{stat.label}</p>
            </motion.div>
          ))}

          {/* Tier + timing */}
          <div className="col-span-2 sm:col-span-4 grid grid-cols-2 gap-3">
            <div className={`glass-card p-3 rounded-xl border flex items-center gap-3 ${tierConfig.bg}`}>
              <TierIcon size={20} className={tierConfig.color} />
              <div>
                <p className={`font-bold text-sm ${tierConfig.color}`}>{tierConfig.label}</p>
                <p className="text-slate-500 text-xs">{result.auto_coding_summary.split('.')[0]}</p>
              </div>
            </div>
            <div className="glass-card p-3 rounded-xl border border-slate-800 flex items-center gap-3">
              <Clock size={20} className="text-purple-400" />
              <div>
                <p className="text-white font-bold text-sm">{result.processing_time.toFixed(0)}ms</p>
                <p className="text-slate-500 text-xs">Processing time</p>
              </div>
            </div>
          </div>

          {/* Patient info */}
          {result.patient_info?.name && (
            <div className="col-span-2 sm:col-span-4 glass-card p-3 rounded-xl border border-slate-800">
              <div className="flex items-center gap-2 mb-2">
                <User size={15} className="text-cyan-400" />
                <span className="text-slate-400 text-xs font-semibold uppercase tracking-wider">Patient</span>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
                <div><p className="text-slate-500 text-xs">Name</p><p className="text-white">{result.patient_info.name}</p></div>
                <div><p className="text-slate-500 text-xs">DOB</p><p className="text-slate-300">{result.patient_info.dob}</p></div>
                <div><p className="text-slate-500 text-xs">Provider</p><p className="text-slate-300 text-xs">{result.patient_info.provider?.split(',')[0]}</p></div>
                <div><p className="text-slate-500 text-xs">Visit Type</p>
                  <span className="text-xs bg-slate-800 text-slate-300 px-2 py-0.5 rounded-full capitalize">
                    {result.patient_info.visit_type}
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* Validation issues */}
          {result.validation_issues.length > 0 && (
            <div className="col-span-2 sm:col-span-4">
              {result.validation_issues.map((vi, i) => (
                <div key={i} className="flex items-start gap-2 p-2.5 rounded-xl bg-red-500/10 border border-red-500/25 text-xs text-red-400 mb-2">
                  <AlertTriangle size={13} className="flex-shrink-0 mt-0.5" />
                  <div>
                    <span className="font-bold">{vi.type}: </span>{vi.message}
                    {vi.recommendation && <div className="text-red-300/70 mt-0.5">{vi.recommendation}</div>}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Radar chart */}
        {result.code_accuracy_by_type && (
          <AccuracyRadar accuracy={result.code_accuracy_by_type} overallConfidence={result.confidence_at_coding} />
        )}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 overflow-x-auto pb-1 border-b border-slate-800">
        {tabs.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-t-lg text-sm font-medium whitespace-nowrap transition-all duration-200
              ${tab === t.id ? tabColor[t.color] + ' border-b-2' : 'text-slate-500 hover:text-slate-300'}`}>
            {t.label}
            {t.count !== undefined && (
              <span className={`text-xs px-1.5 py-0.5 rounded-full ${tab === t.id ? 'bg-white/20' : 'bg-slate-800'}`}>
                {t.count}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <AnimatePresence mode="wait">
        <motion.div key={tab} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -5 }}
          transition={{ duration: 0.2 }}>
          {tab === 'CPT' && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {result.cpt_codes.length ? result.cpt_codes.map((c, i) => <CPTCard key={c.code} code={c} index={i} />)
                : <EmptyState label="No CPT codes generated" />}
            </div>
          )}
          {tab === 'ICD' && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {result.icd_codes.length ? result.icd_codes.map((c, i) => <ICDCard key={c.code} code={c} index={i} />)
                : <EmptyState label="No ICD-10-CM codes generated" />}
            </div>
          )}
          {tab === 'HCPCS' && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {result.hcpcs_codes.length ? result.hcpcs_codes.map((c, i) => <HCPCSCard key={c.code} code={c} index={i} />)
                : <EmptyState label="No HCPCS codes generated" />}
            </div>
          )}
          {tab === 'SNOMED' && (
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
              {result.comprehend_snomed.length ? result.comprehend_snomed.map((c, i) => <SNOMEDCard key={c.concept_id} concept={c} index={i} />)
                : <EmptyState label="No SNOMED concepts mapped" />}
            </div>
          )}
          {tab === 'AUDIT' && <AuditPanel result={result} />}
          {tab === 'JSON' && <JSONPanel result={result} />}
        </motion.div>
      </AnimatePresence>
    </motion.div>
  )
}

function AuditPanel({ result }: { result: CodingResult }) {
  const findings = result.pre_submission_audit_findings
  const audit = result.documentation_audit

  const severityStyles: Record<string, string> = {
    ERROR: 'border-red-500/30 bg-red-500/8 text-red-400',
    WARNING: 'border-orange-500/30 bg-orange-500/8 text-orange-400',
    INFO: 'border-cyan-500/30 bg-cyan-500/8 text-cyan-400',
  }

  return (
    <div className="space-y-4">
      {/* Score */}
      <div className="glass-card p-4 rounded-xl border border-slate-800">
        <div className="flex justify-between items-center mb-3">
          <h4 className="text-slate-200 font-semibold">Pre-Submission Audit</h4>
          <span className={`text-xl font-bold font-mono ${result.pre_submission_audit_score >= 0.9 ? 'text-green-400' : 'text-orange-400'}`}>
            {Math.round(result.pre_submission_audit_score * 100)}%
          </span>
        </div>
        <div className="grid grid-cols-3 gap-3 text-center text-sm">
          <div className="bg-green-500/10 rounded-xl p-3 border border-green-500/20">
            <p className="text-green-400 font-bold text-xl">{audit?.fully_supported ?? 0}</p>
            <p className="text-slate-500 text-xs">Supported</p>
          </div>
          <div className="bg-orange-500/10 rounded-xl p-3 border border-orange-500/20">
            <p className="text-orange-400 font-bold text-xl">{audit?.partially_supported ?? 0}</p>
            <p className="text-slate-500 text-xs">Partial</p>
          </div>
          <div className="bg-red-500/10 rounded-xl p-3 border border-red-500/20">
            <p className="text-red-400 font-bold text-xl">{audit?.unsupported ?? 0}</p>
            <p className="text-slate-500 text-xs">Unsupported</p>
          </div>
        </div>
      </div>

      {/* Findings */}
      <div className="space-y-2">
        {findings.map((f, i) => (
          <motion.div key={i} initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.05 }}
            className={`p-3 rounded-xl border text-sm ${severityStyles[f.severity] || severityStyles.INFO}`}>
            <div className="flex items-start gap-2">
              <AlertTriangle size={14} className="flex-shrink-0 mt-0.5" />
              <div>
                <div className="flex items-center gap-2 flex-wrap mb-0.5">
                  <span className="font-bold uppercase text-xs">{f.severity}</span>
                  {f.code && <span className="font-mono text-xs bg-black/30 px-1.5 py-0.5 rounded">{f.code}</span>}
                  <span className="text-xs opacity-70">{f.category}</span>
                </div>
                <p>{f.message}</p>
                {f.recommendation && <p className="opacity-70 text-xs mt-1 italic">{f.recommendation}</p>}
              </div>
            </div>
          </motion.div>
        ))}
        {!findings.length && <EmptyState label="No audit findings — note is clean!" icon="✓" green />}
      </div>

      {/* Global surgery */}
      {result.global_surgery_warnings?.length > 0 && (
        <div className="glass-card p-4 rounded-xl border border-yellow-500/20">
          <h4 className="text-yellow-400 font-semibold mb-2 flex items-center gap-2">
            <Shield size={15} /> Global Surgery Alerts
          </h4>
          {result.global_surgery_warnings.map((g: any, i: number) => (
            <div key={i} className="text-sm text-slate-300 mb-1">
              <span className="font-mono text-yellow-400">{g.code}</span>: {g.message}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function JSONPanel({ result }: { result: CodingResult }) {
  const [copied, setCopied] = useState(false)
  const json = JSON.stringify(result, null, 2)
  const copy = () => { navigator.clipboard.writeText(json); setCopied(true); setTimeout(() => setCopied(false), 2000) }

  return (
    <div className="glass-card rounded-2xl border border-slate-800 overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2 bg-slate-900/60 border-b border-slate-800">
        <span className="text-slate-400 text-sm font-mono">output.json</span>
        <button onClick={copy}
          className="text-xs text-slate-500 hover:text-cyan-400 transition-colors px-2 py-1 rounded border border-slate-700 hover:border-cyan-500/40">
          {copied ? '✓ Copied!' : 'Copy'}
        </button>
      </div>
      <div className="overflow-auto max-h-[600px]">
        <pre className="json-view text-slate-300 p-4 whitespace-pre-wrap break-all text-xs leading-relaxed">
          <JsonHighlight json={json} />
        </pre>
      </div>
    </div>
  )
}

function JsonHighlight({ json }: { json: string }) {
  const html = json
    .replace(/("(?:[^"\\]|\\.)*")\s*:/g, '<span style="color:#7dd3fc">$1</span>:')
    .replace(/:\s*("(?:[^"\\]|\\.)*")/g, ': <span style="color:#86efac">$1</span>')
    .replace(/:\s*(\d+\.?\d*)/g, ': <span style="color:#fb923c">$1</span>')
    .replace(/:\s*(true|false|null)/g, ': <span style="color:#c084fc">$1</span>')
  return <span dangerouslySetInnerHTML={{ __html: html }} />
}

function EmptyState({ label, icon = '—', green = false }: { label: string; icon?: string; green?: boolean }) {
  return (
    <div className={`col-span-full flex flex-col items-center justify-center py-16 text-center ${green ? 'text-green-400' : 'text-slate-500'}`}>
      <span className="text-4xl mb-3">{icon}</span>
      <p className="text-sm">{label}</p>
    </div>
  )
}
