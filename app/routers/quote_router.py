from fastapi import APIRouter, HTTPException, UploadFile, File
import os
import uuid

# --- Services ---
from app.pipeline.rag_pipeline import process_rfq_bundle
from app.config import UPLOAD_DIR

router = APIRouter(prefix="/quote", tags=["Quote Generation"])

os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/excel", summary="Upload and Generate Quote from Excel")
async def generate_quote_from_excel(
    file: UploadFile = File(..., description="Upload Excel (.xlsx or .xls)")
):
    try:
        # ✅ Validate
        if not file.filename.lower().endswith(('.xlsx', '.xls')):
            raise HTTPException(status_code=400, detail="Only Excel files allowed")

        # ✅ Prevent overwrite with UUID
        safe_filename = f"{uuid.uuid4()}_{os.path.basename(file.filename)}"
        file_path = os.path.join(UPLOAD_DIR, safe_filename)

        # ✅ Async-safe file saving
        content = await file.read()
        with open(file_path, "wb") as buffer:
            buffer.write(content)

        # ✅ Await async pipeline
        result = await process_rfq_bundle(
            project_name=f"Excel RFQ: {safe_filename}",
            file_paths=[file_path]
        )

        return {
            "status": "success",
            "file": safe_filename,
            "data": result
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Processing failed: {str(e)}"
        )

    finally:
        await file.close()
