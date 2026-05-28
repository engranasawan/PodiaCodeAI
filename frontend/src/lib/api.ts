import axios from 'axios'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export const api = axios.create({
  baseURL: API_BASE,
  timeout: 120000,
})

export async function uploadPDF(file: File): Promise<CodingResult> {
  const form = new FormData()
  form.append('file', file)
  const { data } = await api.post<CodingResult>('/api/code/pdf', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function submitText(text: string, documentId?: string): Promise<CodingResult> {
  const { data } = await api.post<CodingResult>('/api/code/text', {
    text,
    document_id: documentId,
  })
  return data
}

export async function healthCheck() {
  const { data } = await api.get('/health')
  return data
}

// ─── Types ────────────────────────────────────────────────────────────────────

export interface CodingResult {
  document_id: string
  timestamp: string
  success: boolean
  processing_time: number
  patient_info?: PatientInfo
  cpt_codes: CPTCode[]
  hcpcs_codes: HCPCSCode[]
  icd_codes: ICDCode[]
  comprehend_snomed: SNOMEDConcept[]
  error_message?: string
  validation_issues: ValidationIssue[]
  warnings: any[]
  documentation_audit: DocumentationAudit
  pre_submission_audit_findings: AuditFinding[]
  pre_submission_audit_score: number
  lcd_ncd_findings: any[]
  global_surgery_warnings: any[]
  auto_coding_tier: 'AUTO_APPROVED' | 'REVIEW' | 'MANUAL'
  auto_coding_confidence: number
  auto_coding_review_reasons: string[]
  auto_coding_summary: string
  encounter_integrity: EncounterIntegrity
  code_accuracy_by_type: AccuracyByType
  uncertainty_score: number
  confidence_at_coding: number
}

export interface PatientInfo {
  name?: string
  dob?: string
  mrn?: string
  provider?: string
  npi?: string
  date_of_service?: string
  insurance?: string
  visit_type?: string
}

export interface CPTCode {
  code: string
  description: string
  short_description?: string
  confidence: number
  modifiers: string[]
  source: string
  mdm_details?: MDMDetails
  reasoning?: string
  evidence_spans?: string[]
  linked_diagnoses?: LinkedDiagnosis[]
  medical_necessity?: boolean
  procedure_status?: string
  laterality?: string
  units?: number
  modifier_reasoning?: string[]
  needs_review?: boolean
  review_reason?: string
}

export interface MDMDetails {
  mdm_level: string
  problem_score: number
  data_score: number
  risk_score: number
  effective_score: number
  em_level_new: string
  em_level_established: string
  reasoning: string
}

export interface HCPCSCode {
  code: string
  description: string
  confidence: number
  source: string
  quantity?: number
  modifiers?: string[]
  linked_diagnoses?: LinkedDiagnosis[]
  needs_review?: boolean
}

export interface ICDCode {
  code: string
  description: string
  confidence: number
  source: string
  laterality?: string
  needs_review?: boolean
  review_reason?: string
  evidence_spans?: string[]
  resolver_injected?: boolean
}

export interface SNOMEDConcept {
  entity_text: string
  concept_id: string
  description: string
  score: number
  source: string
}

export interface LinkedDiagnosis {
  code: string
  description: string
  linkage_type: string
}

export interface ValidationIssue {
  type: string
  severity: string
  message: string
  recommendation?: string
  code?: string
  code1?: string
  code2?: string
}

export interface AuditFinding {
  severity: string
  code?: string
  category: string
  message: string
  recommendation?: string
  denial_risk?: string
}

export interface DocumentationAudit {
  audit_entries: AuditEntry[]
  total_codes: number
  fully_supported: number
  partially_supported: number
  unsupported: number
  documentation_score: number
}

export interface AuditEntry {
  code: string
  description: string
  documentation_support: string[]
  documentation_gaps: string[]
  supported: boolean
}

export interface EncounterIntegrity {
  encounter_issues: any[]
  error_count: number
  warning_count: number
}

export interface AccuracyByType {
  CPT: { count: number; avg_confidence?: number; accuracy_pct?: number }
  HCPCS: { count: number; avg_confidence?: number; accuracy_pct?: number }
  ICD10CM: { count: number; avg_confidence?: number; accuracy_pct?: number }
  SNOMED: { count: number; avg_confidence?: number; accuracy_pct?: number }
}
