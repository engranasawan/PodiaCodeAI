'use client'
import { useCallback, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import { motion, AnimatePresence } from 'framer-motion'
import { Upload, FileText, X, Zap, Brain } from 'lucide-react'
import { uploadPDF, submitText, CodingResult } from '@/lib/api'

interface Props {
  onResult: (result: CodingResult) => void
  onLoading: (loading: boolean) => void
  loading: boolean
}

export default function FileUpload({ onResult, onLoading, loading }: Props) {
  const [mode, setMode] = useState<'file' | 'text'>('file')
  const [noteText, setNoteText] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [processingStep, setProcessingStep] = useState(0)

  const STEPS = [
    'Initializing neural pipeline...',
    'Parsing clinical note sections...',
    'Extracting clinical entities...',
    'Generating ICD-10-CM codes...',
    'Generating CPT codes...',
    'Mapping HCPCS codes...',
    'Mapping SNOMED concepts...',
    'Running NCCI/MUE validation...',
    'Compiling documentation audit...',
    'Finalizing output...',
  ]

  const startProcessing = async (fn: () => Promise<CodingResult>) => {
    setError(null)
    onLoading(true)
    setProcessingStep(0)

    const interval = setInterval(() => {
      setProcessingStep(prev => Math.min(prev + 1, STEPS.length - 1))
    }, 600)

    try {
      const result = await fn()
      clearInterval(interval)
      setProcessingStep(STEPS.length - 1)
      setTimeout(() => { onResult(result); onLoading(false) }, 400)
    } catch (err: any) {
      clearInterval(interval)
      setError(err?.response?.data?.detail || err?.message || 'Processing failed. Is the backend running?')
      onLoading(false)
    }
  }

  const onDrop = useCallback((accepted: File[]) => {
    if (accepted[0]) setFile(accepted[0])
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'application/pdf': ['.pdf'] },
    maxFiles: 1,
    disabled: loading,
  })

  const handleSubmit = async () => {
    if (mode === 'file' && file) {
      await startProcessing(() => uploadPDF(file))
    } else if (mode === 'text' && noteText.trim().length > 50) {
      await startProcessing(() => submitText(noteText.trim()))
    } else {
      setError(mode === 'file' ? 'Please select a PDF file.' : 'Note text must be at least 50 characters.')
    }
  }

  return (
    <div className="w-full max-w-3xl mx-auto">
      {/* Mode Toggle */}
      <div className="flex gap-2 mb-6 p-1 glass-card rounded-xl">
        {(['file', 'text'] as const).map(m => (
          <button
            key={m}
            onClick={() => setMode(m)}
            className={`flex-1 py-2.5 px-4 rounded-lg text-sm font-medium transition-all duration-300 flex items-center justify-center gap-2
              ${mode === m ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/40 shadow-neon-cyan' : 'text-slate-400 hover:text-slate-200'}`}
          >
            {m === 'file' ? <FileText size={15} /> : <Brain size={15} />}
            {m === 'file' ? 'Upload PDF' : 'Paste Note Text'}
          </button>
        ))}
      </div>

      <AnimatePresence mode="wait">
        {mode === 'file' ? (
          <motion.div key="file" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }}>
            <div
              {...getRootProps()}
              className={`drop-zone border-2 border-dashed rounded-2xl p-12 text-center cursor-pointer transition-all duration-300
                ${isDragActive ? 'active border-cyan-400 bg-cyan-500/5' : 'border-slate-700 hover:border-cyan-500/40 hover:bg-cyan-500/3'}
                ${file ? 'border-cyan-500/60 bg-cyan-500/5' : ''}
                ${loading ? 'pointer-events-none opacity-50' : ''}`}
            >
              <input {...getInputProps()} />
              <AnimatePresence mode="wait">
                {file ? (
                  <motion.div key="file-selected" initial={{ scale: 0.9, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} className="flex flex-col items-center gap-3">
                    <div className="w-14 h-14 rounded-2xl bg-cyan-500/20 border border-cyan-500/40 flex items-center justify-center">
                      <FileText className="text-cyan-400" size={28} />
                    </div>
                    <div>
                      <p className="text-cyan-300 font-semibold">{file.name}</p>
                      <p className="text-slate-500 text-sm mt-1">{(file.size / 1024).toFixed(1)} KB</p>
                    </div>
                    <button onClick={e => { e.stopPropagation(); setFile(null) }}
                      className="text-slate-500 hover:text-red-400 transition-colors flex items-center gap-1 text-sm">
                      <X size={14} /> Remove
                    </button>
                  </motion.div>
                ) : (
                  <motion.div key="upload-prompt" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex flex-col items-center gap-4">
                    <motion.div animate={{ y: [0, -8, 0] }} transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
                      className="w-16 h-16 rounded-2xl bg-gradient-to-br from-cyan-500/20 to-purple-500/20 border border-cyan-500/30 flex items-center justify-center">
                      <Upload className="text-cyan-400" size={30} />
                    </motion.div>
                    <div>
                      <p className="text-lg font-semibold text-slate-200">
                        {isDragActive ? 'Release to analyze...' : 'Drop podiatry note PDF here'}
                      </p>
                      <p className="text-slate-500 text-sm mt-1">or click to browse · PDF files only · max 20MB</p>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </motion.div>
        ) : (
          <motion.div key="text" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }}>
            <textarea
              value={noteText}
              onChange={e => setNoteText(e.target.value)}
              disabled={loading}
              placeholder="Paste the full clinical note here...

Example: Chief Complaint, HPI, Physical Exam, Assessment/Diagnoses, Plan..."
              className="w-full h-64 bg-slate-900/60 border border-slate-700 hover:border-cyan-500/40 focus:border-cyan-500/60 
                rounded-2xl p-4 text-sm text-slate-300 placeholder:text-slate-600 resize-none outline-none
                transition-all duration-300 font-mono leading-relaxed"
            />
            <p className="text-right text-xs text-slate-600 mt-1">{noteText.length} characters</p>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Error */}
      <AnimatePresence>
        {error && (
          <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }}
            className="mt-4 p-3 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-sm flex items-center gap-2">
            <X size={15} /> {error}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Processing overlay */}
      <AnimatePresence>
        {loading && (
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
            className="mt-6 glass-card p-5 rounded-2xl border border-cyan-500/20">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-6 h-6 rounded-full processing-ring flex-shrink-0" />
              <span className="text-cyan-400 text-sm font-mono typing-cursor">{STEPS[processingStep]}</span>
            </div>
            <div className="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
              <motion.div
                className="h-full rounded-full bg-gradient-to-r from-cyan-500 via-purple-500 to-green-500"
                animate={{ width: `${((processingStep + 1) / STEPS.length) * 100}%` }}
                transition={{ duration: 0.5, ease: 'easeOut' }}
              />
            </div>
            <div className="flex justify-between mt-1.5">
              <span className="text-slate-600 text-xs">Step {processingStep + 1}/{STEPS.length}</span>
              <span className="text-slate-600 text-xs">{Math.round(((processingStep + 1) / STEPS.length) * 100)}%</span>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Submit button */}
      <motion.button
        onClick={handleSubmit}
        disabled={loading || (mode === 'file' && !file) || (mode === 'text' && noteText.trim().length < 50)}
        whileHover={{ scale: 1.02 }}
        whileTap={{ scale: 0.98 }}
        className={`btn-neon mt-6 w-full py-4 rounded-2xl font-bold text-base flex items-center justify-center gap-3
          transition-all duration-300
          ${loading || (mode === 'file' && !file) || (mode === 'text' && noteText.trim().length < 50)
            ? 'bg-slate-800 text-slate-600 cursor-not-allowed border border-slate-700'
            : 'bg-gradient-to-r from-cyan-600 to-purple-600 hover:from-cyan-500 hover:to-purple-500 text-white shadow-neon-cyan border border-cyan-500/40'
          }`}
      >
        <Zap size={18} className={loading ? 'animate-pulse' : ''} />
        {loading ? 'Analyzing...' : 'Generate Medical Codes'}
      </motion.button>
    </div>
  )
}
