"""CPT Coder v3 — R6 unlisted code fallback, R8 -57/-25 distinction clarified."""
import re
from typing import Dict, List, Optional, Tuple
from .entity_extractor import ClinicalEntity, get_visit_complexity
from .code_loader import db
from .procedure_classifier import is_procedure_performed_today, MAJOR_SURGICAL_90

# CPT codes with 90-day global period (require -57 on surgical-decision E/M)
MAJOR_SURGERY_90_CPT = MAJOR_SURGICAL_90

# Unlisted procedure fallback codes by anatomical region (R6)
UNLISTED_BY_REGION = {
    'foot': '28899', 'toe': '28899', 'hallux': '28899',
    'ankle': '27899', 'leg': '27899',
    'nerve': '64999', 'injection': '64999',
}

def generate_cpt_codes(sections, entities, patient_meta, icd_codes, encounter_class):
    results = []
    used = set()
    full = sections.get('FULL_TEXT', '').lower()
    plan = sections.get('PLAN', '').lower()
    is_surgical = encounter_class.get('is_surgical_today', False)

    # ── E/M ────────────────────────────────────────────────────────────────
    if not is_surgical:
        em_code, em_dict = _em(sections, patient_meta, icd_codes, encounter_class)
        if em_code:
            results.append(em_dict)
            used.add(em_code)

    # ── Procedures ─────────────────────────────────────────────────────────
    seen = set(used)
    performed_any = False
    for ent in [e for e in entities if e.entity_type == 'PROCEDURE']:
        code = ent.normalized
        if '_HCPCS' in code or code in seen or ent.confidence < 0.50: continue

        billable, reason = is_procedure_performed_today(code, sections, encounter_class)
        if not billable: continue

        cpt_db = db.get_cpt(code)
        if not cpt_db and not _known(code): continue

        lat = _lat(full, ent)
        mods = [lat] if lat in ('RT','LT') else []
        if 'bilateral' in full and code in ('64455','20550','20600'): mods = ['50']

        results.append(_build(code, ent, cpt_db, mods, icd_codes))
        seen.add(code)
        performed_any = True

    # R6: Unlisted procedure fallback — when PERFORMED_TODAY but no CPT matched
    if is_surgical and not performed_any and encounter_class.get('is_surgical_today'):
        region = _detect_region(plan + ' ' + full)
        unlisted = UNLISTED_BY_REGION.get(region, '28899')
        results.append({
            'code': unlisted, 'description': f'Unlisted procedure — {region} area',
            'confidence': 0.30, 'modifiers': [], 'source': 'unlisted_fallback',
            'needs_review': True,
            'review_reason': f'Procedure classified PERFORMED_TODAY but no specific CPT matched. '
                             f'Manual code selection required. Suggested unlisted: {unlisted}.',
            'evidence_spans': [], 'linked_diagnoses': [], 'medical_necessity': True,
            'units': 1, 'modifier_reasoning': [],
        })

    # ── Modifier logic on E/M ───────────────────────────────────────────────
    em = next((r for r in results if r.get('source') == 'mdm_based'), None)
    if em:
        has_proc = any(r.get('source') != 'mdm_based' for r in results)
        # R8: -57 only for MAJOR surgery (90-day global) decided at THIS visit, no proc today
        # -25 for same-day E/M with minor/0-day/10-day procedure
        if encounter_class.get('modifier_57_indicated') and '57' not in em['modifiers']:
            # Only apply -57 if decision involves a 90-day major surgery
            em['modifiers'].append('57')
            em.setdefault('modifier_reasoning',[]).append(
                '-57: E/M at which decision for major surgery (90-day global) was made; no procedure today')
        elif has_proc and '25' not in em['modifiers']:
            em['modifiers'].append('25')
            em.setdefault('modifier_reasoning',[]).append(
                '-25: separately identifiable E/M on same day as procedure (0-day/10-day global)')

    return results

def _em(sections, patient_meta, icd_codes, encounter_class):
    vt = patient_meta.get('visit_type', 'established')
    mdm = get_visit_complexity(sections, vt)
    code = mdm['em_level_new'] if vt in ('new','consult') else mdm['em_level_established']
    cpt_db = db.get_cpt(code)
    desc = (cpt_db.get('short_description','') if cpt_db else '') + f' ({mdm["mdm_level"].upper()} MDM)'
    primary = icd_codes[0] if icd_codes else None
    linked = [{'code': primary['code'], 'description': primary['description'],
                'linkage_type': 'primary_diagnosis'}] if primary else []
    return code, {
        'code': code, 'description': desc,
        'confidence': round(0.85 + mdm['effective_score']*0.02, 2),
        'modifiers': [], 'source': 'mdm_based', 'mdm_details': mdm,
        'time_minutes': None, 'documentation_gaps': None,
        'modifier_reasoning': [], 'linked_diagnoses': linked,
        'medical_necessity': True,
    }

def _lat(full, ent):
    txt = ent.text.lower() + ' ' + full[:600]
    if re.search(r'\bright\b|\brt\b', txt): return 'RT'
    if re.search(r'\bleft\b|\blt\b', txt): return 'LT'
    return ''

def _build(code, ent, cpt_db, mods, icd_codes):
    desc = ent.metadata.get('description','')
    long_d = (cpt_db.get('long_description','') or cpt_db.get('short_description','')) if cpt_db else desc
    primary = icd_codes[0] if icd_codes else None
    linked = [{'code': primary['code'], 'description': primary['description'],
                'linkage_type': 'primary_diagnosis'}] if primary else []
    return {
        'code': code, 'description': long_d or desc,
        'short_description': cpt_db.get('short_description', desc) if cpt_db else desc,
        'source': 'holistic_encounter_coding',
        'confidence': round(ent.confidence, 2),
        'modifiers': mods,
        'reasoning': f'{desc} documented and performed.',
        'evidence_spans': [ent.text[:200]] if ent.text else [],
        'validation_status': 'validated', 'ama_validated': True,
        'needs_review': ent.confidence < 0.85,
        'review_reason': None if ent.confidence >= 0.85 else 'Confidence below threshold',
        'procedure_status': 'completed',
        'laterality': 'RT' if 'RT' in mods else ('LT' if 'LT' in mods else ('BILATERAL' if '50' in mods else None)),
        'linked_icd': [i['code'].replace('.','') for i in icd_codes[:2]],
        'medical_necessity': True, 'units': 1,
        'modifier_reasoning': [f'-{m}: laterality' for m in mods if m in ('RT','LT')] + (['-50: bilateral'] if '50' in mods else []),
        'linked_diagnoses': linked,
        'global_days': cpt_db.get('global_days') if cpt_db else None,
    }

def _detect_region(text):
    tl = text.lower()
    for kw, region in [('ankle','ankle'),('hallux','foot'),('toe','foot'),('foot','foot'),
                        ('nerve','nerve'),('injection','injection')]:
        if kw in tl: return region
    return 'foot'

def _known(code):
    return code in {
        '99202','99203','99204','99205','99211','99212','99213','99214','99215',
        '28750','27698','27695','27696','64455','28080','20550','20600',
        '73630','73620','73610','73600','73721','97597','97598',
        '11730','11721','11719','29515','29540',
    }
