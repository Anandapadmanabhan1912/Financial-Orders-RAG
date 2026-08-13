import os
import fitz  # PyMuPDF
import pdfplumber
import uuid
import json
from typing import Dict, Any, List
from backend.app.config import UPLOADS_DIR
from backend.app.pdf_utils import generate_all_page_previews
from backend.app.metadata_extractor import (
    extract_go_number,
    extract_department,
    extract_date,
    extract_abstract,
    extract_financial_parameters,
    extract_references_and_relations
)
from backend.app.db import save_document, save_chunks, save_references, get_db_connection

# Lazy embedding model loader
_embed_model = None

def get_embedding_model():
    global _embed_model
    if _embed_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _embed_model = SentenceTransformer('all-MiniLM-L6-v2')
            print("Loaded local SentenceTransformer model (all-MiniLM-L6-v2).")
        except Exception as e:
            print(f"SentenceTransformer not available ({e}). Using heuristic vector fallback.")
            _embed_model = "heuristic"
    return _embed_model

def generate_embedding(text: str) -> List[float]:
    model = get_embedding_model()
    if model and model != "heuristic":
        try:
            return model.encode(text).tolist()
        except Exception as e:
            print(f"Error encoding embedding: {e}")
    # Simple term frequency embedding fallback (32 dims)
    words = text.lower().split()
    vec = [0.0] * 32
    for w in words:
        idx = sum(ord(c) for c in w) % 32
        vec[idx] += 1.0
    norm = sum(v * v for v in vec) ** 0.5 or 1.0
    return [v / norm for v in vec]

def extract_pdf_content(file_path: str, doc_id: str) -> Dict[str, Any]:
    full_text_pages = []
    tables = []
    
    # 1. Extract text and page numbers with PyMuPDF
    doc = fitz.open(file_path)
    for idx, page in enumerate(doc):
        page_num = idx + 1
        p_text = page.get_text("text")
        full_text_pages.append({
            "page_num": page_num,
            "text": p_text
        })
    doc.close()
    
    # 2. Extract tables with pdfplumber
    try:
        with pdfplumber.open(file_path) as pdf:
            for idx, page in enumerate(pdf.pages):
                page_num = idx + 1
                page_tables = page.extract_tables()
                for tbl in page_tables:
                    clean_tbl = [[cell.replace('\n', ' ').strip() if cell else '' for cell in row] for row in tbl]
                    if clean_tbl and len(clean_tbl) > 1:
                        tables.append({
                            "page_num": page_num,
                            "table_data": clean_tbl
                        })
    except Exception as e:
        print(f"pdfplumber table extraction warning for {file_path}: {e}")
        
    return {
        "pages": full_text_pages,
        "tables": tables
    }

def process_and_ingest_pdf(file_path: str, doc_id: str = None) -> Dict[str, Any]:
    if not doc_id:
        doc_id = str(uuid.uuid4())[:8]
        
    file_name = os.path.basename(file_path)
    
    # Generate page previews for source inspection UI
    generate_all_page_previews(file_path, doc_id)
    
    # Extract layout content
    parsed = extract_pdf_content(file_path, doc_id)
    full_text_combined = "\n".join([p["text"] for p in parsed["pages"]])
    
    # Extract metadata
    go_number = extract_go_number(full_text_combined) or f"GO/UNKNOWN/{doc_id}"
    department = extract_department(full_text_combined)
    date_raw, date_iso = extract_date(full_text_combined)
    abstract = extract_abstract(full_text_combined)
    financial_params = extract_financial_parameters(full_text_combined)
    
    # Extract references
    refs = extract_references_and_relations(full_text_combined, current_go=go_number)
    
    # Match existing target_doc_id for references in DB if present
    conn = get_db_connection()
    cursor = conn.cursor()
    for r in refs:
        cursor.execute("SELECT id FROM documents WHERE LOWER(go_number) = LOWER(?)", (r['target_go_number'],))
        row = cursor.fetchone()
        if row:
            r['target_doc_id'] = row['id']
    conn.close()
    
    # Construct metadata record
    doc_record = {
        "id": doc_id,
        "file_name": file_name,
        "file_path": file_path,
        "go_number": go_number,
        "department": department,
        "date_str": date_raw,
        "parsed_date": date_iso,
        "abstract": abstract,
        "financial_params": financial_params,
        "status": "CURRENT"
    }
    save_document(doc_record)
    save_references(doc_id, refs)
    
    # Create Chunks (Paragraphs & Tables)
    chunks = []
    
    # Page text chunks
    for p in parsed["pages"]:
        paragraphs = [para.strip() for para in p["text"].split("\n\n") if len(para.strip()) > 20]
        if not paragraphs and p["text"].strip():
            paragraphs = [p["text"].strip()]
            
        for p_idx, para in enumerate(paragraphs):
            c_id = f"{doc_id}_p{p['page_num']}_c{p_idx}"
            emb = generate_embedding(para)
            chunks.append({
                "id": c_id,
                "document_id": doc_id,
                "page_num": p["page_num"],
                "section": f"Page {p['page_num']} Paragraph {p_idx+1}",
                "chunk_type": "TEXT",
                "content": para,
                "go_number": go_number,
                "embedding": emb
            })
            
    # Table chunks
    for t_idx, tbl in enumerate(parsed["tables"]):
        headers = tbl["table_data"][0]
        md_table_rows = [" | ".join(headers), " | ".join(["---"] * len(headers))]
        for row in tbl["table_data"][1:]:
            md_table_rows.append(" | ".join(row))
        md_table_str = "\n".join(md_table_rows)
        
        c_id = f"{doc_id}_tbl_{t_idx}"
        tbl_content = f"TABLE (Page {tbl['page_num']}):\n{md_table_str}"
        emb = generate_embedding(tbl_content)
        chunks.append({
            "id": c_id,
            "document_id": doc_id,
            "page_num": tbl["page_num"],
            "section": f"Page {tbl['page_num']} Table",
            "chunk_type": "TABLE",
            "content": tbl_content,
            "go_number": go_number,
            "embedding": emb
        })
        
    save_chunks(chunks)
    
    return {
        "doc_id": doc_id,
        "go_number": go_number,
        "department": department,
        "date": date_iso,
        "references": refs,
        "chunk_count": len(chunks)
    }
