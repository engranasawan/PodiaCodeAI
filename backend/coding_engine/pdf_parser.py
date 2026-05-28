"""PDF/Text Parser — section detection with all v2 fixes + R4 fallback for structureless notes."""
import re
from typing import Dict, List, Optional
import pdfplumber, io

SECTION_PATTERNS = {
    'CHIEF_COMPLAINT': [r'CHIEF\s*COMPLAINT', r'\bCC\s*:', r'REASON\s+FOR\s+VISIT'],
    'HPI': [r'HISTORY\s+OF\s+PRESENT\s+ILLNESS', r'\bH\.?P\.?I\.?\b'],
    'PMH': [r'PAST\s+(?:MEDICAL\s+)?HISTORY', r'\bPMH\b', r'MEDICATIONS?\s*:', r'ALLERGIES?\s*:'],
    'EXAM': [r'PHYSICAL\s+EXAM(?:INATION)?', r'\bOBJECTIVE\b'],
    'IMAGING': [r'IMAGING(?:\s*/\s*DIAGNOSTICS)?', r'DIAGNOSTICS?\s*:', r'RADIOLOGY'],
    'ASSESSMENT': [r'ASSESSMENT(?:\s*/\s*DIAGNOS(?:IS|ES))?', r'DIAGNOS(?:IS|ES)\s*:', r'IMPRESSION\s*:', r'A/P\s*:'],
    # \bPLAN\b word boundary prevents 'planus' false match (Fix #4)
    'PLAN': [r'\bPLAN\b(?:\s*/\s*TREATMENT)?', r'TREATMENT\s+PLAN', r'PROCEDURE(?:S?\s+PERFORMED)?'],
}
COMPILED = {s: [re.compile(p, re.IGNORECASE) for p in pats] for s, pats in SECTION_PATTERNS.items()}

def _clean(text):
    text = re.sub(r'\(cid:\d+\)', '•', text)
    return re.sub(r'[ \t]+', ' ', text)

def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    parts = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            t = page.extract_text(x_tolerance=2, y_tolerance=2)
            if t: parts.append(t)
    return '\n'.join(parts)

def parse_note(text: str) -> Dict[str, str]:
    text = _clean(text)
    sections: Dict[str, str] = {'FULL_TEXT': text}
    lines = text.split('\n')

    boundaries: List[tuple] = []
    for i, line in enumerate(lines):
        ls = line.strip()
        if not ls or i < 10: continue  # skip header block
        for sec, patterns in COMPILED.items():
            for pat in patterns:
                if (pat.match(ls) or pat.search(ls[:45])) and len(ls) < 100:
                    boundaries.append((i, sec)); break
            else: continue
            break

    # dedupe adjacent same-section
    deduped = []
    seen = set()
    for idx, sec in boundaries:
        if sec not in seen:
            deduped.append((idx, sec)); seen.add(sec)

    for k, (line_idx, sec_name) in enumerate(deduped):
        start = line_idx + 1
        end = deduped[k+1][0] if k+1 < len(deduped) else len(lines)
        section_text = '\n'.join(lines[start:end]).strip()
        if sec_name not in sections:
            sections[sec_name] = section_text

    # R4: Fallback for structureless notes (no SOAP headers detected)
    if 'ASSESSMENT' not in sections:
        sections['ASSESSMENT'] = text
        sections['_no_section_headers'] = 'true'

    sections['PATIENT_INFO'] = '\n'.join(l.strip() for l in lines[:20] if l.strip())
    return sections

def extract_patient_meta(text: str) -> dict:
    meta = {k: None for k in ['patient_name','dob','provider','npi','date_of_service','mrn','insurance','visit_type']}
    for pat, key in [
        (r'Patient\s+Name[:\s]+([A-Z][a-z]+(?:\s+[A-Z]\.?\s+)?[A-Z][a-z]+)', 'patient_name'),
        (r'(?:Date\s+of\s+Birth|D\.?O\.?B)[:\s]+(\d{1,2}/\d{1,2}/\d{4})', 'dob'),
        (r'Provider[:\s]+([A-Z][a-z]+.*?(?:DPM|MD|DO|NP|PA).*?)(?:\n|$)', 'provider'),
        (r'NPI[:\s]+(\d{10})', 'npi'),
        (r'Date\s+of\s+Service[:\s]+([A-Z][a-z]+ \d{1,2},?\s+\d{4}|\d{1,2}/\d{1,2}/\d{4})', 'date_of_service'),
        (r'MRN[:\s]+([A-Z0-9-]+)', 'mrn'),
        (r'Insurance[:\s]+([^\n|]+)', 'insurance'),
    ]:
        m = re.search(pat, text)
        if m: meta[key] = m.group(1).strip()

    if re.search(r'SURGICAL\s+PROCEDURE', text, re.IGNORECASE): meta['visit_type'] = 'surgical'
    elif re.search(r'NEW\s+PATIENT', text, re.IGNORECASE): meta['visit_type'] = 'new'
    elif re.search(r'ESTABLISHED\s+PATIENT', text, re.IGNORECASE): meta['visit_type'] = 'established'
    elif re.search(r'CONSULT', text, re.IGNORECASE): meta['visit_type'] = 'consult'
    else: meta['visit_type'] = 'established'
    return meta

def extract_laterality(text: str) -> Optional[str]:
    tl = text.lower()
    if re.search(r'\bbilateral\b|\bboth\s+feet\b|\bboth\s+ankles\b', tl): return 'BILATERAL'
    left = len(re.findall(r'\bleft\b|\blt\b', tl))
    right = len(re.findall(r'\bright\b|\brt\b', tl))
    if left > right: return 'LEFT'
    if right > left: return 'RIGHT'
    return None
