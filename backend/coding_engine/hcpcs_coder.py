"""HCPCS Coder v3 — dispensing gate, orthotic suppression, surgical guard."""
import re
from typing import Dict, List, Set
from .entity_extractor import ClinicalEntity
from .code_loader import db

DISPENSING = re.compile(
    r'\b(?:applied|delivered|fitted|dispensed|issued|administered|molded|fabricated|given\s+(?:to|the|patient))\b',
    re.IGNORECASE)
RECOMMENDATION = re.compile(
    r'\b(?:until\s+(?:or|surgery)|for\s+sport\s+until|recommended|order(?:ed)?\s+from|'
    r'prescription\s+written|will\s+be\s+(?:provided|dispensed|applied)|until\s+or\b)\b',
    re.IGNORECASE)

HCPCS_MAP = [
    (r'custom.*?molded.*?foot.*?orthoti[cs]|l3000|delivered.*?fitted.*?orthot', 'L3000',
     'Foot insert custom molded UCB type', 0.97, True),
    (r'prefabricat.*?orthoti[cs]|off.the.shelf.*?insert', 'L3020',
     'Foot insert prefabricated', 0.82, True),
    (r'heel\s+(?:lift|pad)', 'L3485', 'Heel pad', 0.80, True),
    (r'cam\s+walker\s+(?:applied|placed|fitted|given)|applied.*?cam\s+walker', 'L4361',
     'Walking boot CAM walker', 0.92, True),
    (r'ankle\s+brace\s+(?:applied|fitted|dispensed|given)|applied.*?ankle\s+brace', 'L1906',
     'AFO prefabricated', 0.85, True),
    (r"morton.?s?\s+extension", 'L3395', 'Full-foot extension', 0.80, False),
]

REQUIRES_DISPENSING: Set[str] = {'L3000','L3010','L3020','L3040','L3395','L3300','L3485','L4361','L4360','L1906','L1970'}
SECONDARY_ORTHOTICS: Set[str] = {'L3010','L3020','L3040','L3485'}
SURGICAL_ALLOWED: Set[str] = {'L4361','L4360','L1970'}

def generate_hcpcs_codes(sections, entities, patient_meta, icd_codes, encounter_class):
    results = []
    seen: Set[str] = set()
    full = sections.get('FULL_TEXT','').lower()
    plan = sections.get('PLAN','')
    plan_lower = plan.lower()
    is_surgical = encounter_class.get('is_surgical_today', False)
    l3000_explicit = bool(re.search(r'\bl3000\b|custom.molded.*orthot|UCB\s+type', plan, re.IGNORECASE))

    # Entity path
    for ent in entities:
        if ent.entity_type != 'PROCEDURE' or '_HCPCS' not in ent.normalized: continue
        code = ent.normalized.replace('_HCPCS','')
        if code in seen: continue
        if l3000_explicit and code in SECONDARY_ORTHOTICS: continue
        if is_surgical and code not in SURGICAL_ALLOWED: continue
        if code in REQUIRES_DISPENSING and not _dispensed(plan, plan_lower): continue
        hcpcs_e = db.get_hcpcs(code)
        desc = hcpcs_e['description'] if hcpcs_e else ent.metadata.get('description', code)
        qty = _qty(plan_lower, code)
        results.append(_build(code, desc, ent.confidence, 'entity_extraction', ent.text, icd_codes, qty))
        seen.add(code)

    # Pattern path
    for pat, code, desc, conf, needs_d in HCPCS_MAP:
        if code in seen: continue
        if l3000_explicit and code in SECONDARY_ORTHOTICS: continue
        if is_surgical and code not in SURGICAL_ALLOWED: continue
        m = re.search(pat, full, re.IGNORECASE)
        if not m: continue
        ctx = full[max(0,m.start()-200):m.end()+200]
        if needs_d and not _dispensed(plan, ctx): continue
        hcpcs_e = db.get_hcpcs(code)
        fd = hcpcs_e['description'] if hcpcs_e else desc
        results.append(_build(code, fd, round(conf,2), 'hcpcs_pattern', m.group(0), icd_codes, _qty(full, code)))
        seen.add(code)

    return results

def _dispensed(plan, ctx=''):
    check = ctx if ctx else plan
    if RECOMMENDATION.search(check) or RECOMMENDATION.search(plan): return False
    return bool(DISPENSING.search(plan))

def _qty(text, code):
    if code in ('L3000','L3010','L3020') and re.search(r'bilateral|both\s+feet', text, re.IGNORECASE): return 2
    return 1

def _build(code, desc, conf, src, ev, icd_codes, qty=1):
    primary = icd_codes[0] if icd_codes else None
    linked = [{'code': primary['code'], 'description': primary['description'],
                'linkage_type': 'primary_diagnosis'}] if primary else []
    return {
        'code': code, 'description': desc, 'confidence': round(conf,2),
        'source': src, 'evidence_spans': [ev[:200]] if ev else [],
        'quantity': qty, 'units': qty, 'modifiers': [],
        'needs_review': conf < 0.85,
        'review_reason': None if conf >= 0.85 else 'Verify medical necessity',
        'linked_diagnoses': linked, 'medical_necessity': True, 'validation_status': 'validated',
    }
