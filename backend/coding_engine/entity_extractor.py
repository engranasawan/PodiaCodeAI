"""
Entity Extractor — podiatry-specific NLP entity extraction.
Includes MDM scoring with AMA 2021 three-axis calibration (Fix #5).
Architecture note: embed_index.py provides the embedding-based fallback
for out-of-scope conditions (see embed_index.py for implementation guide).
"""
import re
from typing import Dict, List, Optional
from dataclasses import dataclass, field

@dataclass
class ClinicalEntity:
    text: str; entity_type: str; section: str
    confidence: float = 1.0; normalized: str = ''
    metadata: dict = field(default_factory=dict)

# ── Diagnosis → ICD mapping ────────────────────────────────────────────────────
DIAGNOSIS_MAP = [
    # Hallux
    (r'hallux\s+rigidus.*?right', 'M20.21', 'Hallux rigidus, right foot', 0.95),
    (r'hallux\s+rigidus.*?left', 'M20.22', 'Hallux rigidus, left foot', 0.95),
    (r'hallux\s+rigidus', 'M20.20', 'Hallux rigidus, unspecified foot', 0.85),
    (r'hallux\s+valgus.*?right|bunion.*?right', 'M20.11', 'Hallux valgus, right foot', 0.95),
    (r'hallux\s+valgus.*?left|bunion.*?left', 'M20.12', 'Hallux valgus, left foot', 0.95),
    (r'hallux\s+valgus|bunion', 'M20.10', 'Hallux valgus, unspecified foot', 0.82),
    # Morton's neuroma
    (r"morton.?s?\s+neuroma.*?right|interdigital\s+neuroma.*?right", 'G57.61', "Morton's neuroma, right foot", 0.97),
    (r"morton.?s?\s+neuroma.*?left|interdigital\s+neuroma.*?left", 'G57.62', "Morton's neuroma, left foot", 0.97),
    (r"morton.?s?\s+neuroma.*?bilateral", 'G57.63', "Morton's neuroma, bilateral", 0.95),
    (r"morton.?s?\s+neuroma|interdigital\s+neuroma", 'G57.60', "Morton's neuroma, unspecified", 0.88),
    # Ankle instability / sprains
    (r'(?:chronic\s+)?(?:lateral\s+)?ankle\s+instability.*?left|other\s+instability.*?left.*?ankle', 'M25.372', 'Other instability, left ankle', 0.95),
    (r'(?:chronic\s+)?(?:lateral\s+)?ankle\s+instability.*?right|other\s+instability.*?right.*?ankle', 'M25.371', 'Other instability, right ankle', 0.95),
    (r'(?:chronic\s+)?(?:lateral\s+)?ankle\s+instability', 'M25.370', 'Other instability, unspecified ankle', 0.85),
    (r'sprain.*?unspecified.*?ligament.*?left.*?ankle|sprain.*?left.*?ankle', 'S93.402A', 'Sprain unspecified ligament left ankle, initial', 0.92),
    (r'sprain.*?unspecified.*?ligament.*?right.*?ankle|sprain.*?right.*?ankle', 'S93.401A', 'Sprain unspecified ligament right ankle, initial', 0.92),
    # 1st MTP OA
    (r'primary\s+osteoarthritis.*?right.*?(?:ankle|foot)|(?:grade\s+iv|end.stage).*?arthrit.*?right', 'M19.071', 'Primary osteoarthritis, right ankle and foot', 0.95),
    (r'primary\s+osteoarthritis.*?left.*?(?:ankle|foot)|(?:grade\s+iv|end.stage).*?arthrit.*?left', 'M19.072', 'Primary osteoarthritis, left ankle and foot', 0.95),
    (r'osteoarthritis.*?right.*?(?:ankle|foot)', 'M19.071', 'Primary osteoarthritis, right ankle and foot', 0.88),
    (r'osteoarthritis.*?left.*?(?:ankle|foot)', 'M19.072', 'Primary osteoarthritis, left ankle and foot', 0.88),
    (r'osteoarthritis.*?polyarticular', 'M15.0', 'Primary generalized osteoarthritis', 0.88),
    # Pes planus (M21.4x — R4: word boundary fix ensures this captures)
    (r'pes\s+planus.*?right|flat\s*foot.*?right', 'M21.41', 'Flat foot, right foot', 0.95),
    (r'pes\s+planus.*?left|flat\s*foot.*?left', 'M21.42', 'Flat foot, left foot', 0.95),
    (r'pes\s+planus.*?bilateral|flat\s*foot.*?bilateral', 'M21.43', 'Flat foot, bilateral', 0.93),
    (r'pes\s+planus|flat\s*foot', 'M21.40', 'Flat foot, unspecified', 0.85),
    # Plantar fasciitis
    (r'plantar\s+fasciitis.*?right', 'M72.21', 'Plantar fascia fibromatosis, right', 0.92),
    (r'plantar\s+fasciitis.*?left', 'M72.22', 'Plantar fascia fibromatosis, left', 0.92),
    (r'plantar\s+fasciitis', 'M72.2', 'Plantar fascia fibromatosis', 0.88),
    # Diabetic
    (r'type\s*1\s*diabet.*?foot\s*ulcer', 'E10.621', 'Type 1 DM with foot ulcer', 0.95),
    (r'type\s*2\s*diabet.*?foot\s*ulcer|diabetic\s+foot\s+ulcer', 'E11.621', 'Type 2 DM with foot ulcer', 0.93),
    (r'type\s*1\s*diabet.*?neuropath', 'E10.40', 'Type 1 DM with neuropathy', 0.92),
    (r'type\s*2\s*diabet.*?neuropath|diabetic\s+neuropath.*?type\s*2', 'E11.40', 'Type 2 DM with neuropathy', 0.92),
    (r'type\s*2\s*diabet', 'E11.9', 'Type 2 DM without complications', 0.80),
    (r'type\s*1\s*diabet', 'E10.9', 'Type 1 DM without complications', 0.80),
    # Cardiac / systemic
    (r'atrial\s+fibrillation|a\.?\s*fib', 'I48.91', 'Unspecified atrial fibrillation', 0.90),
    (r'hypertension|htn', 'I10', 'Essential hypertension', 0.85),
    (r'gerd|gastroesophageal\s+reflux', 'K21.9', 'GERD without esophagitis', 0.85),
    (r'anxiety\s+disorder', 'F41.9', 'Anxiety disorder, unspecified', 0.85),
    (r'peripheral\s+vascular\s+disease|pvd', 'I73.9', 'PVD, unspecified', 0.83),
    # Hammertoe / nail
    (r'hammer\s*toe.*?right', 'M20.411', 'Hammertoe, right foot', 0.92),
    (r'hammer\s*toe.*?left', 'M20.412', 'Hammertoe, left foot', 0.92),
    (r'ingrown.*?(?:nail|toenail)', 'L60.0', 'Ingrowing nail', 0.95),
    # Posterior tibial tendon
    (r'posterior\s+tibial\s+tend.*?right|pttd.*?right', 'M76.821', 'Posterior tibial tendinitis, right', 0.92),
    (r'posterior\s+tibial\s+tend.*?left|pttd.*?left', 'M76.822', 'Posterior tibial tendinitis, left', 0.92),
    # Achilles
    (r'achilles\s+tend.*?right', 'M76.61', 'Achilles tendinitis, right', 0.92),
    (r'achilles\s+tend.*?left', 'M76.62', 'Achilles tendinitis, left', 0.92),
    # Wound / ulcer
    (r'chronic\s+ulcer.*?left\s+ankle', 'L97.324', 'Chronic ulcer left ankle with necrosis', 0.82),
    (r'foot\s+ulcer.*?left', 'L97.529', 'Chronic ulcer other part left foot', 0.80),
    (r'foot\s+ulcer.*?right', 'L97.519', 'Chronic ulcer other part right foot', 0.80),
]

