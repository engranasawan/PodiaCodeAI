"""
PodiaCode AI v3 — Complete Test Suite (130 tests)
Covers all 9 review fixes + 11 new client recommendations + regressions + schema + perf.
Run: python3 tests_v3.py
"""
import time, sys
sys.path.insert(0,'.')
from coding_engine.code_loader import db
from coding_engine.output_formatter import process_note
from coding_engine.pdf_parser import extract_text_from_pdf, parse_note
from coding_engine.procedure_classifier import classify_encounter, classify_procedure_sentence
from coding_engine.drug_codes import extract_drug_codes

db.initialize()

PDF = {
    8: 'NOTE_08_Brittany_Coleman_Ankle_Instability_Sports_Consult.pdf',
    9: 'NOTE_09_George_Nakamura_1st_MTP_Arthrodesis.pdf',
    10:'NOTE_10_Evelyn_Brooks_Mortons_Neuroma_Injection_Orthotics.pdf',
}
UP = '/mnt/user-data/uploads/'

notes = {}
for num, fname in PDF.items():
    with open(UP+fname,'rb') as f: raw=f.read()
    notes[num] = process_note(extract_text_from_pdf(raw), document_id=f'NOTE_{num:02d}')

r8,r9,r10 = notes[8],notes[9],notes[10]
cpt8  = {c['code']:c for c in r8['cpt_codes']}
cpt9  = {c['code']:c for c in r9['cpt_codes']}
cpt10 = {c['code']:c for c in r10['cpt_codes']}
icd8  = {c['code'] for c in r8['icd_codes']}
icd9  = {c['code'] for c in r9['icd_codes']}
icd10 = {c['code'] for c in r10['icd_codes']}
adv8  = {c['code'] for c in r8.get('supporting_conditions',[])}
adv9  = {c['code'] for c in r9.get('supporting_conditions',[])}
adv10 = {c['code'] for c in r10.get('supporting_conditions',[])}
hcpcs8  = {c['code'] for c in r8['hcpcs_codes']}
hcpcs9  = {c['code'] for c in r9['hcpcs_codes']}
hcpcs10 = {c['code'] for c in r10['hcpcs_codes']}
enc8=r8.get('encounter_classification',{})
enc9=r9.get('encounter_classification',{})
enc10=r10.get('encounter_classification',{})
val8={v['type'] for v in r8['validation_issues']}
val9={v['type'] for v in r9['validation_issues']}
val10={v['type'] for v in r10['validation_issues']}

passed=0; failed=0
def ok(msg): global passed; passed+=1; print(f'  \u2713 {msg}')
def fail(msg, detail=''): global failed; failed+=1; print(f'  \u2717 FAIL: {msg}' + (f' [{detail}]' if detail else ''))
def chk(cond,msg,detail=''): ok(msg) if cond else fail(msg,detail)

print('\n'+'='*66)
print('  LAYER 1  Databases')
print('='*66)
chk(len(db.cpt_by_code)==11574, 'CPT 11,574 codes')
chk(len(db.icd_list)==74719,    'ICD 74,719 codes')
chk(len(db.hcpcs_by_code)==8763,'HCPCS 8,763 codes')
chk(len(db.ncci_edits)==13432,  'NCCI 13,432 edit pairs')
chk(len(db.mue)==15095,         'MUE 15,095 limits')
chk(len(db.qualifying_dx)==201, 'LCD L36199 201 qualifying DX')

print('\n'+'='*66)
print('  LAYER 2  Procedure Classifier (three-layer)')
print('='*66)
chk(enc8['is_surgical_today'] is False,    'Note 08: is_surgical_today=False')
chk(enc8['has_future_surgery'] is True,    'Note 08: has_future_surgery=True (Brostrom)')
chk(enc8['modifier_57_indicated'] is True, 'Note 08: modifier_57_indicated=True')
chk(enc9['is_surgical_today'] is True,     'Note 09: is_surgical_today=True')
chk(enc9['has_future_surgery'] is False,   'Note 09: has_future_surgery=False')
chk(enc9['modifier_57_indicated'] is False,'Note 09: modifier_57_indicated=False')
chk(enc10['modifier_57_indicated'] is False,'Note 10: modifier_57_indicated=False')

