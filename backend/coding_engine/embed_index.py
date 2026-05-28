"""
Embedding-Based Code Search — Architecture Enhancement (from client suggestion doc).

Expands coverage from 80 diagnosis patterns to all 95,056 code descriptions.
Uses sentence-transformers (all-MiniLM-L6-v2) + FAISS for vector similarity search.

Install dependencies:
    pip install sentence-transformers faiss-cpu numpy

This module is designed as a drop-in replacement for the pattern-based
entity extractor. All downstream pipeline stages (procedure_classifier,
icd_coder, cpt_coder, hcpcs_coder, validators) are unchanged.

Usage:
    from coding_engine.embed_index import CodeEmbeddingIndex
    idx = CodeEmbeddingIndex("data/cpt_codes.json", "data/icd10cm_codes.json", "data/hcpcs_codes.json")
    results = idx.search("posterior tibial tendon dysfunction stage II left", top_k=5)
    # Returns: [{'code': 'M76.822', 'description': '...', 'system': 'ICD-10-CM', 'score': 0.93}, ...]
"""
import json, os
from typing import List, Dict

# Thresholds (from architecture suggestion doc)
BILLABLE_THRESHOLD = 0.90   # Assessment-sourced → billable tier
ADVISORY_THRESHOLD = 0.75   # PMH/lower confidence → advisory tier

class CodeEmbeddingIndex:
    """
    Builds a FAISS vector index over all CPT + ICD-10-CM + HCPCS descriptions.
    Falls back gracefully if sentence-transformers or faiss are not installed.
    """

    def __init__(self, cpt_path: str, icd_path: str, hcpcs_path: str):
        self.codes: List[tuple] = []  # (code, description, system)
        self.index = None
        self.model = None
        self._available = False

        try:
            from sentence_transformers import SentenceTransformer
            import faiss, numpy as np
            self._faiss = faiss
            self._np = np
            self.model = SentenceTransformer("all-MiniLM-L6-v2")
            self._build(cpt_path, icd_path, hcpcs_path)
            self._available = True
            print(f"[EmbedIndex] Built: {len(self.codes):,} codes indexed")
        except ImportError:
            print("[EmbedIndex] sentence-transformers/faiss not installed — using pattern fallback")
        except Exception as e:
            print(f"[EmbedIndex] Build failed: {e} — using pattern fallback")

    @property
    def is_available(self) -> bool:
        return self._available

    def _build(self, cpt_path: str, icd_path: str, hcpcs_path: str):
        import numpy as np
        import faiss as _faiss

        loaders = [
            (cpt_path, 'CPT', lambda d: d.get('codes', d) if isinstance(d, dict) else d),
            (icd_path, 'ICD-10-CM', lambda d: d if isinstance(d, list) else d.get('codes', [])),
            (hcpcs_path, 'HCPCS', lambda d: d if isinstance(d, list) else d.get('codes', [])),
        ]
        for path, system, extract in loaders:
            if not os.path.exists(path):
                continue
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for entry in extract(data):
                code = str(entry.get('code', '')).strip()
                # Clean HCPCS embedded codes
                import re
                m = re.match(r'^([A-Z]\d{4})', code)
                if system == 'HCPCS' and m:
                    code = m.group(1)
                desc = (entry.get('long_description') or entry.get('description') or
                        entry.get('short_description') or '').strip()
                if code and desc:
                    self.codes.append((code, desc, system))

        descriptions = [c[1] for c in self.codes]
        print(f"[EmbedIndex] Encoding {len(descriptions):,} descriptions…")
        embeddings = self.model.encode(
            descriptions, batch_size=512,
            show_progress_bar=True,
            convert_to_numpy=True
        ).astype('float32')
        _faiss.normalize_L2(embeddings)
        self.index = _faiss.IndexFlatIP(embeddings.shape[1])
        self.index.add(embeddings)

    def search(self, query: str, top_k: int = 8) -> List[Dict]:
        """Return top_k closest codes to query. Returns empty list if not available."""
        if not self._available or self.index is None:
            return []
        import numpy as np
        vec = self.model.encode([query], convert_to_numpy=True).astype('float32')
        self._faiss.normalize_L2(vec)
        scores, indices = self.index.search(vec, top_k)
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or score < ADVISORY_THRESHOLD:
                continue
            code, desc, system = self.codes[idx]
            results.append({
                'code': code, 'description': desc, 'system': system,
                'score': float(score),
                'tier': 'billable' if score >= BILLABLE_THRESHOLD else 'advisory',
            })
        return results

    def search_assessment(self, assessment_text: str) -> List[Dict]:
        """
        Segment assessment text into clinical phrases and search each.
        Returns merged, deduplicated results above ADVISORY_THRESHOLD.
        """
        import re
        phrases = re.split(r'[.;\n]|\d+[.)]\s', assessment_text)
        phrases = [p.strip() for p in phrases if len(p.strip()) > 8]
        seen = set()
        all_results = []
        for phrase in phrases:
            for hit in self.search(phrase, top_k=5):
                if hit['code'] not in seen:
                    hit['source_phrase'] = phrase
                    all_results.append(hit)
                    seen.add(hit['code'])
        all_results.sort(key=lambda x: -x['score'])
        return all_results


# Global singleton (initialised lazily by main.py if dependencies available)
_embed_index: CodeEmbeddingIndex = None

def get_embed_index() -> CodeEmbeddingIndex:
    return _embed_index

def init_embed_index(cpt_path, icd_path, hcpcs_path):
    global _embed_index
    _embed_index = CodeEmbeddingIndex(cpt_path, icd_path, hcpcs_path)
    return _embed_index
