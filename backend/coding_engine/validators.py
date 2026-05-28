"""
Validators v3 — NCCI/MUE, R1 post-op bundle suppression, R3 ICD-vs-CPT laterality cross-check.
"""
import re
from typing import Dict, List, Tuple
from .entity_extractor import ClinicalEntity, SNOMED_MAP
from .code_loader import db

# R1: Post-op immobilisation codes bundled into 90-day global surgical package
# These must NOT be billed on same DOS as the corresponding major surgery
GLOBAL_BUNDLE_SUPPRESS = {
    '28750': {'29515','29540','29550','99213','99212','99211'},  # MTP arthrodesis bundles splint
    '27698': {'29515','29540','29530'},
    '28080': {'29515'},
}

def generate_snomed_concepts(sections, entities):
    results = []
    seen = set()
    full = sections.get('FULL_TEXT','')
    full_lower = full.lower()
    for ent in [e for e in entities if e.entity_type == 'SNOMED']:
        cid = ent.normalized
        if cid in seen: continue
        results.append({'entity_text': ent.text, 'concept_id': cid,
                        'description': ent.metadata.get('description',''),
                        'score': round(ent.confidence,4), 'source': 'infer_snomedct'})
        seen.add(cid)
    for term, (cid, desc, score) in SNOMED_MAP.items():
        if cid in seen: continue
        if term in full_lower:
            results.append({'entity_text': term, 'concept_id': cid,
                            'description': desc, 'score': round(score,4), 'source': 'infer_snomedct'})
            seen.add(cid)
    results.sort(key=lambda x: -x['score'])
    return results[:20]

def validate_ncci_mue(cpt_codes, hcpcs_codes) -> Tuple[List[dict], List[dict], List[dict]]:
    all_codes = [c['code'] for c in cpt_codes] + [c['code'] for c in hcpcs_codes]
    val_issues, warnings, enc_issues = [], [], []

    # R1: Post-op bundle suppression
    major_billed = {c['code'] for c in cpt_codes if c['code'] in GLOBAL_BUNDLE_SUPPRESS}
    for major in major_billed:
        bundles = GLOBAL_BUNDLE_SUPPRESS[major]
        for c in cpt_codes + hcpcs_codes:
            if c['code'] in bundles:
                val_issues.append({
                    'type': 'GLOBAL_BUNDLE_SUPPRESSION', 'severity': 'ERROR',
                    'code': c['code'], 'major_code': major,
                    'message': f'CPT {c["code"]} is included in the global surgical package for {major} and cannot be billed separately on the same DOS.',
                    'recommendation': f'Remove {c["code"]} from the claim. Post-operative immobilisation is bundled into the {major} procedure.',
                    'modifier_allowed': False,
                })

    # NCCI PTP
    for i, c1 in enumerate(all_codes):
        for j, c2 in enumerate(all_codes):
            if i >= j: continue
            conflict, mod_ok = db.check_ncci(c1, c2)
            if conflict:
                mods = (next((c.get('modifiers',[]) for c in cpt_codes if c['code']==c1), []) +
                        next((c.get('modifiers',[]) for c in cpt_codes if c['code']==c2), []))
                if mod_ok and mods:
                    warnings.append({'type':'NCCI_PTP_MODIFIER_BYPASS','severity':'INFO',
                        'code1':c1,'code2':c2,
                        'message':f'NCCI conflict {c1}+{c2} — modifier present, bypass allowed.',
                        'recommendation':'Verify modifier is clinically appropriate.'})
                else:
                    val_issues.append({'type':'NCCI_PTP_CONFLICT','severity':'ERROR',
                        'code1':c1,'code2':c2,
                        'message':f'NCCI PTP edit: {c1} and {c2} cannot be billed together without modifier.',
                        'recommendation':f'Remove {c2} or add modifier if justified.',
                        'modifier_allowed':mod_ok})

    # MUE
    unit_counts = {}
    for c in cpt_codes + hcpcs_codes:
        unit_counts[c['code']] = unit_counts.get(c['code'],0) + c.get('units',1)
    for code, billed in unit_counts.items():
        limit = db.get_mue(code)
        if limit and billed > limit:
            val_issues.append({'type':'MUE_EXCEEDED','severity':'ERROR',
                'code':code,'billed_units':billed,'mue_limit':limit,
                'message':f'MUE exceeded for {code}: billed {billed} units, limit is {limit}.',
                'recommendation':f'Reduce to ≤{limit} units or split across dates.'})

    # R3: ICD-vs-CPT laterality cross-check
    for cpt in cpt_codes:
        cpt_lat = _cpt_laterality(cpt.get('modifiers',[]))
        if not cpt_lat: continue
        for icd in cpt.get('linked_diagnoses', []):
            icd_lat = _icd_laterality(icd.get('code',''))
            if icd_lat and icd_lat != cpt_lat:
                val_issues.append({
                    'type': 'LATERALITY_MISMATCH', 'severity': 'ERROR',
                    'code': cpt['code'],
                    'message': f'Laterality mismatch: CPT {cpt["code"]} modifier -{cpt_lat} vs ICD {icd["code"]} ({icd_lat}). This is a direct claim rejection trigger.',
                    'recommendation': f'Verify laterality. CPT modifier should match ICD diagnosis side.',
                })

    # Imaging interpretation check
    for c in cpt_codes:
        if c['code'] in {'73630','73610','73620','73600','73721'}:
            enc_issues.append({'type':'IMAGING_NO_INTERPRETATION','severity':'INFO',
                'code':c['code'],
                'message':f'CPT {c["code"]} (imaging) — verify interpretation documented. Add modifier -26 for interpretation-only billing.'})

    return val_issues, warnings, enc_issues