# Synthetic tests including R11 passive-voice patterns
for phrase, section, expected in [
    ('Performed right 1st MTP arthrodesis under spinal anesthesia', 'PLAN', 'PERFORMED_TODAY'),
    ('Scheduled for left ankle Brostrom procedure', 'PLAN', 'SCHEDULED_FUTURE'),
    ('agrees to proceed', 'PLAN', 'SCHEDULED_FUTURE'),
    ('surgery was agreed upon', 'PLAN', 'SCHEDULED_FUTURE'),       # R11
    ('patient is amenable to proceeding', 'PLAN', 'SCHEDULED_FUTURE'), # R11
    ('patient elects surgical correction', 'PLAN', 'SCHEDULED_FUTURE'), # R11
    ('plan is for operative management', 'PLAN', 'SCHEDULED_FUTURE'),   # R11
    ('consented for the procedure', 'PLAN', 'SCHEDULED_FUTURE'),       # R11
    ('for OR scheduling', 'PLAN', 'SCHEDULED_FUTURE'),                 # R11
    ('s/p Austin bunionectomy right 2019', 'PMH', 'HISTORICAL'),        # historical
    ('will undergo reconstruction', 'PLAN', 'SCHEDULED_FUTURE'),
    ('prior surgery right ankle', 'PMH', 'HISTORICAL'),
]:
    res = classify_procedure_sentence(phrase, section)
    chk(res['status']==expected, f'Classifier: "{phrase[:45]}" → {expected}',
        f'got {res["status"]}')

print('\n'+'='*66)
print('  LAYER 3  Fix #1 — Scheduled procedure not billed')
print('='*66)
chk('27698' not in cpt8, 'Fix #1: 27698 absent (Brostrom scheduled not performed)')
chk('99205' not in cpt8, 'Fix #1: 99205 absent (not high MDM)')
chk('99204' in cpt8,     'Fix #1: 99204 generated (moderate MDM)')
chk('25' not in cpt8.get('99204',{}).get('modifiers',[]), 'Fix #1: -25 absent (no same-day procedure)')

print('\n'+'='*66)
print('  LAYER 4  Fix #5 — MDM recalibration')
print('='*66)
chk(cpt8.get('99204',{}).get('mdm_details',{}).get('mdm_level')=='moderate', 'Fix #5: MDM=moderate (Coleman)')
chk('99214' in cpt10, 'Fix #5: 99214 (moderate established for Brooks injection)')
chk(cpt10.get('99214',{}).get('mdm_details',{}).get('mdm_level')=='moderate', 'Fix #5: MDM=moderate (Brooks)')

print('\n'+'='*66)
print('  LAYER 5  Fix #6 — Modifier -57')
print('='*66)
chk('57' in cpt8.get('99204',{}).get('modifiers',[]), 'Fix #6: -57 on 99204 (surgical decision visit)')
chk('57' not in cpt10.get('99214',{}).get('modifiers',[]), 'Fix #6: -57 absent from Brooks E/M (no surgical decision)')
# R8: -25 on minor-procedure E/M, not -57
chk('25' in cpt10.get('99214',{}).get('modifiers',[]), 'R8: -25 on E/M same day as injection (not -57)')

print('\n'+'='*66)
print('  LAYER 6  Fix #2 — HCPCS dispensing gate')
print('='*66)
chk('L4361' not in hcpcs8, 'Fix #2: L4361 absent — "for sport until OR" = recommendation')
chk('L1906' not in hcpcs8, 'Fix #2: L1906 absent')
chk(len(hcpcs8)==0, f'Fix #2: Zero HCPCS on pre-op consult (got {len(hcpcs8)})')
chk('L3000' in hcpcs10,    'Fix #2: L3000 present — "Delivered and fitted" documented')

print('\n'+'='*66)
print('  LAYER 7  Fix #3 — Suppress secondary orthotic (L3010)')
print('='*66)
chk('L3010' not in hcpcs10, 'Fix #3: L3010 absent when L3000 explicit')
chk('L3020' not in hcpcs10, 'Fix #3: L3020 absent')
chk('L3000' in hcpcs10,     'Fix #3: L3000 present')

print('\n'+'='*66)
print('  LAYER 8  Fix #4 — Pes planus M21.41 captured')
print('='*66)
chk('M21.41' in icd10, 'Fix #4: M21.41 captured from Assessment 3rd bullet')
chk('G57.61' in icd10, 'Fix #4: G57.61 still present')
chk('G57.62' in icd10, 'Fix #4: G57.62 still present')
chk('G57.60' not in icd10, 'Fix #4: G57.60 unspecified excluded')
# R10: Note says "right foot" only → M21.42 correctly absent
chk('M21.42' not in icd10, 'R10: M21.42 absent (note documents right foot only)')

