'use client'
import { motion } from 'framer-motion'

interface Props {
  value: number  // 0–1
  size?: 'sm' | 'md' | 'lg'
  showLabel?: boolean
  delay?: number
}

function getColor(v: number) {
  if (v >= 0.90) return { from: '#00d4ff', to: '#00ff88', text: 'text-green-400' }
  if (v >= 0.80) return { from: '#00d4ff', to: '#b347ff', text: 'text-cyan-400' }
  if (v >= 0.70) return { from: '#ff8c00', to: '#ffcc00', text: 'text-orange-400' }
  return { from: '#ff3366', to: '#ff8c00', text: 'text-red-400' }
}

export default function ConfidenceBar({ value, size = 'md', showLabel = true, delay = 0 }: Props) {
  const color = getColor(value)
  const heights = { sm: 'h-1', md: 'h-1.5', lg: 'h-2.5' }
  const pct = Math.round(value * 100)

  return (
    <div className="w-full">
      <div className={`confidence-bar ${heights[size]} w-full`}>
        <motion.div
          className="confidence-fill h-full"
          style={{ background: `linear-gradient(90deg, ${color.from}, ${color.to})` }}
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 1, delay, ease: 'easeOut' }}
        />
      </div>
      {showLabel && (
        <motion.span
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: delay + 0.3 }}
          className={`text-xs font-mono font-semibold ${color.text} mt-0.5 block text-right`}
        >
          {pct}%
        </motion.span>
      )}
    </div>
  )
}
