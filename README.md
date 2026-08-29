
---

# 🤖 RFQ AI System — Document Intelligence & Conflict Engine

Automated extraction, vector indexing, and conflict detection for engineering documents (BOQ, Specs, CAD). The system normalizes multi-format inputs, builds embeddings, and runs RAG-style retrieval for QA and conflict analysis.

## Key Features (as implemented)
- Multi-source ingestion: `.pdf`, `.docx`, `.xlsx`/`.xls`, `.csv`, `.txt`, `.dwg`, `.dxf`.
- Document normalization + chunking: controlled by `CHUNK_SIZE` and `CHUNK_OVERLAP` in `app/config.py`.
- Embedding generation: uses `EMBEDDING_MODEL` (`text-embedding-3-large` by default) and the project's `embedding_service`.
- Vector store: FAISS-backed store implemented in `app/brain/vector_service.py` with persistence paths in `app/config.py`.
- Conflict detection: fuzzy name matching + quantity comparison implemented in `app/brain/conflict_engine.py`.
- Export & deliverables: PDF export using `fpdf2` and JSON deliverables saved under `deliverables/`.

## Technology & Requirements
- Backend: FastAPI
- Vector DB: FAISS (`faiss-cpu`)
- Embeddings / LLMs: OpenAI Python SDK (configurable via `OPENAI_MODEL`), default embedding model `text-embedding-3-large`.
- Parsers: PyMuPDF, pdfplumber, python-docx, ezdxf
- Excel processing: pandas + openpyxl
- PDF generation: fpdf2

See `requirements.txt` for the full dependency list.

## Config & Environment
Required environment variables (or set in a `.env` file):

- `OPENAI_API_KEY` — (required) OpenAI API key. The application will raise an error if missing (`app/config.py`).
- `OPENAI_MODEL` — optional, default: `gpt-4o-mini`.
- `EMBEDDING_MODEL` — optional, default: `text-embedding-3-large`.
- `UPLOAD_DIR`, `SAVE_DIR`, `DWG_TEMP_DIR` — optional overrides for storage directories.

Important defaults from `app/config.py`:

- `CHUNK_SIZE`: 1000
- `CHUNK_OVERLAP`: 200
- `MAX_UPLOAD_SIZE_MB`: 50
- `ALLOWED_FILE_TYPES`: `.docx, .pdf, .dwg, .dxf, .txt, .csv, .xlsx, .xls`
- FAISS index path: `${SAVE_DIR}/index.faiss`

## Installation
```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Running (development)
```bash
uvicorn app.main:app --reload --port 8008
```

- API docs: `http://127.0.0.1:8000/docs`
- Frontend (served by FastAPI if present): `http://127.0.0.1:8000/`

## Endpoints & Behavior (high level)
- `POST /upload` — accepts allowed file types, runs `process_document` (see `app/brain/document_service.py`), chunks, embeds, and indexes content.
- `POST /query` — RAG-style chat / retrieval (see `app/routers/query_router.py`).
- `GET /` — serves `app/web/index.html` if the `app/web` folder exists.
- `GET /docs` — automatic OpenAPI docs from FastAPI.

## Workflow (implemented)
1. Ingest uploaded files (Excel BOQ, PDFs, DOCX, CAD)
2. Normalize and chunk text via `chunk_service`
3. Generate embeddings via `embedding_service`
4. Index vectors into FAISS via `vector_service`
5. Run conflict detection using `conflict_engine.detect_conflicts`

## 💡 Example Queries

### 📌 Information Extraction

* "Summarize all uploaded RFQ documents"
* "List all equipment with quantities"
* "Extract fire safety requirements"

### ⚠️ Conflict Detection

* "Are there inconsistencies between BOQ and drawings?"
* "Compare M-F1 vs M-F2 drawings"

"# RFQ-Intelligence-Platform" 
