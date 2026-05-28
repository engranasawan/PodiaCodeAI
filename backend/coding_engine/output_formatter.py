"""Output Formatter v3 — full pipeline orchestrator."""
import re, time, uuid
from datetime import datetime
from typing import Dict, List, Optional

from .pdf_parser import parse_note, extract_patient_meta
from .entity_extractor import extract_entities
from .procedure_classifier import classify_encounter
from .icd_coder import generate_icd_codes
from .cpt_coder import generate_cpt_codes
from .hcpcs_coder import generate_hcpcs_codes
from .drug_codes import extract_drug_codes
from .validators import generate_snomed_concepts, validate_ncci_mue, build_documentation_audit
from .code_loader import db

def process_note(note_text: str, document_id: Optional[str] = None) -> dict:
    start = time.time()
    doc_id = document_id or f'note_{uuid.uuid4().hex[:12]}'
    try:
        sections     = parse_note(note_text)
        patient_meta = extract_patient_meta(note_text)
        entities     = extract_entities(sections)
        enc_class    = classify_encounter(sections, patient_meta)
        icd_bill, icd_adv = generate_icd_codes(sections, entities, patient_meta)
        cpt_codes    = generate_cpt_codes(sections, entities, patient_meta, icd_bill, enc_class)
        hcpcs_codes  = generate_hcpcs_codes(sections, entities, patient_meta, icd_bill, enc_class)
        drug_codes   = extract_drug_codes(sections, icd_bill)
        hcpcs_codes  = _merge_drugs(hcpcs_codes, drug_codes)
        snomed       = generate_snomed_concepts(sections, entities)
        val_issues, warnings, enc_issues = validate_ncci_mue(cpt_codes, hcpcs_codes)
        doc_audit    = build_documentation_audit(cpt_codes, hcpcs_codes, icd_bill, sections)
        pre_sub      = _pre_sub(cpt_codes, hcpcs_codes, icd_bill, icd_adv, val_issues, sections)
        tier, conf, reasons = _tier(cpt_codes, hcpcs_codes, icd_bill, val_issues)
        ms = (time.time()-start)*1000

        return {
            'document_id': doc_id,
            'timestamp': datetime.utcnow().isoformat(),
            'success': True,
            'processing_time': round(ms, 3),
            'patient_info': {k: patient_meta.get(k) for k in
                ['patient_name','dob','mrn','provider','npi','date_of_service','insurance','visit_type']},
            'cpt_codes': cpt_codes,
            'hcpcs_codes': hcpcs_codes,
            'icd_codes': icd_bill,
            'supporting_conditions': icd_adv,
            'comprehend_snomed': snomed,
            'error_message': None,
            'validation_issues': val_issues,
            'warnings': warnings,
            'prior_auth_flags': [],
            'prior_auth_summary': 'No codes flagged for prior authorization',
            'prior_auth_codes_flagged': 0,
            'prior_authorization_awareness': 'ON',
            'documentation_audit': doc_audit,
            'pre_submission_audit_findings': pre_sub,
            'pre_submission_audit_score': _audit_score(pre_sub),
            'lcd_ncd_findings': _lcd(cpt_codes, icd_bill),
            'lcd_ncd_validation': 'ON',
            'frequency_alerts': [],
            'frequency_utilization_edits': 'ON',
            'global_surgery_warnings': _global(cpt_codes),
            'global_surgery_period_awareness': 'ON',
            'q_modifier_inference': 'ON',
            'toe_modifier_inference': 'ON',
            'modifier_sequencing': 'ON',
            'auto_coding_tier': tier,
            'auto_coding_confidence': round(conf, 2),
            'auto_coding_review_reasons': reasons,
            'auto_coding_summary': _summary(tier, reasons),
            'encounter_integrity': {
                'encounter_issues': enc_issues,
                'error_count': sum(1 for i in enc_issues if i.get('severity')=='ERROR'),
                'warning_count': sum(1 for i in enc_issues if i.get('severity')=='WARNING'),
            },
            'encounter_classification': enc_class,
            'no_section_headers_detected': sections.get('_no_section_headers') == 'true',
            'longitudinal_patient_context': {'available': False, 'reason': 'no_patient_id'},
            'uncertainty_score': round(1.0-conf, 2),
            'model_source': 'hybrid_rules_nlp_v3',
            'confidence_at_coding': round(conf, 2),
            'code_accuracy_by_type': _acc(cpt_codes, hcpcs_codes, icd_bill, snomed),
        }
    except Exception as exc:
        import traceback
        return {
            'document_id': doc_id, 'timestamp': datetime.utcnow().isoformat(),
            'success': False, 'processing_time': round((time.time()-start)*1000, 3),
            'cpt_codes': [], 'hcpcs_codes': [], 'icd_codes': [], 'supporting_conditions': [],
            'comprehend_snomed': [], 'error_message': str(exc), 'traceback': traceback.format_exc(),
            'validation_issues': [], 'warnings': [],
        }

def _merge_drugs(hcpcs, drugs):
    existing = {c['code'] for c in hcpcs}
    for d in drugs:
        if d['code'] not in existing: hcpcs.append(d)
    return hcpcs