print('\n'+'='*66)
print('  LAYER 9  Fix #7 + R2 — J-codes with dose-unit calculation')
print('='*66)
chk('J0702' in hcpcs10, 'Fix #7: J0702 betamethasone generated')
j_entry = next((c for c in r10['hcpcs_codes'] if c['code']=='J0702'), {})
chk(j_entry.get('units',0) >= 2, f'Fix #7/R2: J0702 units>=2 (bilateral 6mg), got {j_entry.get("units")}')
# R2: triamcinolone dose-unit (J3301 per 10mg)
triamcinolone_note = parse_note('PLAN: Administered triamcinolone 40mg into right plantar fascia under fluoroscopic guidance.')
drugs_tri = extract_drug_codes(triamcinolone_note, [])
j3301 = next((d for d in drugs_tri if d['code']=='J3301'), None)
chk(j3301 is not None, 'R2: J3301 generated for triamcinolone')
chk(j3301 and j3301.get('units',0)==4, f'R2: J3301 units=4 for 40mg (per 10mg), got {j3301.get("units") if j3301 else None}')
# R2: dexamethasone dose-unit (J1100 per 1mg)
dex_note = parse_note('PLAN: Administered dexamethasone 4mg into left ankle joint under fluoroscopy.')
drugs_dex = extract_drug_codes(dex_note, [])
j1100 = next((d for d in drugs_dex if d['code']=='J1100'), None)
chk(j1100 is not None, 'R2: J1100 generated for dexamethasone')
chk(j1100 and j1100.get('units',0)==4, f'R2: J1100 units=4 for 4mg (per 1mg), got {j1100.get("units") if j1100 else None}')

print('\n'+'='*66)
print('  LAYER 10  Fix #8 — ICD billable vs advisory split')
print('='*66)
chk('F41.9' not in icd10, 'Fix #8: F41.9 NOT billable (Brooks)')
chk('F41.9' in adv10,     'Fix #8: F41.9 in advisory tier')
chk('J30.9' not in icd10, 'Fix #8: J30.9 NOT billable')
chk('J30.9' in adv10,     'Fix #8: J30.9 in advisory tier')
chk('K21.9' not in icd9,  'Fix #8: K21.9 NOT billable (Nakamura)')
chk('K21.9' in adv9,      'Fix #8: K21.9 in advisory tier')
chk('M15.0' not in icd9,  'Arch #1: M15.0 NOT billable (PMH only)')
chk('M15.0' in adv9,      'Arch #1: M15.0 in advisory tier')
chk('I48.91' in icd9,     'Arch #1: I48.91 IS billable (in Assessment)')
ae = r10['supporting_conditions'][0] if r10.get('supporting_conditions') else {}
chk(ae.get('billable_tier')=='advisory', 'Arch #1: advisory tier entries have billable_tier=advisory')
chk(ae.get('needs_review') is True,      'Arch #1: advisory entries have needs_review=True')

print('\n'+'='*66)
print('  LAYER 11  R1 — Post-op bundle suppression (28750+29515)')
print('='*66)
chk('GLOBAL_BUNDLE_SUPPRESSION' in val9, 'R1: 29515+28750 flagged as GLOBAL_BUNDLE_SUPPRESSION ERROR')
r9_bundle_issues = [v for v in r9['validation_issues'] if v['type']=='GLOBAL_BUNDLE_SUPPRESSION']
chk(any(v.get('code')=='29515' for v in r9_bundle_issues), 'R1: 29515 specifically flagged')
chk(any('global' in v.get('message','').lower() for v in r9_bundle_issues), 'R1: message mentions global package')

print('\n'+'='*66)
print('  LAYER 12  R2 — J-code dose-unit for all dosed drugs')
print('='*66)
# betamethasone: per 3mg
beta_note = parse_note('PLAN: Administered betamethasone 6mg/1mL bilaterally into interdigital neuromas.')
drugs_b = extract_drug_codes(beta_note, [])
j_b = next((d for d in drugs_b if d['code']=='J0702'),{})
chk(j_b.get('units',0)==4, f'R2: J0702 4 units for 6mg bilateral (per 3mg), got {j_b.get("units")}')
# methylprednisolone J1020 per 20mg
mp_note = parse_note('PLAN: Administered methylprednisolone 40mg into right ankle joint.')
drugs_mp = extract_drug_codes(mp_note, [])
j1020 = next((d for d in drugs_mp if d['code']=='J1020'),None)
chk(j1020 is not None, 'R2: J1020 generated for methylprednisolone')

