import sqlite3
from typing import Dict, Any, List, Optional
from datetime import datetime
from backend.app.db import get_db_connection, get_all_documents, update_document_status

def recompute_all_document_statuses():
    """
    Traverses references graph to update document statuses in DB.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Fetch all documents sorted by date ascending
    cursor.execute("SELECT id, go_number, date_str, parsed_date, status FROM documents ORDER BY parsed_date ASC")
    docs = [dict(r) for r in cursor.fetchall()]
    
    # Fetch all reference links
    cursor.execute("""
    SELECT r.source_doc_id, r.target_go_number, r.target_doc_id, r.relation_type, d.go_number as source_go, d.parsed_date as source_date
    FROM references_rel r
    JOIN documents d ON r.source_doc_id = d.id
    """)
    references = [dict(r) for r in cursor.fetchall()]
    conn.close()
    
    # Map GO number to document record
    go_to_doc = {}
    for d in docs:
        if d['go_number']:
            go_to_doc[d['go_number'].lower().strip()] = d
            
    # Track supersessions & amendments
    superseded_ids = set()
    amended_ids = set()
    
    for ref in references:
        target_go_key = ref['target_go_number'].lower().strip()
        rel_type = ref['relation_type']
        
        # If target GO is ingested in our system
        if target_go_key in go_to_doc:
            target_doc = go_to_doc[target_go_key]
            
            # Check date ordering: Source doc must be newer than target doc
            source_date = ref['source_date'] or ""
            target_date = target_doc['parsed_date'] or ""
            
            if source_date >= target_date:
                if rel_type in ["SUPERSEDES", "CONTINUATION"]:
                    superseded_ids.add(target_doc['id'])
                elif rel_type in ["AMENDS", "EXTENDS"]:
                    amended_ids.add(target_doc['id'])
                    
    # Update DB statuses
    for d in docs:
        doc_id = d['id']
        if doc_id in superseded_ids:
            new_status = "SUPERSEDED"
        elif doc_id in amended_ids:
            new_status = "AMENDED"
        else:
            new_status = "CURRENT"
            
        update_document_status(doc_id, new_status)
        d['status'] = new_status
        
    return docs

def get_version_chain_for_document(doc_id: str) -> Dict[str, Any]:
    """
    Returns the complete DAG version history for a given document.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
    target_doc = cursor.fetchone()
    if not target_doc:
        conn.close()
        return {}
    target_doc = dict(target_doc)
    
    # Find orders that reference this order (Newer orders modifying/superseding it)
    cursor.execute("""
    SELECT d.id, d.go_number, d.parsed_date, d.status, r.relation_type
    FROM references_rel r
    JOIN documents d ON r.source_doc_id = d.id
    WHERE LOWER(r.target_go_number) = LOWER(?) OR r.target_doc_id = ?
    ORDER BY d.parsed_date DESC
    """, (target_doc['go_number'], doc_id))
    newer_orders = [dict(r) for r in cursor.fetchall()]
    
    # Find orders that this order references (Older base orders)
    cursor.execute("""
    SELECT r.target_go_number, r.target_doc_id, r.relation_type, d.parsed_date, d.status
    FROM references_rel r
    LEFT JOIN documents d ON r.target_doc_id = d.id OR LOWER(r.target_go_number) = LOWER(d.go_number)
    WHERE r.source_doc_id = ?
    """, (doc_id,))
    older_orders = [dict(r) for r in cursor.fetchall()]
    
    conn.close()
    
    return {
        "document_id": doc_id,
        "go_number": target_doc['go_number'],
        "parsed_date": target_doc['parsed_date'],
        "status": target_doc['status'],
        "superseded_by_or_continued_in": newer_orders,
        "reads_or_modifies_prior": older_orders
    }

def resolve_as_of_date(as_of_date_str: str, subject_keywords: List[str] = None) -> List[Dict[str, Any]]:
    """
    Resolves which document versions were active on a given target date (YYYY-MM-DD).
    Filters out documents issued AFTER the target date.
    """
    recompute_all_document_statuses()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Fetch all documents issued ON OR BEFORE as_of_date_str
    cursor.execute("""
    SELECT * FROM documents 
    WHERE parsed_date <= ?
    ORDER BY parsed_date DESC
    """, (as_of_date_str,))
    rows = cursor.fetchall()
    valid_docs_as_of_date = [dict(r) for r in rows]
    
    # Find documents excluded (issued after target date)
    cursor.execute("""
    SELECT go_number, parsed_date, abstract FROM documents 
    WHERE parsed_date > ?
    """, (as_of_date_str,))
    excluded_docs = [dict(r) for r in cursor.fetchall()]
    
    conn.close()
    
    results = []
    for d in valid_docs_as_of_date:
        chain = get_version_chain_for_document(d['id'])
        # Check if superseded by an order ALSO issued on or before as_of_date_str
        superseded_before_date = False
        for n_ord in chain.get('superseded_by_or_continued_in', []):
            if n_ord['parsed_date'] and n_ord['parsed_date'] <= as_of_date_str:
                superseded_before_date = True
                break
                
        effective_status = "SUPERSEDED" if superseded_before_date else "ACTIVE_ON_TARGET_DATE"
        
        results.append({
            "document": d,
            "effective_status_as_of_date": effective_status,
            "excluded_future_orders": [e['go_number'] for e in excluded_docs]
        })
        
    return results