def _cpt_laterality(mods):
    if 'RT' in mods: return 'RIGHT'
    if 'LT' in mods: return 'LEFT'
    return None

def _icd_laterality(code):
    c = code.replace('.','')
    if len(c) >= 5:
        suffix = c[-1]
        if suffix in ('1','A'): return 'RIGHT'
        if suffix in ('2','B'): return 'LEFT'
    return None

def build_documentation_audit(cpt_codes, hcpcs_codes, icd_codes, sections):
    full = sections.get('FULL_TEXT','').lower()
    entries = []
    for c in cpt_codes + hcpcs_codes + icd_codes:
        code = c.get('code','')
        desc = c.get('description','')
        kws = [w for w in re.findall(r'\b[a-zA-Z]{4,}\b', desc.lower())
               if w not in {'with','that','from','this','where','which','when'}][:6]
        found_kws = [k for k in kws if k in full]
        sec = _find_section(desc, sections)
        gaps = []
        if c.get('needs_review') and c.get('review_reason'):
            gaps.append(c['review_reason'])
        support = (
            [f"MDM: {c['mdm_details']['mdm_level']}" + f" ({c['mdm_details']['reasoning']})"]
            if c.get('source') == 'mdm_based' and c.get('mdm_details')
            else [f'Entity: "{e}"' for e in c.get('evidence_spans',[])[:2]]
              + ([f'Section: {sec}'] if sec else [])
              + ([f'Keywords: {", ".join(found_kws[:4])}'] if found_kws else [])
        )
        entries.append({'code':code,'description':desc,'documentation_support':support,
                        'documentation_gaps':gaps,'supported':len(gaps)==0})
    total = len(entries)
    supported = sum(1 for e in entries if e['supported'])
    return {'audit_entries':entries,'total_codes':total,
            'fully_supported':supported,'partially_supported':total-supported,
            'unsupported':0,'codes_with_gaps':total-supported,
            'documentation_score':round(supported/total,2) if total else 1.0}

def _find_section(desc, sections):
    kws = re.findall(r'\b[a-zA-Z]{5,}\b', desc.lower())[:3]
    for sec, txt in sections.items():
        if sec == 'FULL_TEXT': continue
        if any(k in txt.lower() for k in kws): return sec
    return ''