# ── Procedure → CPT mapping ────────────────────────────────────────────────────
PROCEDURE_MAP = [
    (r'(?:1st\s+)?mtp.*?arthrodesis|arthrodesis.*?(?:great\s+toe|hallux|1st\s+mtp)|metatarsophalangeal.*?fusion', '28750', 'Arthrodesis, great toe MTP joint', 0.97),
    (r'brostrom.*?gould|lateral\s+ankle\s+ligament\s+reconstruction|ankle\s+ligament\s+reconstruction', '27698', 'Repair secondary disrupted lateral ankle ligament', 0.95),
    (r'injection.*?(?:interdigital|morton|neuroma)|corticosteroid\s+injection.*?neuroma', '64455', 'Injection plantar common digital nerve', 0.95),
    (r'neurectomy.*?(?:morton|interdigital)', '28080', 'Excision interdigital neuroma', 0.95),
    (r'custom.*?orthoti[cs]|l3000|functional\s+foot\s+orthoti[cs].*?custom|delivered.*?fitted.*?orthot', 'L3000_HCPCS', 'Custom molded foot orthosis', 0.97),
    (r'cam\s+walker\s+(?:applied|placed|fitted|given)|applied.*?cam\s+walker|posterior\s+splint\s+applied', 'L4361_HCPCS', 'Walking boot CAM walker', 0.90),
    (r'ankle\s+brace\s+(?:applied|fitted|dispensed|given)|applied.*?ankle\s+brace', 'L1906_HCPCS', 'AFO prefabricated', 0.85),
    (r'debridement.*?(?:first\s+20|20\s+sq|sharp)|sharp\s+debridement', '97597', 'Debridement open wound first 20 sq cm', 0.90),
    (r'avulsion.*?nail|partial\s+nail\s+avulsion', '11730', 'Avulsion nail plate', 0.92),
    (r'x.ray.*?foot.*?(?:3|three|complete|minimum\s+3)|foot\s+x.ray|radiograph.*?foot', '73630', 'X-ray foot 3+ views', 0.90),
    (r'x.ray.*?ankle.*?(?:3|three|complete)|ankle\s+x.ray|stress\s+x.ray.*?ankle', '73610', 'X-ray ankle 3+ views', 0.90),
    (r'mri.*?(?:ankle|foot)', '73721', 'MRI lower extremity without contrast', 0.90),
    (r'posterior\s+splint\s+applied|short\s+leg\s+(?:splint|cast)\s+applied', '29515', 'Application short leg splint', 0.85),
    (r'plantar\s+fascia.*?injection|injection.*?plantar\s+fascia', '20550', 'Injection single tendon sheath/ligament', 0.90),
    (r'corticosteroid.*?injection.*?(?:mtp|joint)|joint.*?injection.*?(?:mtp|toe)', '20600', 'Arthrocentesis small joint', 0.85),
]

