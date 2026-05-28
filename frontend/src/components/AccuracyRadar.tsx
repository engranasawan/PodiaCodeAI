'use client'
import { motion } from 'framer-motion'
import { RadarChart, Radar, PolarGrid, PolarAngleAxis, ResponsiveContainer, Tooltip } from 'recharts'
import { AccuracyByType } from '@/lib/api'

interface Props {
  accuracy: AccuracyByType
  overallConfidence: number
}

const CustomTooltip = ({ active, payload }: any) => {
  if (active && payload?.length) {
    return (
      <div className="glass-card border border-cyan-500/30 p-3 rounded-xl text-sm">
        <p className="text-cyan-400 font-mono font-bold">{payload[0].payload.type}</p>
        <p className="text-white">{payload[0].value?.toFixed(1)}%</p>
      </div>
    )
  }
  return null
}

export default function AccuracyRadar({ accuracy, overallConfidence }: Props) {
  const data = [
    { type: 'CPT', value: accuracy.CPT?.accuracy_pct ?? 0, count: accuracy.CPT?.count ?? 0 },
    { type: 'ICD-10-CM', value: accuracy.ICD10CM?.accuracy_pct ?? 0, count: accuracy.ICD10CM?.count ?? 0 },
    { type: 'HCPCS', value: accuracy.HCPCS?.accuracy_pct ?? 0, count: accuracy.HCPCS?.count ?? 0 },
    { type: 'SNOMED', value: accuracy.SNOMED?.accuracy_pct ?? 0, count: accuracy.SNOMED?.count ?? 0 },
  ]

  const tier = overallConfidence >= 0.92 ? { label: 'EXCELLENT', color: 'text-green-400', bg: 'bg-green-500/20 border-green-500/30' }
    : overallConfidence >= 0.85 ? { label: 'GOOD', color: 'text-cyan-400', bg: 'bg-cyan-500/20 border-cyan-500/30' }
    : { label: 'REVIEW', color: 'text-orange-400', bg: 'bg-orange-500/20 border-orange-500/30' }

  return (
    <div className="glass-card p-5 rounded-2xl border border-cyan-500/15">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-slate-200 font-semibold">Coding Accuracy</h3>
        <span className={`text-xs font-bold px-3 py-1 rounded-full border ${tier.bg} ${tier.color}`}>
          {tier.label}
        </span>
      </div>

      {/* Radar */}
      <ResponsiveContainer width="100%" height={200}>
        <RadarChart data={data}>
          <PolarGrid stroke="rgba(0,212,255,0.1)" />
          <PolarAngleAxis dataKey="type" tick={{ fill: '#94a3b8', fontSize: 11 }} />
          <Radar
            dataKey="value"
            stroke="#00d4ff"
            fill="rgba(0,212,255,0.15)"
            strokeWidth={2}
          />
          <Tooltip content={<CustomTooltip />} />
        </RadarChart>
      </ResponsiveContainer>

      {/* Stats row */}
      <div className="grid grid-cols-2 gap-3 mt-2">
        {data.map((d, i) => (
          <motion.div key={d.type}
            initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.3 + i * 0.1 }}
            className="flex items-center justify-between bg-slate-900/50 rounded-xl p-3 border border-slate-800">
            <div>
              <p className="text-slate-400 text-xs">{d.type}</p>
              <p className="text-white font-bold font-mono text-sm">{d.count} codes</p>
            </div>
            <div className="text-right">
              <p className={`font-bold font-mono text-lg ${
                d.value >= 90 ? 'text-green-400' : d.value >= 80 ? 'text-cyan-400' : 'text-orange-400'
              }`}>
                {d.value?.toFixed(1)}%
              </p>
            </div>
          </motion.div>
        ))}
      </div>

      {/* Overall */}
      <div className="mt-4 p-3 rounded-xl bg-gradient-to-r from-cyan-500/10 to-purple-500/10 border border-cyan-500/20">
        <div className="flex justify-between items-center">
          <span className="text-slate-400 text-sm">Overall Confidence</span>
          <span className="text-2xl font-bold font-mono text-glow-cyan" style={{ color: '#00d4ff' }}>
            {(overallConfidence * 100).toFixed(1)}%
          </span>
        </div>
      </div>
    </div>
  )
}