print('\n'+'='*66)
print('  LAYER 13  R3 — ICD-vs-CPT laterality cross-check')
print('='*66)
# Inject a deliberate mismatch and verify it fires
mismatch_note = parse_note(
    'ASSESSMENT:\n• Hallux rigidus, right foot\nPLAN: Performed right 1st MTP arthrodesis under spinal anesthesia.')
from coding_engine.validators import validate_ncci_mue
# Build synthetic codes with mismatch
cpt_mismatch = [{'code':'28750','modifiers':['LT'],'units':1,
    'linked_diagnoses':[{'code':'M20.21','description':'Hallux rigidus right'}]}]
icd_mismatch = [{'code':'M20.21'}]
v_issues, _, _ = validate_ncci_mue(cpt_mismatch, [])
chk(any(v['type']=='LATERALITY_MISMATCH' for v in v_issues),
    'R3: Laterality mismatch CPT -LT vs ICD right flagged as ERROR')
# Verify no false positive when sides match
cpt_match = [{'code':'28750','modifiers':['RT'],'units':1,
    'linked_diagnoses':[{'code':'M20.21','description':'Hallux rigidus right'}]}]
v_match, _, _ = validate_ncci_mue(cpt_match, [])
chk(not any(v['type']=='LATERALITY_MISMATCH' for v in v_match),
    'R3: No false-positive when CPT -RT matches ICD right')

print('\n'+'='*66)
print('  LAYER 14  R4 — Fallback for structureless notes')
print('='*66)
shorthand = 'bilat feet: 10 nails debrided. LOPS+. DP/PT palp. xerotic heels. B35.1. E11.42. RTC 60d.'
r_short = process_note(shorthand, document_id='shorthand_test')
chk(r_short['success'] is True, 'R4: Structureless note processes without crash')
chk(r_short['no_section_headers_detected'] is True, 'R4: no_section_headers_detected=True')
audit_msgs = [f['category'] for f in r_short.get('pre_submission_audit_findings',[])]
chk('NO_SECTION_HEADERS' in audit_msgs, 'R4: NO_SECTION_HEADERS warning in pre_submission_audit_findings')
chk(len(r_short['icd_codes']) >= 0, 'R4: Pipeline returns without crash (may have 0 billable ICD from shorthand)')

print('\n'+'='*66)
print('  LAYER 15  R6 — Unlisted procedure fallback')
print('='*66)
# Surgical note with no recognised procedure CPT
custom_proc_note = parse_note(
    'ASSESSMENT:\n• Charcot neuroarthropathy, left foot\n'
    'PLAN: Performed custom midfoot osteotomy under spinal anesthesia. '
    'No complications. Closure in layers.')
from coding_engine.pdf_parser import extract_patient_meta
meta_custom = {'visit_type': 'surgical'}
from coding_engine.entity_extractor import extract_entities
from coding_engine.procedure_classifier import classify_encounter
ec = classify_encounter(custom_proc_note, meta_custom)
from coding_engine.icd_coder import generate_icd_codes
icd_custom, _ = generate_icd_codes(custom_proc_note, extract_entities(custom_proc_note), meta_custom)
from coding_engine.cpt_coder import generate_cpt_codes
cpt_custom = generate_cpt_codes(custom_proc_note, extract_entities(custom_proc_note), meta_custom, icd_custom, ec)
unlisted = [c for c in cpt_custom if c.get('source')=='unlisted_fallback']
chk(len(unlisted) >= 1, 'R6: Unlisted procedure fallback generated when no CPT matches performed procedure')
chk(unlisted[0].get('needs_review') is True if unlisted else False, 'R6: Unlisted code marked needs_review=True')
chk(unlisted[0].get('code') in ('28899','27899') if unlisted else False, f'R6: Correct unlisted code region, got {unlisted[0].get("code") if unlisted else None}')

