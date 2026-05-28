"""PodiaCode AI v3 — FastAPI backend."""
import io, os, uuid
from contextlib import asynccontextmanager
from typing import Optional
import fastapi
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from coding_engine.code_loader import db
from coding_engine.pdf_parser import extract_text_from_pdf
from coding_engine.output_formatter import process_note

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[Startup] Loading databases…")
    db.initialize()
    # Try embedding index if deps available
    try:
        from coding_engine.embed_index import init_embed_index
        DATA = os.path.join(os.path.dirname(__file__), 'data')
        ei = init_embed_index(f'{DATA}/cpt_codes.json', f'{DATA}/icd10cm_codes.json', f'{DATA}/hcpcs_codes.json')
        app.state.embed_index = ei
    except Exception as e:
        print(f"[Startup] Embedding index skipped: {e}")
        app.state.embed_index = None
    print("[Startup] Ready.")
    yield

app = FastAPI(title="PodiaCode AI v3", version="3.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

class TextReq(BaseModel):
    text: str
    document_id: Optional[str] = None

@app.get("/health")
def health():
    return {"status":"ok","databases_loaded":db._initialized,
            "cpt":len(db.cpt_by_code),"icd":len(db.icd_list),
            "hcpcs":len(db.hcpcs_by_code),"ncci_pairs":len(db.ncci_edits),
            "mue":len(db.mue),"version":"3.0.0"}

@app.post("/api/code/pdf")
async def code_pdf(file: UploadFile = File(...)):
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(400, "Only PDF files accepted.")
    content = await file.read()
    if len(content) > 20*1024*1024:
        raise HTTPException(413, "File too large (max 20MB).")
    try: note_text = extract_text_from_pdf(content)
    except Exception as e: raise HTTPException(422, f"PDF extraction failed: {e}")
    if len(note_text.strip()) < 50:
        raise HTTPException(422, "PDF has no extractable text.")
    result = process_note(note_text, document_id=file.filename.replace('.pdf','_results'))
    return JSONResponse(result)

@app.post("/api/code/text")
async def code_text(req: TextReq):
    if len(req.text.strip()) < 50: raise HTTPException(400, "Note text too short.")
    result = process_note(req.text, document_id=req.document_id or f"text_{uuid.uuid4().hex[:8]}")
    return JSONResponse(result)

@app.get("/api/lookup/cpt/{code}")
def lookup_cpt(code: str):
    e = db.get_cpt(code)
    if not e: raise HTTPException(404, f"CPT {code} not found.")
    return e

@app.get("/api/lookup/icd/{code}")
def lookup_icd(code: str):
    e = db.get_icd(code)
    if not e: raise HTTPException(404, f"ICD {code} not found.")
    return e

@app.get("/api/lookup/hcpcs/{code}")
def lookup_hcpcs(code: str):
    e = db.get_hcpcs(code)
    if not e: raise HTTPException(404, f"HCPCS {code} not found.")
    return e

@app.get("/api/lookup/mue/{code}")
def lookup_mue(code: str):
    v = db.get_mue(code)
    if v is None: raise HTTPException(404, f"No MUE for {code}.")
    return {"code": code, "mue_limit": v}

@app.get("/api/lookup/ncci")
def lookup_ncci(code1: str, code2: str):
    conflict, mod_ok = db.check_ncci(code1, code2)
    return {"code1":code1,"code2":code2,"has_conflict":conflict,"modifier_can_bypass":mod_ok}

@app.get("/api/stats")
def stats():
    return {"engine":"PodiaCode AI v3",
            "databases":{"cpt":len(db.cpt_by_code),"icd10cm":len(db.icd_list),
                         "hcpcs":len(db.hcpcs_by_code),"ncci_pairs":len(db.ncci_edits),"mue":len(db.mue)},
            "supported_code_types":["CPT","ICD-10-CM","HCPCS","SNOMED","NCCI"],
            "validation_layers":["NCCI_PTP","MUE","LCD_L36199","Global_Surgery","Documentation_Audit",
                                 "ICD_vs_CPT_Laterality","PostOp_Bundle_Suppression","ICD_Hierarchy_Conflict"],
            "v3_new_features":["Three-layer procedure classifier","Per-unit J-code dose calculation",
                               "ICD-CPT laterality cross-check","Post-op bundle suppression",
                               "Unlisted procedure fallback","ICD hierarchy conflict detection",
                               "Embedding index ready (install sentence-transformers + faiss-cpu)"]}
