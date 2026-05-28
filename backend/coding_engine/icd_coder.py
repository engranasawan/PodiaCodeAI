"""
ICD-10-CM Coder v3 — billable/advisory split + R7 ICD hierarchy conflict + R3 laterality prep.
"""
import re
from collections import defaultdict
from typing import Dict, List, Tuple
from .entity_extractor import ClinicalEntity
from .code_loader import db

def generate_icd_codes(sections, entities, patient_meta) -> Tuple[List[dict], List[dict]]:
    """Returns (billable_codes, advisory_codes)."""
    billable, advisory = [], []
    seen_b, seen_a = set(), set()

    diag_ents = [e for e in entities if e.entity_type == 'DIAGNOSIS']
    best = {}
    for ent in diag_ents:
        code = ent.normalized
        if code not in best or ent.confidence > best[code].confidence:
            best[code] = ent

    sec_pri = {'ASSESSMENT': 0, 'CHIEF_COMPLAINT': 1, 'HPI': 2, 'PMH': 3}
    sorted_ents = sorted(best.values(), key=lambda e: (sec_pri.get(e.section, 9), -e.confidence))

    full_text = sections.get('FULL_TEXT', '')

    for ent in sorted_ents:
        code = ent.normalized
        ck = code.replace('.', '')
        if ck in seen_b: continue

        icd_entry = db.get_icd(code)
        desc = icd_entry.get('description', ent.metadata.get('description','')) if icd_entry else ent.metadata.get('description','')

        # PMH/HPI → advisory tier only
        if ent.section in ('PMH', 'HPI'):
            if ck not in seen_a:
                advisory.append({
                    'code': _fmt(code), 'description': desc,
                    'confidence': round(ent.confidence * 0.75, 2),
                    'source': 'pmh_hpi_advisory', 'billable_tier': 'advisory',
                    'needs_review': True,
                    'review_reason': f'Found in {ent.section} only — not in Assessment. Do not bill unless addressed on this DOS.',
                })
                seen_a.add(ck)
            continue

        if ent.confidence < 0.70: continue

        billable.append({
            'code': _fmt(code), 'description': desc,
            'confidence': round(ent.confidence, 2),
            'source': 'podiatry_icd_resolver', 'resolver_injected': True,
            's3_validated': icd_entry is not None,
            'resolver_injection_reason': f'{ent.text[:60]} in {ent.section}.',
            'needs_review': ent.confidence < 0.85,
            'review_reason': None if ent.confidence >= 0.85 else f'Verify specificity for {code}',
            'laterality': _lat(full_text, ent),
            'billable_tier': 'billable',
        })
        seen_b.add(ck)

    billable = _dedup_unspecified(billable)
    # R7: ICD subcategory hierarchy conflict detection
    billable = _remove_hierarchy_conflicts(billable)

    # Medication crossref → advisory only
    med_codes = _med_crossref(sections.get('PMH','') + ' ' + full_text, seen_b)
    for mc in med_codes:
        if mc['code'].replace('.','') not in seen_a:
            advisory.append(mc); seen_a.add(mc['code'].replace('.',''))

    return billable, advisory

def _fmt(code):
    code = code.strip()
    return code[:3]+'.'+code[3:] if '.' not in code and len(code)>3 else code

def _lat(full_text, ent):
    desc = ent.metadata.get('description','').lower()
    for k, v in [('right','RIGHT'),('left','LEFT'),('bilateral','BILATERAL'),('both','BILATERAL')]:
        if k in desc: return v
    txt = (ent.text+' '+full_text[:800]).lower()
    l = len(re.findall(r'\bleft\b|\blt\b', txt))
    r = len(re.findall(r'\bright\b|\brt\b', txt))
    if l > r: return 'LEFT'
    if r > l: return 'RIGHT'
    return ''

def _dedup_unspecified(codes):
    families = defaultdict(list)
    for c in codes:
        families[c['code'].replace('.','')[:3]].append(c)
    keep = []
    for _, group in families.items():
        if len(group) == 1: keep.extend(group); continue
        def is_unspec(c):
            return ('unspecified' in c.get('description','').lower() or
                    c['code'].replace('.','').endswith(('0','9'))) and c['confidence'] < 0.96
        specific = [c for c in group if not is_unspec(c)]
        unspec = [c for c in group if is_unspec(c)]
        keep.extend(specific if specific else [max(unspec, key=lambda c: c['confidence'])])
    return keep

def _remove_hierarchy_conflicts(codes):
    """R7: Remove unspecified when more specific code from same subcategory present."""
    families = defaultdict(list)
    for c in codes:
        # subcategory = first 5 chars (e.g. E11.3, M25.3)
        sub = c['code'].replace('.','')[:4]
        families[sub].append(c)
    keep = []
    for _, group in families.items():
        if len(group) == 1: keep.extend(group); continue
        specific = [c for c in group if 'unspecified' not in c.get('description','').lower()]
        unspec = [c for c in group if 'unspecified' in c.get('description','').lower()]
        if specific:
            keep.extend(specific)
            # flag removed unspecified in a review note on the kept code
            if unspec and specific:
                specific[0]['review_reason'] = (
                    (specific[0].get('review_reason') or '') +
                    f' [Hierarchy: {",".join(u["code"] for u in unspec)} removed as superseded]'
                ).strip()
        else:
            keep.extend(group)
    return keep

MED_INFERENCE = [
    (r'\blisinopril\b|\benalapril\b|\blosartan\b|\bamlodipine\b', 'I10', 'Essential hypertension', 0.78),
    (r'\bmetformin\b|\bglipizide\b|\binsulin\b', 'E11.9', 'Type 2 DM', 0.76),
    (r'\batorvastatin\b|\bsimvastatin\b|\brosuvastatin\b', 'E78.5', 'Hyperlipidemia', 0.74),
    (r'\bomeprazole\b|\bpantoprazole\b', 'K21.9', 'GERD', 0.72),
    (r'\bescitalopram\b|\bsertraline\b|\bfluoxetine\b', 'F41.9', 'Anxiety disorder', 0.72),
    (r'\blevothyroxine\b|\bsynthroid\b', 'E03.9', 'Hypothyroidism', 0.74),
    (r'\bapixaban\b|\bwarfarin\b|\brivaroxaban\b', 'I48.91', 'Atrial fibrillation', 0.70),
    (r'\bcetirizine\b|\bloratadine\b', 'J30.9', 'Allergic rhinitis', 0.68),
]

def _med_crossref(text, existing):
    results = []
    tl = text.lower()
    for pat, code, desc, conf in MED_INFERENCE:
        if code.replace('.','') in existing: continue
        m = re.search(pat, tl)
        if m:
            results.append({
                'code': _fmt(code), 'description': desc, 'confidence': round(conf,2),
                'source': 'medication_crossref_advisory', 'billable_tier': 'advisory',
                'needs_review': True,
                'review_reason': f'Inferred from medication {m.group(0).title()} — not in Assessment. Do not bill without clinical justification.',
                'evidence_spans': [f'Medication: {m.group(0).title()}'],
            })
    return results