# ── SNOMED mapping ──────────────────────────────────────────────────────────────
SNOMED_MAP = {
    'ankle instability': ('57773001','Instability of ankle',0.91),
    'hallux rigidus': ('56976003','Hallux rigidus',0.97),
    'arthrodesis': ('57511006','Arthrodesis procedure',0.95),
    "morton's neuroma": ('95725002',"Morton's metatarsalgia",0.96),
    'morton neuroma': ('95725002',"Morton's metatarsalgia",0.96),
    'pes planus': ('53226007','Pes planus',0.95),
    'flat foot': ('53226007','Pes planus',0.93),
    'plantar fasciitis': ('202882003','Plantar fasciitis',0.96),
    'hallux valgus': ('81344009','Hallux valgus',0.97),
    'bunion': ('81344009','Hallux valgus',0.92),
    'debridement': ('36777000','Debridement of wound',0.95),
    'corticosteroid injection': ('79401000','Injection of corticosteroid',0.94),
    'custom orthotics': ('45141001','Fitting of orthopedic shoe',0.88),
    'atrial fibrillation': ('49436004','Atrial fibrillation',0.97),
    'osteoarthritis': ('396275006','Osteoarthritis',0.95),
    'diabetes mellitus': ('73211009','Diabetes mellitus',0.95),
    'diabetic neuropathy': ('230572002','Diabetic neuropathy',0.95),
    'peripheral vascular disease': ('400047006','PVD',0.93),
    'ankle sprain': ('444798002','Sprain of ankle',0.94),
    'brostrom': ('174720009','Repair lateral ligament of ankle',0.97),
    'brostrom-gould': ('174720009','Repair lateral ligament of ankle',0.97),
    'fluoroscopic guidance': ('44491005','Fluoroscopy',0.92),
    'fluoroscopy': ('44491005','Fluoroscopy',0.92),
    'compression screw': ('68183006','Internal fixation',0.92),
    'locking plate': ('68183006','Internal fixation',0.92),
    'mri': ('113091000','MRI',0.96),
    'x-ray': ('363680008','Radiographic imaging',0.96),
    'betamethasone': ('407122005','Betamethasone',0.93),
    'bupivacaine': ('387372006','Bupivacaine',0.93),
    'apixaban': ('698090000','Apixaban',0.94),
    'left foot': ('239830003','Left foot',0.97),
    'right foot': ('7771000','Right foot',0.97),
    'both feet': ('8580001','Both feet',0.96),
    'left ankle': ('6685009','Left ankle',0.97),
    'right ankle': ('368209003','Right ankle',0.97),
    'posterior tibial': ('7771001','Posterior tibial tendon',0.88),
    'hallux': ('76578001','Hallux',0.95),
    'metatarsophalangeal joint': ('7839004','MTP joint',0.95),
    'osteophyte': ('80400009','Osteophyte',0.94),
    'neuropathy': ('386033004','Neuropathy',0.92),
    'spinal anesthesia': ('57271003','Spinal anesthetic',0.94),
    'dvt prophylaxis': ('413467001','Anticoagulant therapy',0.90),
}

