import os
import json
import logging

from app.brain.document_service import process_document
from app.extraction.bom_extractor import extract_bom
from app.extraction.spec_extractor import extract_specs
from app.extraction.table_extractor import extract_tables
from app.services.cad_service import extract_dwg, parse_dxf, summarize_dxf
from app.services.intelligence_service import DocumentIntelligence
from app.config import UPLOAD_DIR

logger = logging.getLogger(__name__)


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
