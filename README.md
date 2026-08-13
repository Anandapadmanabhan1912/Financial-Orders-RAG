# ORDERWISE — Kerala Finance Government Order Knowledge Assistant

ORDERWISE is a version-aware Hybrid RAG assistant designed for government finance officials. It processes Kerala Finance Government Orders (GOs), extracts metadata and tables, traces amendment/supersession relationships across document versions, answers natural-language and exact GO queries with strict grounding, and displays exact PDF source evidence and page previews.

---

## Key Features

1. **Version-Aware DAG Relationship Engine**:
   - Detects references between government orders (`G.O.(Rt)No.5618/2026/FIN`, `G.O.(Ms)No.106/2026/FIN`, `G.O.(Ms)No.23/2022/FIN`).
   - Automatically builds a Directed Acyclic Graph (DAG) of document references.
   - Computes dynamic order statuses: `CURRENT`, `SUPERSEDED`, `AMENDED`, `HISTORICAL`, or `UNRESOLVED`.

2. **As-Of-Date Historical Validity Resolver**:
   - Resolves active rules as of any historical target date (e.g. querying KFC financial assistance limit as of `2023-01-01` vs `2026-08-01`).
   - Explains why newer orders issued after the target date were excluded.

3. **Hybrid Retrieval Pipeline**:
   - Dual-channel retrieval using SQLite FTS5 (BM25 keyword matching giving massive boost to exact GO identifiers) and dense vector embeddings (`sentence-transformers` / `all-MiniLM-L6-v2` / Gemini embeddings).
   - Reciprocal Rank Fusion (RRF) for candidate ranking and deduplication.

4. **Exact Metadata & Table Extraction**:
   - Page-by-page layout text extraction using PyMuPDF (`fitz`).
   - Structured table extraction preserving numerical row/column alignment using `pdfplumber`.
   - Automatic regex extraction of GO numbers, departments, issue dates, and financial parameters (budget allocations, monetary limits like `Rs. 100 Crore`, interest rates, schedule dates).

5. **Grounded RAG Assistant**:
   - Integrates with the official `google-genai` SDK using `gemini-3.6-flash` (`client.interactions.create`).
   - Supports Hugging Face Inference API via `openai` client compatible router (`https://router.huggingface.co/v1`).
   - Includes a structured offline failsafe generator when API keys are unconfigured.

6. **Interactive UI & Source Inspection Drawer**:
   - Modern Vanilla HTML5/CSS3/JS single-page web app.
   - Grounded RAG Chat console with As-Of-Date datepicker, tool execution trace dropdown, and formatted Markdown rendering via Marked.js.
   - Document repository list with status badges (`CURRENT`, `SUPERSEDED`, `AMENDED`), financial parameters cards, and version DAG history.
   - Drag-and-drop PDF ingestion dropzone.
   - Side drawer displaying exact PDF page preview PNG snapshots.

---

## Technology Stack

- **Backend**: Python 3.9+, FastAPI, Uvicorn
- **Database & Search**: SQLite with FTS5 virtual table + JSON metadata storage
- **Vector Embeddings**: `sentence-transformers` (`all-MiniLM-L6-v2`) / FAISS / Gemini Embeddings
- **PDF Processing**: `PyMuPDF` (`fitz`), `pdfplumber`, `reportlab` (for seed PDF generation)
- **AI / LLM Integrations**:
  - `google-genai` SDK (`gemini-3.6-flash`)
  - `openai` SDK (`router.huggingface.co/v1`)
- **Frontend**: Vanilla HTML5, CSS3, JavaScript ES6, `Marked.js` (for client-side Markdown rendering)

---

## Directory Structure

```
orderwise/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI REST server & static hosting
│   │   ├── config.py                # Environment configuration loader
│   │   ├── db.py                    # SQLite database schema, FTS5 & CRUD
│   │   ├── ingestor.py              # PDF text, table & chunking ingestion pipeline
│   │   ├── metadata_extractor.py    # GO regex, dates, departments & reference parser
│   │   ├── version_engine.py        # Reference DAG graph & As-Of-Date resolver
│   │   ├── hybrid_retriever.py      # BM25 FTS + Vector Search + RRF fusion
│   │   ├── llm_service.py           # Grounded RAG response generator
│   │   └── pdf_utils.py             # PDF page PNG preview renderer
│   └── seed_data/
│       └── generate_seed_gos.py     # Sample Kerala Finance GO PDF generator
├── frontend/
│   ├── index.html                   # Main single-page web application UI
│   ├── css/
│   │   └── style.css                # Custom CSS styling system
│   └── js/
│       ├── app.js                   # Application manager, upload dropzone & repository
│       └── chat.js                  # Interactive chat, markdown renderer & source drawer
├── data/                            # Runtime database, PDF uploads & page preview images
├── mock_data/                       # Sample pre-populated mock dataset & database
├── .env                             # Environment variables configuration
├── .gitignore                       # Git ignore configuration
├── requirements.txt                 # Backend Python package requirements
├── run.bat                          # One-click Windows launch script
└── run.sh                           # One-click Unix launch script
```

---

## Quick Start & Setup

### Option A: One-Click Launch Scripts

- **Windows**: Double-click `run.bat` or execute in command prompt:
  ```cmd
  run.bat
  ```

- **Linux / macOS**: Execute in shell:
  ```bash
  chmod +x run.sh
  ./run.sh
  ```

### Option B: Manual Setup

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Environment Variables** (Optional API keys):
   Edit `.env` in the root folder:
   ```env
   GEMINI_API_KEY=your_gemini_api_key_here
   HF_TOKEN=your_huggingface_token_here
   PORT=8000
   HOST=127.0.0.1
   DATA_DIR=data
   DB_PATH=data/orderwise.db
   ```

3. **Generate Seed Government Order PDFs**:
   ```bash
   python backend/seed_data/generate_seed_gos.py
   ```

4. **Launch Backend Server**:
   ```bash
   python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
   ```

5. **Open Web Interface**:
   Access the web app in your browser at:
   ```text
   http://127.0.0.1:8000
   ```

---

## API Endpoints

- `GET /`: Serves the frontend web interface.
- `GET /api/documents`: Lists all ingested GO documents with active version statuses (`CURRENT`, `SUPERSEDED`, `AMENDED`).
- `GET /api/documents/{doc_id}`: Retrieves complete document metadata, tables, and version DAG chain.
- `GET /api/documents/{doc_id}/preview/{page}`: Serves rendered PNG preview snapshot of PDF page.
- `POST /api/upload`: Uploads a custom PDF document and triggers the ingestion pipeline.
- `POST /api/chat`: Processes grounded RAG query (accepts query text + optional `as_of_date`), returning formatted answer, sources, tool trace, and warnings.
- `POST /api/as-of-date`: Evaluates document version statuses active on a target date.

---

## Disclaimer

ORDERWISE is an administrative reference assistant. It does not make autonomous financial decisions. Always verify official government orders with the issuing department authority before taking administrative or financial action.