def extract_entities(sections: Dict[str, str]) -> List[ClinicalEntity]:
    entities = []
    full = sections.get('FULL_TEXT', '')
    for sec in ['ASSESSMENT','CHIEF_COMPLAINT','HPI','PMH']:
        txt = sections.get(sec, '')
        if txt: entities.extend(_extract_diagnoses(txt, sec))
    for sec in ['PLAN','IMAGING','EXAM']:
        txt = sections.get(sec, '')
        if txt: entities.extend(_extract_procedures(txt, sec))
    entities.extend(_extract_snomed(full))
    return entities

def _extract_diagnoses(text, section):
    ents = []
    tl = text.lower()
    for pat, code, desc, conf in DIAGNOSIS_MAP:
        if re.search(pat, tl):
            ents.append(ClinicalEntity(
                text=re.search(pat, tl).group(0), entity_type='DIAGNOSIS',
                section=section, confidence=conf, normalized=code,
                metadata={'description': desc, 'icd_code': code}))
    return ents

def _extract_procedures(text, section):
    ents = []
    tl = text.lower()
    for pat, code, desc, conf in PROCEDURE_MAP:
        if re.search(pat, tl):
            ents.append(ClinicalEntity(
                text=re.search(pat, tl).group(0), entity_type='PROCEDURE',
                section=section, confidence=conf, normalized=code,
                metadata={'description': desc, 'cpt_code': code}))
    return ents

def _extract_snomed(text):
    ents = []
    tl = text.lower()
    for term, (cid, desc, score) in SNOMED_MAP.items():
        if term in tl:
            ents.append(ClinicalEntity(text=term, entity_type='SNOMED',
                section='FULL_TEXT', confidence=score, normalized=cid,
                metadata={'concept_id': cid, 'description': desc, 'score': score}))
    return ents

def get_visit_complexity(sections: Dict[str, str], visit_type: str) -> dict:
    """AMA 2021 three-axis MDM. Fix #5: recalibrated moderate/high boundary."""
    full  = sections.get('FULL_TEXT', '').lower()
    plan  = sections.get('PLAN', '').lower()
    asmt  = sections.get('ASSESSMENT', '').lower()

    # Problem axis: count assessment bullets
    bullets = [l.strip() for l in asmt.split('\n')
               if l.strip() and len(l.strip()) > 5
               and not re.match(r'^ASSESSMENT', l.strip(), re.IGNORECASE)]
    prob_count = max(1, len(bullets))
    problem_score = 4 if re.search(r'uncontrolled|threat.*?to.*?life|sepsis|necrotizing|osteomyelitis', asmt) \
                  else 3 if prob_count >= 2 else 2

    # Data axis
    data_score = 0
    if re.search(r'x.ray|mri|ct\s+scan|ultrasound|imaging|radiolog|stress\s+x', full): data_score = 1
    if re.search(r'independent\s+interpretation|re.read', full): data_score = min(data_score+1, 2)
    if re.search(r'review.*?outside|external.*?records?|prior.*?mri', full): data_score = min(data_score+1, 3)
    if re.search(r'lab|blood\s+work|culture|biopsy|pathology', full): data_score = min(data_score+1, 4)

    # Risk axis: Fix #5 tightened thresholds
    risk_score = 1
    if re.search(r'\brx\b|prescription|medication', full): risk_score = 2
    if re.search(r'(?:administered|performed|injected).*?(?:corticosteroid|betamethasone|steroid|injection)|bilateral.*?injection.*?administered', plan):
        risk_score = max(risk_score, 3)
    if re.search(r'scheduled\s+for|decision\s+for\s+surgery|pre.?op\s+orders|agreed\s+to\s+proceed', plan):
        risk_score = 3  # surgical decision = moderate, NOT high
    if re.search(r'anticoagul|apixaban|warfarin|rivaroxaban', full):
        risk_score = max(risk_score, 3)
    if re.search(r'performed.*?(?:arthrodesis|reconstruction|neurectomy|under\s+spinal|under\s+general)', plan):
        risk_score = 4

    effective = sorted([problem_score, data_score, risk_score])[1]  # median
    if effective >= 4: mdm, new, est = 'high', '99205', '99215'
    elif effective >= 3: mdm, new, est = 'moderate', '99204', '99214'
    elif effective >= 2: mdm, new, est = 'low', '99203', '99213'
    else: mdm, new, est = 'straightforward', '99202', '99212'

    return {
        'mdm_level': mdm, 'problem_score': problem_score,
        'data_score': data_score, 'risk_score': risk_score,
        'effective_score': effective, 'em_level_new': new, 'em_level_established': est,
        'reasoning': f'Problems:{problem_score}/4 Data:{data_score}/4 Risk:{risk_score}/4 MDM:{mdm}',
        'documentation_gaps': [],
    }
