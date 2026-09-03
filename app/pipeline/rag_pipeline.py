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
from app.services.cad_service import extract_dwg, parse_dxf, summarize_dxf
from app.services.intelligence_service import DocumentIntelligence
from app.services.excel_service import extract_boq_data
from app.brain.conflict_engine import detect_conflicts, deduplicate_entities, normalize_entity
from app.config import UPLOAD_DIR

logger = logging.getLogger(__name__)


# ==========================================================
# 📄 SINGLE-FILE RFQ PROCESSING
# ==========================================================
async def process_rfq(file_path: str):
    """
    Orchestrates the full RFQ Intelligence Pipeline:
    Extraction -> Vectorization -> Structured JSON Generation.
    """
    try:
        filename = os.path.basename(file_path)

        # --------------------------------------------------
        # 1️⃣ Extract text & store vectors
        # --------------------------------------------------
        # process_document() handles extraction, smart chunking (like the
        # Excel BOQ rows), embedding, and saving to VectorService.
        text = await process_document(file_path)

        if not text:
            raise ValueError("No text extracted from document")

        # --------------------------------------------------
        # 2️⃣ Structured extraction (LLM Document Intelligence task)
        # --------------------------------------------------
        doc_intel = DocumentIntelligence()
        structured_data = await doc_intel.extract_structured_data(raw_text=text)

        # Save deliverable to local folder
        os.makedirs("deliverables", exist_ok=True)
        with open(f"deliverables/requirements_{filename}.json", "w") as f:
            json.dump(structured_data, f, indent=4)

        # --------------------------------------------------
        # 3️⃣ Component extraction
        # --------------------------------------------------
        bom = extract_bom(text)
        specs = extract_specs(text)
        tables = extract_tables(text)

        # --------------------------------------------------
        # 4️⃣ Prepare result
        # --------------------------------------------------
        result = {
            "status": "success",
            "source_file": filename,
            "project_name": structured_data.get("project", "Unknown"),
            "structured_items": structured_data.get("items", []),
            "bom": bom,
            "specifications": specs,
            "tables": tables,
        }

        # --------------------------------------------------
        # 5️⃣ CAD processing (optional)
        # --------------------------------------------------
        if file_path.lower().endswith(".dwg"):
            cad_result = extract_dwg(file_path, output_dir=UPLOAD_DIR)
            result["cad_summary"] = cad_result.get("summary")
            result["cad_entities"] = cad_result.get("parsed_entities", {})

        elif file_path.lower().endswith(".dxf"):
            # .dxf files skip DWG→DXF conversion (already DXF) but still
            # need parsing so CAD entities reach the conflict engine, same
            # as .dwg files do.
            parsed_data = parse_dxf(file_path)
            result["cad_summary"] = summarize_dxf(parsed_data)
            result["cad_entities"] = parsed_data

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
    Merges data from PDF, Word, Excel, and CAD, and saves results to the
    deliverables folder.
    """
    logger.info(f"🚀 Starting Bundle processing for project: {project_name}")

    all_normalized_entities: List[Dict[str, Any]] = []
    processed_results: List[Dict[str, Any]] = []
    success_count = 0
    error_count = 0
    EXCEL_EXTS = {"xlsx", "xls"}

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

            # 1️⃣ STAGE: Process document (text, vectors, structured data, CAD)
            result = await process_rfq(str(path))

            if not result or result.get("status") == "error":
                raise ValueError(result.get("message", "Extraction error"))

            # Save individual JSON result
            with open(f"deliverables/requirements_{filename}.json", "w") as f:
                json.dump(result, f, indent=4)

            # Carry the extracted content through to the bundle response,
            # not just a status string — the frontend/API caller gets the
            # structured items, BOM, specs, tables, CAD summary per file.
            file_result: Dict[str, Any] = {
                "file": filename,
                "file_type": ext,
                "status": "processed",
                **{k: v for k, v in result.items() if k not in ("status",)}
            }

            # 2️⃣ STAGE: Entity extraction
            if ext in EXCEL_EXTS:
                boq_data = extract_boq_data(str(path))
                if isinstance(boq_data, list):
                    for row in boq_data:
                        if not isinstance(row, dict):
                            continue
                        item = row.get("Item") or row.get("Description")
                        qty = row.get("Quantity") or row.get("Qty")
                        if item and qty:
                            entities.append(normalize_entity(item, qty, f"BOQ ({filename})", "BOQ", str(path)))
                file_result["status"] = "processed as BOQ"
            else:
                # CAD entities — parse_dxf()/extract_dwg() return a dict
                # shaped {"entities": [...], "blocks": [...]}, not a flat
                # list. Only named block inserts (e.g. a "VALVE_A" symbol
                # placed N times) represent actual countable components —
                # raw LINE/CIRCLE/ARC entities have no item/quantity
                # semantics, so they're not useful to the conflict engine.
                cad_data = result.get("cad_entities") or {}
                cad_blocks = cad_data.get("blocks", []) if isinstance(cad_data, dict) else []

                for block in cad_blocks:
                    if isinstance(block, dict) and block.get("block_name"):
                        entities.append(normalize_entity(
                            block["block_name"], 1, f"CAD ({filename})", "CAD", str(path)
                        ))

                # BOM entities (from bom_extractor's pipe-delimited parsing)
                for item in result.get("bom", []) or []:
                    if isinstance(item, dict):
                        entities.append(normalize_entity(
                            item.get("part", "Unknown"), item.get("qty"),
                            f"Spec BOM ({filename})", "Spec BOM", str(path)
                        ))
                    else:
                        entities.append(normalize_entity(item, 1, f"Spec BOM ({filename})", "Spec BOM", str(path)))

                file_result["status"] = "processed as unstructured"

            if not entities:
                file_result["status"] += " (no entities found)"

            file_result["entities"] = entities
            processed_results.append(file_result)
            all_normalized_entities.extend(entities)
            success_count += 1

        except Exception as e:
            logger.exception(f"Error processing file {filename}: {e}")
            processed_results.append({
                "file": filename,
                "status": "error",
                "message": str(e),
                "entities": [],
            })
            error_count += 1

    # 3️⃣ STAGE: Conflict detection & fallback
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

    # 4️⃣ STAGE: Final master report with safe filename
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

    logger.info(f"✅ Full report saved successfully to {report_path}")
    return final_output
