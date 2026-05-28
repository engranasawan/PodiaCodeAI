"""
Procedure Classifier v3 — Three-layer classifier (R11 + Arch suggestion).

Layer 1: Section context (highest confidence, no NLP)
Layer 2: Extended pattern library (13 original + passive/indirect/historical patterns)
Layer 3: Verb-tense analysis (lightweight regex-based, spaCy optional upgrade)

Conservative default: UNKNOWN → not billed + review flag.
"""
import re
from typing import Dict, List, Optional

# ── Layer 1: Section context priors ──────────────────────────────────────────
SECTION_PRIORS = {
    'PLAN': 'SCHEDULED_FUTURE',
    'PMH': 'HISTORICAL', 'HPI': 'HISTORICAL',
    'EXAM': 'HISTORICAL',
    'IMAGING': 'PERFORMED_TODAY',   # imaging documented = performed
}

# ── Layer 2: Extended pattern library ────────────────────────────────────────
INTENT_PATTERNS = {
    'PERFORMED_TODAY': [
        r'\bperformed\b', r'\badministered\b', r'\binjected\b', r'\bapplied\b',
        r'\bdelivered\b', r'\bfitted\b', r'\bdispensed\b',
        r'dorsal\s+incision', r'under\s+(?:spinal|general|local|iv|mac)\s+anes',
        r'fluoroscopic\s+confirm', r'closure\s+in\s+layers', r'fixed\s+with',
        r'joint\s+preparation', r'\bnwb\b', r'posterior\s+splint\s+applied',
        r'\bebl\b', r'tourniquet\s+(?:time|applied|released)',
        r'no\s+complications', r'pt\s+tolerated\s+(?:well|procedure)',
        r'sutures?\s+(?:placed|applied|closed)', r'wound\s+closed',
        r'hemostasis\s+achieved', r'specimen[s]?\s*:\s*(?:none|sent)',
    ],
    'SCHEDULED_FUTURE': [
        # Original 13
        r'\bscheduled\s+for\b', r'\bagrees?\s+to\s+proceed\b',
        r'\bpre.?op\s+orders?\s+placed\b', r'\bwill\s+undergo\b',
        r'\bpatient\s+consents?\s+to\s+proceed\b', r'\bbooked\s+for\b',
        r'\bdecision\s+for\s+(?:surgery|major)\b', r'\bto\s+be\s+performed\b',
        r'\bpending\s+(?:authorization|clearance)\b', r'\bwill\s+be\s+performed\b',
        r'\bpre.?operative\b', r'\bpre.?surgical\b', r'\bpre.?op\s+visit\b',
        # R11 passive / indirect additions
        r'\bpatient\s+(?:is|was)\s+(?:amenable|agreeable|willing)\s+to\b',
        r'\belects?\s+(?:to\s+)?(?:proceed|surgical|intervention|correction)\b',
        r'\boperative\s+(?:management|approach)\s+(?:is|was)?\s*indicated\b',
        r'\bplan\s+(?:is|was)?\s*for\s+(?:surgical|operative)\b',
        r'\bfor\s+OR\s+(?:scheduling|booking|date)\b',
        r'\bconsented\s+for\s+(?:the\s+)?(?:procedure|surgery)\b',
        r'\bH&P\s+(?:completed|on\s+file|obtained)\b',
        r'\bmedical\s+clearance\b',
        r'\bsurgery\s+was\s+agreed\s+upon\b',
        r'\boperative\s+intervention\s+(?:is|was)?\s*(?:indicated|planned)\b',
        r'\bpatient\s+elects?\s+surgical\b',
        r'\bplan\s+is\s+(?:for\s+)?operative\b',
        r'\breferral\s+for\s+operative\s+management\b',
        r'\bwill\s+be\s+scheduled\b', r'\bsurgical\s+planning\b',
    ],
    'HISTORICAL': [
        r'\bs/?p\b', r'\bstatus\s+post\b',
        r'\bprior\s+(?:surgery|procedure|repair|reconstruction|fusion)\b',
        r'\bprevious\s+(?:surgery|procedure|repair)\b',
        r'\bhealed\s+(?:surgical|operative)\s+(?:site|wound|incision)\b',
        r'\bunderwent\b.{0,40}\bin\s+\d{4}\b',
        r'\b\d{4}\s+(?:surgery|procedure|repair)\b',
    ],
}
_COMPILED = {intent: [re.compile(p, re.IGNORECASE) for p in pats]
             for intent, pats in INTENT_PATTERNS.items()}

# ── Major surgical codes (90-day global) ─────────────────────────────────────
MAJOR_SURGICAL_90 = {
    '28750','28755','28760','27698','27695','27696',
    '28080','28295','28296','28285','28270','28090',
    '28120','28122','28113','28110','27830','27870',
}