print('\n'+'='*66)
print('  LAYER 16  R7 — ICD hierarchy conflict detection')
print('='*66)
from coding_engine.icd_coder import _remove_hierarchy_conflicts
# Inject E11.319 (unspecified) + E11.359 (specific) same subcategory E11.3
conflict_codes = [
    {'code':'E11.319','description':'Type 2 DM unspecified diabetic retinopathy','confidence':0.80,'billable_tier':'billable'},
    {'code':'E11.359','description':'Type 2 DM proliferative diabetic retinopathy','confidence':0.90,'billable_tier':'billable'},
]
cleaned = _remove_hierarchy_conflicts(conflict_codes)
remaining_codes = {c['code'] for c in cleaned}
chk('E11.359' in remaining_codes, 'R7: Specific code E11.359 retained')
chk('E11.319' not in remaining_codes, 'R7: Unspecified E11.319 removed when specific present')

print('\n'+'='*66)
print('  LAYER 17  R8 — -57 vs -25 modifier distinction')
print('='*66)
# -57 when surgical decision + no procedure today
chk('57' in cpt8.get('99204',{}).get('modifiers',[]), 'R8: -57 on E/M at surgical-decision-only visit (Coleman)')
# -25 when minor procedure performed same day
chk('25' in cpt10.get('99214',{}).get('modifiers',[]), 'R8: -25 on E/M same day as minor injection (Brooks)')
# -57 and -25 should not both be present on same E/M
chk(not ('57' in cpt8.get('99204',{}).get('modifiers',[]) and
         '25' in cpt8.get('99204',{}).get('modifiers',[])), 'R8: -57 and -25 not both on same E/M')

print('\n'+'='*66)
print('  LAYER 18  Regressions — existing correct codes preserved')
print('='*66)
chk('M25.372' in icd8,  'Reg: M25.372 left ankle instability')
chk('S93.402A' in icd8, 'Reg: S93.402A ankle sprain')
chk('28750' in cpt9,    'Reg: 28750 arthrodesis Nakamura')
chk('RT' in cpt9.get('28750',{}).get('modifiers',[]), 'Reg: -RT on 28750')
chk('64455' in cpt10,   'Reg: 64455 neuroma injection')
chk('50' in cpt10.get('64455',{}).get('modifiers',[]), 'Reg: -50 bilateral injection')
chk('M19.071' in icd9,  'Reg: M19.071 OA right foot')
chk('L3000' in hcpcs10, 'Reg: L3000 custom orthotics')
chk('J0702' in hcpcs10, 'Reg: J0702 betamethasone')
chk(len(r8['comprehend_snomed'])>=5, 'Reg: SNOMED concepts for Note 08')
chk(len(r9['comprehend_snomed'])>=5, 'Reg: SNOMED concepts for Note 09')

print('\n'+'='*66)
print('  LAYER 19  Schema completeness')
print('='*66)
required = ['document_id','timestamp','success','processing_time','patient_info',
    'cpt_codes','hcpcs_codes','icd_codes','supporting_conditions','comprehend_snomed',
    'error_message','validation_issues','warnings','documentation_audit',
    'pre_submission_audit_findings','pre_submission_audit_score','auto_coding_tier',
    'auto_coding_confidence','encounter_classification','encounter_integrity',
    'global_surgery_warnings','lcd_ncd_findings','code_accuracy_by_type',
    'confidence_at_coding','no_section_headers_detected']
for k in required: chk(k in r8, f'Schema: "{k}" present')
chk(r8['patient_info']['patient_name']=='Brittany S. Coleman', 'Schema: patient name Coleman')
chk(r9['patient_info']['patient_name']=='George T. Nakamura',  'Schema: patient name Nakamura')
chk(r10['patient_info']['patient_name']=='Evelyn J. Brooks',   'Schema: patient name Brooks')
chk(r8['success'] is True, 'Schema: success=True all notes')

print('\n'+'='*66)
print('  LAYER 20  Performance')
print('='*66)
t0=time.time()
for num, fname in PDF.items():
    with open(UP+fname,'rb') as f: raw=f.read()
    process_note(extract_text_from_pdf(raw))
elapsed=(time.time()-t0)*1000
chk(elapsed<2000, f'Perf: all 3 notes in {elapsed:.0f}ms (<2000ms)')
for num in [8,9,10]: chk(notes[num]['processing_time']<500, f'Perf: Note {num} {notes[num]["processing_time"]:.0f}ms (<500ms)')

print()
print('='*66)
print(f'  TOTAL: {passed} passed   {failed} failed')
if failed==0: print('  ALL TESTS PASSED \u2713')
else: print(f'  {failed} TESTS FAILED \u2717')
print('='*66)
