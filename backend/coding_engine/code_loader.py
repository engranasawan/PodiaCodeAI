"""Code Loader — indexes all six authoritative code databases."""
import json, os, re
from typing import Dict, List, Optional, Set, Tuple

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')

def _load(fname):
    with open(os.path.join(DATA_DIR, fname), 'r', encoding='utf-8') as f:
        return json.load(f)

class CodeDatabases:
    _instance = None
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def initialize(self):
        if self._initialized: return
        print("[DB] Loading…")
        self._load_cpt(); self._load_icd(); self._load_hcpcs()
        self._load_ncci(); self._load_mue(); self._load_qualifying_dx()
        self._initialized = True
        print("[DB] Ready.")

    def _load_cpt(self):
        raw = _load('cpt_codes.json')
        codes = raw.get('codes', raw) if isinstance(raw, dict) else raw
        self.cpt_by_code: Dict[str, dict] = {str(c.get('code','')).strip(): c for c in codes if c.get('code')}
        print(f"  CPT: {len(self.cpt_by_code)}")

    def _load_icd(self):
        raw = _load('icd10cm_codes.json')
        codes = raw if isinstance(raw, list) else raw.get('codes', [])
        self.icd_by_code: Dict[str, dict] = {}
        self.icd_list: List[dict] = []
        for item in codes:
            code = str(item.get('code','')).strip()
            fmt = code[:3]+'.'+code[3:] if '.' not in code and len(code)>3 else code
            item['_fmt'] = fmt
            self.icd_by_code[code] = item
            self.icd_by_code[fmt] = item
            self.icd_list.append(item)
        print(f"  ICD: {len(self.icd_list)}")

    def _load_hcpcs(self):
        raw = _load('hcpcs_codes.json')
        codes = raw if isinstance(raw, list) else raw.get('codes', [])
        self.hcpcs_by_code: Dict[str, dict] = {}
        for item in codes:
            rc = str(item.get('code','')).strip()
            m = re.match(r'^([A-Z]\d{4})', rc)
            if m:
                code = m.group(1)
                if code not in self.hcpcs_by_code:
                    self.hcpcs_by_code[code] = {
                        'code': code,
                        'description': item.get('short_description', rc).strip(),
                    }
        print(f"  HCPCS: {len(self.hcpcs_by_code)}")

    def _load_ncci(self):
        raw = _load('latest_ncci_data.json')
        self.ncci_edits: Set[Tuple[str,str]] = set()
        self.ncci_mod_ok: Set[Tuple[str,str]] = set()
        for item in raw:
            c1,c2 = str(item.get('code1','')).strip(), str(item.get('code2','')).strip()
            if len(c1)>=4 and len(c2)>=4 and c1[0].isalnum():
                self.ncci_edits.add((c1,c2)); self.ncci_edits.add((c2,c1))
                if str(item.get('modifier','')).strip()=='1':
                    self.ncci_mod_ok.add((c1,c2)); self.ncci_mod_ok.add((c2,c1))
        print(f"  NCCI: {len(self.ncci_edits)} pairs")

    def _load_mue(self):
        raw = _load('latest_mue_practitioner.json')
        self.mue: Dict[str,int] = {}
        for item in raw:
            code = str(item.get('code','')).strip()
            try: self.mue[code] = int(item.get('mue_value',0))
            except: pass
        print(f"  MUE: {len(self.mue)}")

    def _load_qualifying_dx(self):
        raw = _load('podiatry_routine_foot_care_qualifying_dx.json')
        self.qualifying_dx: Set[str] = set(raw.get('qualifying_dx', []))
        print(f"  LCD DX: {len(self.qualifying_dx)}")

    def get_cpt(self, code): return self.cpt_by_code.get(str(code).strip())
    def get_icd(self, code):
        c = code.strip()
        return self.icd_by_code.get(c) or self.icd_by_code.get(c.replace('.',''))
    def get_hcpcs(self, code): return self.hcpcs_by_code.get(str(code).strip())
    def get_mue(self, code): return self.mue.get(str(code).strip())
    def check_ncci(self, c1, c2):
        p=(c1.strip(),c2.strip())
        return p in self.ncci_edits, p in self.ncci_mod_ok
    def is_qualifying_dx(self, code):
        return code.replace('.','') in {q.replace('.','') for q in self.qualifying_dx}

db = CodeDatabases()