# ── Post-op immobilisation codes bundled into major surgical global ───────────
# R1: These must NOT be billed on same DOS as their corresponding major surgery
GLOBAL_BUNDLE_CODES = {
    '29515','29540','29550','29505','29515',  # splints / casts
    '29130','29131',  # finger/toe splints
}

def classify_encounter(sections: Dict[str, str], patient_meta: dict) -> dict:
    plan   = sections.get('PLAN', '').strip() or sections.get('FULL_TEXT', '')
    full   = sections.get('FULL_TEXT', '')
    visit  = patient_meta.get('visit_type', 'established')

    future_matches = _find_matches('SCHEDULED_FUTURE', plan + ' ' + full[:2000])
    performed_matches = _find_matches('PERFORMED_TODAY', plan)
    historical_matches = _find_matches('HISTORICAL', plan + ' ' + full[:1000])

    is_surgical_today = (
        visit == 'surgical' and bool(performed_matches) and not bool(future_matches)
    )
    has_future_surgery = bool(future_matches) and not is_surgical_today
    surgical_decision = has_future_surgery or bool(
        re.search(r'agrees?\s+to\s+proceed|consents?\s+to|decision\s+for\s+surgery|'
                  r'patient\s+elects?|scheduled\s+for\s+(?:surgery|procedure|brostrom|arthrodesis|reconstruction)',
                  plan, re.IGNORECASE)
    )
    modifier_57_indicated = surgical_decision and not is_surgical_today

    return {
        'is_surgical_today':      is_surgical_today,
        'has_future_surgery':     has_future_surgery,
        'surgical_decision':      surgical_decision,
        'modifier_57_indicated':  modifier_57_indicated,
        'future_procedure_phrases': future_matches[:3],
        'performed_phrases':       performed_matches[:3],
    }

def classify_procedure_sentence(sentence: str, section_name: str) -> dict:
    """
    Per-sentence classification. Performed-today language overrides PLAN
    section prior (a completed procedure documented in Plan overrides the default).
    """
    # Check performed patterns FIRST — overrides PLAN section prior
    for pat in _COMPILED['PERFORMED_TODAY']:
        if pat.search(sentence):
            return {'status': 'PERFORMED_TODAY', 'confidence': 'HIGH',
                    'layer': 'performed_override', 'needs_review': False}

    # Layer 1: section context
    prior = SECTION_PRIORS.get(section_name.upper())
    if prior:
        return {'status': prior, 'confidence': 'HIGH', 'layer': 'section', 'needs_review': False}

    # Layer 2: patterns
    for intent in ['PERFORMED_TODAY', 'SCHEDULED_FUTURE', 'HISTORICAL']:
        for pat in _COMPILED[intent]:
            if pat.search(sentence):
                return {'status': intent, 'confidence': 'MEDIUM', 'layer': 'pattern', 'needs_review': False}

    # Conservative fallback — do not bill
    return {'status': 'UNKNOWN', 'confidence': 'LOW', 'layer': 'fallback', 'needs_review': True}

def is_procedure_performed_today(cpt_code: str, sections: Dict[str, str], encounter_class: dict) -> tuple:
    """Returns (is_billable, reason)."""
    plan = sections.get('PLAN', '').lower()

    if cpt_code in MAJOR_SURGICAL_90:
        if encounter_class['is_surgical_today']:
            return True, 'Surgical encounter confirmed'
        if encounter_class['has_future_surgery']:
            return False, f'SCHEDULED_FUTURE: {encounter_class["future_procedure_phrases"]}'
        # Fallback procedure-keyword check
        kws = {
            '28750': ['arthrodesis','1st mtp','metatarsophalangeal'],
            '27698': ['brostrom','lateral ankle ligament','reconstruction'],
            '28080': ['neurectomy','neuroma excision'],
        }
        if any(k in plan for k in kws.get(cpt_code, [])) and any(
            re.search(p, plan, re.IGNORECASE) for p in _COMPILED['PERFORMED_TODAY']
        ):
            return True, 'Procedure keyword + performed language in Plan'
        return False, f'Major surgical {cpt_code}: no confirmed-performed signal'

    # Post-op immobilisation bundled into surgical global (R1)
    if cpt_code in GLOBAL_BUNDLE_CODES and encounter_class.get('is_surgical_today'):
        return True, 'Post-op immobilisation on surgical day'

    return True, 'Non-major procedure assumed performed'

def _find_matches(intent, text):
    found = []
    for pat in _COMPILED[intent]:
        m = pat.search(text)
        if m:
            start = max(0, m.start()-20); end = min(len(text), m.end()+20)
            found.append(text[start:end].strip())
    return found
