"""
RFQ AI System - Upload Router
Handles single and multi-file uploads. This is the entry point 
for the Document Intelligence & Structured Extraction pipeline.
"""

import os
import logging
import json
from typing import List
from fastapi import APIRouter, UploadFile, File, Form, HTTPException

# --- Core Pipelines ---
from app.pipeline.rag_pipeline import process_rfq, process_rfq_bundle
from app.models.rag_model import RFQRequest, RFQResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/upload", tags=["Upload"])

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ---------------------------------------------------------
# 1️⃣ SINGLE FILE PROCESSING
# ---------------------------------------------------------
@router.post("/process", response_model=RFQResponse)
async def process_single_rfq(request: RFQRequest):
    """
    Processes a single document already present on the server.
    Ideal for re-running analysis on a specific file.
    """
    try:
        file_path = request.file_path
        logger.info(f"Processing single file: {file_path}")

        # Await the main extraction pipeline
        result = await process_rfq(file_path)

        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))

        # 🔥 CORRECT PLACEMENT: Parse and structure the result data
        structured_items = json.loads(result.get("structured_items", "[]")) if isinstance(result.get("structured_items"), str) else (result.get("structured_items") or [])
        bom = json.loads(result.get("bom", "[]")) if isinstance(result.get("bom"), str) else (result.get("bom") or [])
        specifications = json.loads(result.get("specifications", "[]")) if isinstance(result.get("specifications"), str) else (result.get("specifications") or [])
        tables = json.loads(result.get("tables", "[]")) if isinstance(result.get("tables"), str) else (result.get("tables") or [])
        
        # Ensure all values are lists of dictionaries
        structured_items = structured_items if isinstance(structured_items, list) else []
        bom = bom if isinstance(bom, list) else []
        specifications = specifications if isinstance(specifications, list) else []
        tables = tables if isinstance(tables, list) else []
        
        return RFQResponse(
            status="success",
            message="Document processed and indexed successfully.",
            structured_items=structured_items,
            bom=bom,
            specifications=specifications,
            tables=tables
        )

    except Exception as e:
        logger.error(f"❌ Single-file processing failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------
# 2️⃣ MULTI-FILE BUNDLE UPLOAD (Document Intelligence Task)
# ---------------------------------------------------------
@router.post("/bundle")
async def upload_rfq_bundle(
    project_name: str = Form("New RFQ Project"),
    files: List[UploadFile] = File(...)
):
    """
    The 'Intelligence' Endpoint:
    1. Saves multiple files (PDF, XLSX, DOCX).
    2. Runs the cross-file engineering conflict detection.
    3. Returns structured JSON including the project requirements.
    """
    saved_filepaths = []
    
    try:
        # Step 1: Securely save all uploaded files to disk
        for file in files:
            if not file.filename:
                raise HTTPException(status_code=400, detail="File must have a valid filename")
            filepath = os.path.join(UPLOAD_DIR, file.filename)
            
            # Using async read to prevent blocking the server
            content = await file.read()
            with open(filepath, "wb") as buffer:
                buffer.write(content)
                
            saved_filepaths.append(filepath)
            logger.info(f"📁 Uploaded: {file.filename}")

        # Step 2: Trigger the Multi-Source Extraction Orchestrator
        logger.info(f"🚀 Analyzing bundle for project: {project_name}")
        
        pipeline_result = await process_rfq_bundle(
            project_name=project_name, 
            file_paths=saved_filepaths
        )

        # Step 3: Return the machine-readable JSON results
        return pipeline_result

    except Exception as e:
        logger.error(f"❌ Bundle processing failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Bundle analysis failed: {str(e)}")