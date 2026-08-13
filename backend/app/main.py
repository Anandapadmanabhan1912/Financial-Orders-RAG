import os
import shutil
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List
from pydantic import BaseModel

from backend.app.config import UPLOADS_DIR, PREVIEWS_DIR, PORT, HOST
from backend.app.db import init_db, get_all_documents, get_document_by_id
from backend.app.ingestor import process_and_ingest_pdf
from backend.app.version_engine import recompute_all_document_statuses, get_version_chain_for_document, resolve_as_of_date
from backend.app.hybrid_retriever import hybrid_retrieve
from backend.app.llm_service import generate_grounded_rag_response
from backend.seed_data.generate_seed_gos import generate_all_seeds

app = FastAPI(
    title="ORDERWISE — Kerala Finance GO Knowledge Assistant",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize DB schema on startup
@app.on_event("startup")
def startup_event():
    init_db()
    # Check if seed documents exist, if not generate & ingest
    existing_docs = get_all_documents()
    if not existing_docs:
        print("No existing documents in DB. Generating and ingesting seed GO PDFs...")
        generate_all_seeds(str(UPLOADS_DIR))
        for fname in os.listdir(UPLOADS_DIR):
            if fname.endswith(".pdf"):
                fpath = os.path.join(UPLOADS_DIR, fname)
                try:
                    process_and_ingest_pdf(fpath)
                except Exception as e:
                    print(f"Error ingesting seed PDF {fname}: {e}")
        recompute_all_document_statuses()
        print("Seed document ingestion complete!")

# Data Models
class ChatRequest(BaseModel):
    query: str
    as_of_date: Optional[str] = None

class AsOfDateRequest(BaseModel):
    date_str: str

# API Routes

@app.get("/api/documents")
def list_documents():
    recompute_all_document_statuses()
    docs = get_all_documents()
    return {"status": "success", "count": len(docs), "documents": docs}

@app.get("/api/documents/{doc_id}")
def get_document_detail(doc_id: str):
    doc = get_document_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    chain = get_version_chain_for_document(doc_id)
    return {"status": "success", "document": doc, "version_chain": chain}

@app.get("/api/documents/{doc_id}/preview/{page}")
def get_page_preview(doc_id: str, page: int):
    img_path = PREVIEWS_DIR / doc_id / f"page_{page}.png"
    if not img_path.exists():
        raise HTTPException(status_code=404, detail="Preview image not found")
    return FileResponse(str(img_path), media_type="image/png")

@app.post("/api/upload")
async def upload_document(file: UploadFile = File(...)):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")
        
    save_path = os.path.join(UPLOADS_DIR, file.filename)
    with open(save_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    try:
        print(f"[DEBUG UPLOAD] Uploading file: {file.filename}", flush=True)
        res = process_and_ingest_pdf(save_path)
        recompute_all_document_statuses()
        print(f"[DEBUG UPLOAD] File {file.filename} processed successfully.", flush=True)
        return {
            "status": "success",
            "message": f"Successfully processed and indexed {file.filename}",
            "details": res
        }
    except Exception as e:
        print(f"[DEBUG UPLOAD ERROR] Failed to process PDF {file.filename}: {e}", flush=True)
        raise HTTPException(status_code=500, detail=f"Failed to process PDF: {str(e)}")

@app.post("/api/chat")
def chat_query(req: ChatRequest):
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")
        
    # Execute hybrid retrieval (BM25 + Vector + RRF)
    retrieval_res = hybrid_retrieve(query=req.query, as_of_date=req.as_of_date, top_k=5)
    
    # Grounded RAG Generation
    response_payload = generate_grounded_rag_response(req.query, retrieval_res)
    
    # Include tool execution trace for transparency
    response_payload["tool_trace"] = {
        "query": req.query,
        "as_of_date": req.as_of_date,
        "bm25_matches": retrieval_res.get("bm25_count", 0),
        "vector_matches": retrieval_res.get("vector_count", 0),
        "candidate_chunks": len(retrieval_res.get("evidence", [])),
        "evidence_used": [
            {
                "doc_id": ev.get("document_id"),
                "go_number": ev.get("go_number"),
                "page": ev.get("page_num"),
                "rrf_score": round(ev.get("rrf_score", 0), 4)
            } for ev in retrieval_res.get("evidence", [])
        ]
    }
    
    return response_payload

@app.post("/api/as-of-date")
def evaluate_as_of_date(req: AsOfDateRequest):
    if not req.date_str:
        raise HTTPException(status_code=400, detail="Date string required.")
    results = resolve_as_of_date(req.date_str)
    return {
        "as_of_date": req.date_str,
        "active_documents": results
    }

# Mount static frontend files
frontend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend"))
app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