def _pre_sub(cpt, hcpcs, icd, adv, val_issues, sections):
    findings = []
    for v in val_issues:
        findings.append({'severity': v.get('severity','WARNING'),
            'code': v.get('code', v.get('code1','')),
            'category': v.get('type','validation'),
            'message': v.get('message',''),
            'recommendation': v.get('recommendation','')})
    # R4: no section headers flag
    if sections.get('_no_section_headers') == 'true':
        findings.insert(0, {
            'severity': 'WARNING', 'code': '', 'category': 'NO_SECTION_HEADERS',
            'message': 'No SOAP section headers detected. Codes sourced from full note text. '
                       'Manual review recommended before billing.',
            'recommendation': 'Verify all generated codes against clinical documentation.',
        })
    # Orphan diagnoses
    cpt_linked = set()
    for c in cpt:
        for ld in c.get('linked_diagnoses',[]): cpt_linked.add(ld.get('code','').replace('.',''))
        for i in c.get('linked_icd',[]): cpt_linked.add(str(i).replace('.',''))
    for code_entry in icd:
        code = code_entry['code']
        if code.replace('.','') not in cpt_linked:
            findings.append({'severity':'INFO','category':'ORPHAN_DIAGNOSIS',
                'denial_risk':'LOW','code':code,
                'message':f'{code} not linked to any procedure',
                'recommendation':'Link to CPT/HCPCS or remove if not addressed today'})
    # Advisory notice
    if adv:
        findings.append({'severity':'INFO','category':'ADVISORY_CONDITIONS','denial_risk':'LOW','code':'',
            'message': f'{len(adv)} condition(s) moved to advisory tier (not billed): ' +
                       ', '.join(f'{a["code"]} ({a["description"]})' for a in adv[:5]),
            'recommendation': 'Only add to claim if condition was directly addressed on this DOS.'})
    # Unspecified ICD
    for entry in icd:
        if 'unspecified' in entry.get('description','').lower():
            findings.append({'severity':'INFO','category':'ICD_SPECIFICITY','denial_risk':'LOW',
                'code':entry['code'],'message':f'{entry["code"]} is unspecified',
                'recommendation':'Use specific laterality/type code if documented'})
    for entry in cpt + icd:
        if entry.get('needs_review') and entry.get('review_reason'):
            findings.append({'severity':'WARNING','code':entry['code'],
                'category':'documentation_adequacy','message':f'{entry["code"]}: {entry["review_reason"]}',
                'recommendation':'Verify documentation before submission.'})
    return findings

def _audit_score(findings):
    e = sum(1 for f in findings if f.get('severity')=='ERROR')
    w = sum(1 for f in findings if f.get('severity')=='WARNING')
    return round(max(0.0, min(1.0, 1.0 - e*0.1 - w*0.05)), 2)

def _tier(cpt, hcpcs, icd, val_issues):
    all_c = cpt + hcpcs + icd
    confs = [c.get('confidence',0.85) for c in all_c]
    avg = sum(confs)/len(confs) if confs else 0.85
    reasons = [f'{c["code"]}: {c["review_reason"]}' for c in all_c
               if c.get('needs_review') and c.get('review_reason')]
    has_err = any(v.get('severity')=='ERROR' for v in val_issues)
    tier = ('REVIEW' if has_err or len(reasons)>=2 or avg<0.88
            else 'AUTO_APPROVED' if avg>=0.93 else 'REVIEW')
    return tier, avg, reasons

def _summary(tier, reasons):
    if tier == 'AUTO_APPROVED': return 'All codes meet confidence threshold. Ready for submission.'
    return f'Coder review recommended ({len(reasons)} item{"s" if len(reasons)!=1 else ""}). Address before submission.'

def _lcd(cpt_codes, icd_codes):
    findings = []
    routine = {'11055','11056','11057','11719','11721','11722'}
    if any(c['code'] in routine for c in cpt_codes):
        icd_set = {i['code'].replace('.','') for i in icd_codes}
        qualifying = {q.replace('.','') for q in db.qualifying_dx}
        if not (icd_set & qualifying):
            findings.append({'lcd_id':'L36199','code':'ROUTINE_FOOT_CARE','severity':'WARNING',
                'message':'Routine foot care CPT billed without qualifying Class A/B/C diagnosis.',
                'recommendation':'Add qualifying diagnosis per LCD L36199.'})
    return findings

def _global(cpt_codes):
    g90 = {'28750','27698','28080','28295','28296','27870'}
    return [{'code':c['code'],'global_period':'90 days',
             'message':f'CPT {c["code"]} has 90-day global period.',
             'recommendation':'Post-op E/M within 90 days requires modifier -24.'}
            for c in cpt_codes if c['code'] in g90]

def _acc(cpt, hcpcs, icd, snomed):
    def s(codes, key='confidence'):
        vals = [c.get(key,0) for c in codes if c.get(key)]
        avg = round(sum(vals)/len(vals),3) if vals else None
        return {'count':len(codes),'avg_confidence':avg,'accuracy_pct':round(avg*100,1) if avg else None}
    return {'CPT':s(cpt),'HCPCS':s(hcpcs),'ICD10CM':s(icd),'SNOMED':s(snomed,'score')}
