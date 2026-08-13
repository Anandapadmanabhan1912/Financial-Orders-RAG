import fitz  # PyMuPDF
import os
from pathlib import Path
from backend.app.config import PREVIEWS_DIR

def render_pdf_page_preview(pdf_path: str, doc_id: str, page_num: int) -> str:
    """
    Renders page_num (1-indexed) of pdf_path into a PNG image under PREVIEWS_DIR.
    Returns relative preview URL path.
    """
    os.makedirs(PREVIEWS_DIR / doc_id, exist_ok=True)
    out_img_path = PREVIEWS_DIR / doc_id / f"page_{page_num}.png"
    
    if out_img_path.exists():
        return f"/api/documents/{doc_id}/preview/{page_num}"
        
    try:
        doc = fitz.open(pdf_path)
        if 0 <= page_num - 1 < len(doc):
            page = doc[page_num - 1]
            pix = page.get_pixmap(dpi=150)
            pix.save(str(out_img_path))
        doc.close()
        return f"/api/documents/{doc_id}/preview/{page_num}"
    except Exception as e:
        print(f"Error rendering PDF page preview for {doc_id} page {page_num}: {e}")
        return ""

def generate_all_page_previews(pdf_path: str, doc_id: str):
    """
    Generates preview PNG images for all pages in the PDF.
    """
    try:
        doc = fitz.open(pdf_path)
        os.makedirs(PREVIEWS_DIR / doc_id, exist_ok=True)
        for idx in range(len(doc)):
            page_num = idx + 1
            out_img_path = PREVIEWS_DIR / doc_id / f"page_{page_num}.png"
            if not out_img_path.exists():
                pix = doc[idx].get_pixmap(dpi=150)
                pix.save(str(out_img_path))
        doc.close()
    except Exception as e:
        print(f"Error generating all previews for {doc_id}: {e}")
