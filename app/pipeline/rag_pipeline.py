import os
import re
import json
import logging
import datetime
from pathlib import Path
from typing import List, Dict, Any

from app.brain.document_service import process_document
from app.extraction.bom_extractor import extract_bom
from app.extraction.spec_extractor import extract_specs
from app.extraction.table_extractor import extract_tables
from app.services.cad_service import extract_dwg
from app.services.intelligence_service import DocumentIntelligence
from app.config import UPLOAD_DIR

# ⚠️ Make sure to import these missing functions from your other modules!
from app.services.excel_service import extract_boq_data 
from app.brain.conflict_engine import detect_conflicts, deduplicate_entities, normalize_entity

logger = logging.getLogger(__name__)

async def process_rfq(file_path: str):
    """
    Orchestrates the full RFQ Intelligence Pipeline:
    Extraction -> Vectorization -> Structured JSON Generation.
    """
    try:
        filename = os.path.basename(file_path)

        # 1. Extract Text & Store Vectors
        text = await process_document(file_path)
        if not text:
            raise ValueError("No text extracted from document")

        # 2. Structured Extraction (Document Intelligence Task)
        doc_intel = DocumentIntelligence()
        structured_data = await doc_intel.extract_structured_data(raw_text=text)

        # Save deliverable to local folder
        os.makedirs("deliverables", exist_ok=True)
        with open(f"deliverables/requirements_{filename}.json", "w") as f:
            json.dump(structured_data, f, indent=4)

        # 3. Component Extraction
        bom = extract_bom(text)
        specs = extract_specs(text)
        tables = extract_tables(text)

        # 4. Final Result Compilation
        result = {
            "status": "success",
            "source_file": filename,
            "project_name": structured_data.get("project", "Unknown"),
            "structured_items": structured_data.get("items", []),
            "bom": bom,
            "specifications": specs,
            "tables": tables,
        }

        # 5. Optional CAD summary
        if file_path.lower().endswith(".dwg"):
            cad_result = extract_dwg(file_path, output_dir=UPLOAD_DIR)
            result["cad_summary"] = cad_result.get("summary")

        return result

    except Exception as e:
        logger.error(f"❌ RFQ processing failed: {e}")
        return {"status": "error", "message": str(e)}
    

# ==========================================================
# 🚀 MULTI-FILE RFQ ORCHESTRATOR
# ==========================================================

async def process_rfq_bundle(project_name: str, file_paths: List[str]) -> Dict[str, Any]:
    """
    Master pipeline for 'Document Intelligence'. 
    Merges data from PDF, Word, and Excel and saves results to the deliverables folder.
    """
    logger.info(f"🚀 Starting Bundle processing for project: {project_name}")

    all_normalized_entities: List[Dict[str, Any]] = []
    processed_results: List[Dict[str, Any]] = []
    success_count = 0
    error_count = 0
    EXCEL_EXTS = {"xlsx", "xls"}

    # Ensure deliverables directory exists
    os.makedirs("deliverables", exist_ok=True)

    for i, raw_path in enumerate(file_paths):
        path = Path(raw_path)
        filename = path.name

        try:
            logger.info(f"Processing {i + 1}/{len(file_paths)}: {filename}")

            if not path.exists() or path.stat().st_size == 0:
                raise ValueError("File not found or empty")

            ext = path.suffix.lower().lstrip(".")
            entities: List[Dict[str, Any]] = []

            # 1️⃣ STAGE: Process Document (Text & Vectors)
            result = await process_rfq(str(path))
            
            if not result or result.get("status") == "error":
                raise ValueError(result.get("message", "Extraction error"))

            # Save individual JSON result
            with open(f"deliverables/requirements_{filename}.json", "w") as f:
                json.dump(result, f, indent=4)

            # 2️⃣ STAGE: Entity Extraction
            if ext in EXCEL_EXTS:
                boq_data = extract_boq_data(str(path))
                if isinstance(boq_data, list):
                    for row in boq_data:
                        if not isinstance(row, dict): continue
                        item = row.get("Item") or row.get("Description")
                        qty = row.get("Quantity") or row.get("Qty")
                        if item and qty:
                            entities.append(normalize_entity(item, qty, f"BOQ ({filename})", "BOQ", str(path)))
                status_msg = "processed as BOQ"
            else:
                # CAD Entities
                for entity in result.get("cad_entities", []):
                    if isinstance(entity, dict):
                        item_name = entity.get("item", "Unknown")
                        qty = entity.get("qty") or entity.get("quantity") or 1
                    else:
                        item_name = entity
                        qty = 1
                    entities.append(normalize_entity(item_name, qty, f"CAD ({filename})", "CAD", str(path)))
                
                # BOM Entities
                for item in result.get("bom", []):
                    if isinstance(item, dict):
                        entities.append(normalize_entity(item.get("item", "Unknown"), item.get("quantity"), f"Spec BOM ({filename})", "Spec BOM", str(path)))
                    else:
                        entities.append(normalize_entity(item, 1, f"Spec BOM ({filename})", "Spec BOM", str(path)))
                
                status_msg = "processed as unstructured"

            processed_results.append({"file": filename, "status": status_msg})
            all_normalized_entities.extend(entities)
            success_count += 1

        except Exception as e:
            logger.exception(f"Error processing file {filename}: {e}")
            processed_results.append({"file": filename, "status": "error", "message": str(e)})
            error_count += 1

    # 3️⃣ STAGE: Conflict Detection & Fallback
    all_normalized_entities = deduplicate_entities(all_normalized_entities)
    
    if not all_normalized_entities:
        logger.warning("⚠️ No entities extracted for the report context.")
        conflict_report = {"message": "No machine-readable entities found to analyze."}
    else:
        try:
            conflict_report = detect_conflicts(all_normalized_entities)
        except Exception as e:
            logger.error(f"Conflict detection failed: {e}")
            conflict_report = {"error": str(e)}

    # 4️⃣ STAGE: Final Master Report with Safe Filename
    safe_time = datetime.datetime.now().strftime("%H-%M-%S")
    safe_project = re.sub(r'[\\/*?:"<>|]', "", project_name)
    
    final_output = {
        "project_name": project_name,
        "timestamp": datetime.datetime.now().isoformat(),
        "summary": {"success": success_count, "errors": error_count},
        "file_details": processed_results,
        "engineering_analysis": conflict_report,
    }

    report_path = f"deliverables/{safe_project}_{safe_time}_Report.json"
    with open(report_path, "w") as f:
        json.dump(final_output, f, indent=4)

    logger.info(f"✅ Full Report saved successfully to {report_path}")
    return final_output