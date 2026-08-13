import sqlite3
import json
import os
from typing import Dict, Any, List, Optional
from backend.app.config import DB_PATH

def get_db_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Documents table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS documents (
        id TEXT PRIMARY KEY,
        file_name TEXT NOT NULL,
        file_path TEXT NOT NULL,
        go_number TEXT,
        department TEXT,
        date_str TEXT,
        parsed_date TEXT,
        abstract TEXT,
        financial_params TEXT,
        status TEXT DEFAULT 'CURRENT',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    
    # Chunks table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chunks (
        id TEXT PRIMARY KEY,
        document_id TEXT NOT NULL,
        page_num INTEGER NOT NULL,
        section TEXT,
        chunk_type TEXT DEFAULT 'TEXT',
        content TEXT NOT NULL,
        embedding TEXT,
        FOREIGN KEY (document_id) REFERENCES documents (id) ON DELETE CASCADE
    );
    """)
    
    # References relationship table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS references_rel (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_doc_id TEXT NOT NULL,
        target_go_number TEXT NOT NULL,
        target_doc_id TEXT,
        relation_type TEXT DEFAULT 'REFERENCES',
        raw_text TEXT,
        FOREIGN KEY (source_doc_id) REFERENCES documents (id) ON DELETE CASCADE
    );
    """)
    
    # FTS5 Virtual Table for Keyword Retrieval
    cursor.execute("""
    CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
        chunk_id UNINDEXED,
        document_id UNINDEXED,
        go_number,
        content,
        section
    );
    """)
    
    conn.commit()
    conn.close()

def save_document(doc_data: Dict[str, Any]):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
    INSERT OR REPLACE INTO documents (id, file_name, file_path, go_number, department, date_str, parsed_date, abstract, financial_params, status)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        doc_data['id'],
        doc_data['file_name'],
        doc_data['file_path'],
        doc_data.get('go_number'),
        doc_data.get('department'),
        doc_data.get('date_str'),
        doc_data.get('parsed_date'),
        doc_data.get('abstract'),
        json.dumps(doc_data.get('financial_params', {})),
        doc_data.get('status', 'CURRENT')
    ))
    conn.commit()
    conn.close()

def save_chunks(chunks: List[Dict[str, Any]]):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    for c in chunks:
        cursor.execute("""
        INSERT OR REPLACE INTO chunks (id, document_id, page_num, section, chunk_type, content, embedding)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            c['id'],
            c['document_id'],
            c['page_num'],
            c.get('section', ''),
            c.get('chunk_type', 'TEXT'),
            c['content'],
            json.dumps(c.get('embedding', [])) if c.get('embedding') else None
        ))
        
        # Populate FTS5 index
        cursor.execute("""
        INSERT INTO chunks_fts (chunk_id, document_id, go_number, content, section)
        VALUES (?, ?, ?, ?, ?)
        """, (
            c['id'],
            c['document_id'],
            c.get('go_number', ''),
            c['content'],
            c.get('section', '')
        ))
        
    conn.commit()
    conn.close()

def save_references(source_doc_id: str, refs: List[Dict[str, Any]]):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Clear existing references from this source doc
    cursor.execute("DELETE FROM references_rel WHERE source_doc_id = ?", (source_doc_id,))
    
    for r in refs:
        cursor.execute("""
        INSERT INTO references_rel (source_doc_id, target_go_number, target_doc_id, relation_type, raw_text)
        VALUES (?, ?, ?, ?, ?)
        """, (
            source_doc_id,
            r['target_go_number'],
            r.get('target_doc_id'),
            r.get('relation_type', 'REFERENCES'),
            r.get('raw_text', '')
        ))
        
    conn.commit()
    conn.close()

def get_all_documents() -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM documents ORDER BY parsed_date DESC")
    rows = cursor.fetchall()
    conn.close()
    
    res = []
    for r in rows:
        d = dict(r)
        d['financial_params'] = json.loads(d['financial_params']) if d.get('financial_params') else {}
        res.append(d)
    return res

def get_document_by_id(doc_id: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        d = dict(row)
        d['financial_params'] = json.loads(d['financial_params']) if d.get('financial_params') else {}
        return d
    return None

def update_document_status(doc_id: str, status: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE documents SET status = ? WHERE id = ?", (status, doc_id))
    conn.commit()
    conn.close()
