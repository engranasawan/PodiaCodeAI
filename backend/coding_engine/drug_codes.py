"""
Drug J-Code Extractor — Fix #7 with R2 dose-unit extension.
J3301 (triamcinolone), J1020 (methylprednisolone), J1100 (dexamethasone)
all get per-unit dose calculations, not flat 1 unit.
"""
import re
from typing import Dict, List

ADMIN_VERB = re.compile(
    r'\b(?:administered|injected|given|infused|delivered|instilled)\b',
    re.IGNORECASE,
)
BILATERAL = re.compile(r'\bbilateral(?:ly)?\b|\bboth\s+(?:sides?|feet|foot|ankles?|interspaces?)\b', re.IGNORECASE)

# (regex, j_code, desc, dose_mg_per_unit, dose_pattern)
# dose_pattern extracts documented mg from the note
DRUG_MAP = [
    # betamethasone: J0702 per 3mg
    (r'betamethasone(?:\s+\d+\s*mg)?', 'J0702',
     'Injection betamethasone acetate/sodium phosphate, per 3mg',
     3, re.compile(r'betamethasone\s+(\d+)\s*mg', re.IGNORECASE)),
    # triamcinolone: J3301 per 10mg (R2 fix)
    (r'triamcinolone(?:\s+\d+\s*mg)?', 'J3301',
     'Injection triamcinolone acetonide, per 10mg',
     10, re.compile(r'triamcinolone\s+(\d+)\s*mg', re.IGNORECASE)),
    # methylprednisolone: J1020 per 20mg (R2 fix)
    (r'methylprednisolone(?:\s+\d+\s*mg)?', 'J1020',
     'Injection methylprednisolone acetate, 20mg',
     20, re.compile(r'methylprednisolone\s+(\d+)\s*mg', re.IGNORECASE)),
    # dexamethasone: J1100 per 1mg (R2 fix)
    (r'dexamethasone(?:\s+\d+\s*mg)?', 'J1100',
     'Injection dexamethasone sodium phosphate, 1mg',
     1, re.compile(r'dexamethasone\s+(\d+)\s*mg', re.IGNORECASE)),
    # hydrocortisone: J1720 per 25mg
    (r'hydrocortisone(?:\s+\d+\s*mg)?', 'J1720',
     'Injection hydrocortisone sodium acetate, 25mg',
     25, re.compile(r'hydrocortisone\s+(\d+)\s*mg', re.IGNORECASE)),
    # bupivacaine: J3490 flat (no standard per-unit dose)
    (r'bupivacaine(?:\s+\d*\.?\d+\s*%)?', 'J3490',
     'Unclassified drugs — bupivacaine', 0, None),
    # lidocaine: J2001 per 10mg
    (r'lidocaine(?:\s+\d*\.?\d+\s*%)?', 'J2001',
     'Injection lidocaine HCl, 10mg', 10,
     re.compile(r'lidocaine\s+(\d+)\s*mg', re.IGNORECASE)),
    # hyaluronic acid
    (r'hyaluronic\s+acid|sodium\s+hyaluronate', 'J7321',
     'Injection hyaluronan, per dose', 0, None),
]

def extract_drug_codes(sections: Dict[str, str], icd_codes: List[dict]) -> List[dict]:
    # Use PLAN section if available, otherwise fall back to full text
    plan = sections.get('PLAN', '').strip() or sections.get('FULL_TEXT', '')
    results = []
    seen = set()
    primary_icd = icd_codes[0] if icd_codes else None
    linked_dx = [{'code': primary_icd['code'], 'description': primary_icd['description'],
                  'linkage_type': 'primary_diagnosis'}] if primary_icd else []

    for pat, j_code, desc, dose_per_unit, dose_re in DRUG_MAP:
        if j_code in seen: continue
        match = re.search(pat, plan, re.IGNORECASE)
        if not match: continue

        # Admin verb must appear within 200 chars
        ctx_start = max(0, match.start()-150); ctx_end = min(len(plan), match.end()+150)
        ctx = plan[ctx_start:ctx_end]
        if not ADMIN_VERB.search(ctx): continue

        # Calculate units
        units = 1
        if dose_per_unit > 0 and dose_re:
            dm = dose_re.search(plan)
            if dm:
                try:
                    mg = int(dm.group(1))
                    units = max(1, round(mg / dose_per_unit))
                except: pass
        # Bilateral doubles units
        if BILATERAL.search(ctx) and dose_per_unit > 0:
            units *= 2

        results.append({
            'code': j_code, 'description': desc,
            'confidence': 0.92, 'source': 'drug_code_extraction',
            'evidence_spans': [match.group(0)[:100]],
            'quantity': units, 'units': units,
            'modifiers': [], 'needs_review': False, 'review_reason': None,
            'linked_diagnoses': linked_dx, 'medical_necessity': True,
            'validation_status': 'validated',
        })
        seen.add(j_code)
    return results
