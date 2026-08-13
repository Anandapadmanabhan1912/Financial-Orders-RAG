import json
import re
from typing import List, Dict, Any, Optional
from backend.app.db import get_db_connection
from backend.app.ingestor import generate_embedding
from backend.app.version_engine import recompute_all_document_statuses, resolve_as_of_date
from backend.app.metadata_extractor import GO_PATTERN

def bm25_fts_search(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Performs full-text search (BM25 style) on chunks_fts.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if exact GO number exists in query
    exact_gos = GO_PATTERN.findall(query)
    
    clean_q = re.sub(r'[^\w\s]', ' ', query).strip()
    terms = [t for t in clean_q.split() if len(t) > 1]
    
    fts_query = " OR ".join(terms) if terms else query
    if exact_gos:
        # Boost exact GO identifier matching
        exact_go_term = exact_gos[0].replace('(', '').replace(')', '')
        fts_query = f'"{exact_gos[0]}" OR {fts_query}'
        
    results = []
    try:
        cursor.execute("""
        SELECT f.chunk_id, f.document_id, f.go_number, f.content, f.section, c.page_num, c.chunk_type, d.parsed_date, d.status, d.abstract
        FROM chunks_fts f
        JOIN chunks c ON f.chunk_id = c.id
        JOIN documents d ON f.document_id = d.id
        WHERE chunks_fts MATCH ?
        ORDER BY rank LIMIT ?
        """, (fts_query, limit))
        
        rows = cursor.fetchall()
        for idx, r in enumerate(rows):
            item = dict(r)
            item['score'] = 1.0 / (idx + 1)
            # Give massive boost to exact GO matches
            if exact_gos and any(g.lower() in item['content'].lower() or g.lower() in item['go_number'].lower() for g in exact_gos):
                item['score'] += 10.0
            results.append(item)
    except Exception as e:
        print(f"[DEBUG RETRIEVER ERROR] FTS search warning: {e}", flush=True)
        # Fallback keyword match
        cursor.execute("""
        SELECT c.id as chunk_id, c.document_id, c.page_num, c.section, c.chunk_type, c.content, d.go_number, d.parsed_date, d.status, d.abstract
        FROM chunks c
        JOIN documents d ON c.document_id = d.id
        WHERE c.content LIKE ? OR d.go_number LIKE ?
        LIMIT ?
        """, (f"%{query}%", f"%{query}%", limit))
        rows = cursor.fetchall()
        for idx, r in enumerate(rows):
            item = dict(r)
            item['score'] = 1.0 / (idx + 1)
            results.append(item)
            
    conn.close()
    return results

def vector_search(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Computes dense vector similarity between query and stored chunk embeddings.
    """
    q_emb = generate_embedding(query)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT c.id as chunk_id, c.document_id, c.page_num, c.section, c.chunk_type, c.content, c.embedding, d.go_number, d.parsed_date, d.status, d.abstract
    FROM chunks c
    JOIN documents d ON c.document_id = d.id
    WHERE c.embedding IS NOT NULL
    """)
    rows = cursor.fetchall()
    conn.close()
    
    candidates = []
    for r in rows:
        item = dict(r)
        if not item['embedding']:
            continue
        try:
            c_emb = json.loads(item['embedding'])
            # Cosine similarity
            dot = sum(a * b for a, b in zip(q_emb, c_emb))
            norm_q = sum(a * a for a in q_emb) ** 0.5 or 1.0
            norm_c = sum(b * b for b in c_emb) ** 0.5 or 1.0
            sim = dot / (norm_q * norm_c)
            item['sim_score'] = sim
            candidates.append(item)
        except Exception:
            continue
            
    candidates.sort(key=lambda x: x['sim_score'], reverse=True)
    return candidates[:limit]

def hybrid_retrieve(query: str, as_of_date: Optional[str] = None, top_k: int = 5) -> Dict[str, Any]:
    """
    Hybrid Retrieval pipeline using RRF (Reciprocal Rank Fusion) of BM25 + Vector Search.
    Filters/annotates results based on document status & as-of-date.
    """
    recompute_all_document_statuses()
    
    bm25_results = bm25_fts_search(query, limit=10)
    vector_results = vector_search(query, limit=10)
    
    # Reciprocal Rank Fusion (RRF)
    rrf_scores = {}
    chunk_map = {}
    
    for rank, item in enumerate(bm25_results, 1):
        c_id = item['chunk_id']
        rrf_scores[c_id] = rrf_scores.get(c_id, 0.0) + (1.0 / (60 + rank))
        chunk_map[c_id] = item
        chunk_map[c_id]['bm25_rank'] = rank
        
    for rank, item in enumerate(vector_results, 1):
        c_id = item['chunk_id']
        rrf_scores[c_id] = rrf_scores.get(c_id, 0.0) + (1.0 / (60 + rank))
        if c_id not in chunk_map:
            chunk_map[c_id] = item
        chunk_map[c_id]['vector_rank'] = rank
        
    # Sort merged candidates by RRF score
    sorted_chunks = sorted(rrf_scores.keys(), key=lambda cid: rrf_scores[cid], reverse=True)
    
    retrieved_items = []
    for cid in sorted_chunks:
        item = chunk_map[cid]
        item['rrf_score'] = rrf_scores[cid]
        
        # Apply as-of-date filter if provided
        if as_of_date and item['parsed_date']:
            if item['parsed_date'] > as_of_date:
                item['date_warning'] = f"Issued on {item['parsed_date']}, which is AFTER target date {as_of_date}."
                item['excluded_by_date'] = True
            else:
                item['excluded_by_date'] = False
        else:
            item['excluded_by_date'] = False
            
        retrieved_items.append(item)
        
    # Valid chunks (not excluded by as_of_date)
    valid_items = [it for it in retrieved_items if not it.get('excluded_by_date', False)]
    final_evidence = valid_items[:top_k] if valid_items else retrieved_items[:top_k]
    
    return {
        "query": query,
        "as_of_date": as_of_date,
        "bm25_count": len(bm25_results),
        "vector_count": len(vector_results),
        "total_candidates": len(retrieved_items),
        "evidence": final_evidence
    }
