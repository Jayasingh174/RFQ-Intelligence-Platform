"""
RAG AI System - Query Router
The API gateway for the Chatbot. Receives JSON questions and returns
grounded AI answers based on the uploaded document context.
"""

import logging
from fastapi import APIRouter, HTTPException

# Import the logic and schemas
from app.pipeline.query_pipeline import ask_rag 
from app.models.query_model import QueryRequest, QueryResponse

# Configure logger for this module
logger = logging.getLogger(__name__)

# Define the router with its prefix and tags for Swagger documentation
router = APIRouter(prefix="/query", tags=["Query"])

# ==========================================
# 🚦 INTENT ROUTER HELPER  
# ==========================================
def detect_export_intent(question: str) -> str | None:
    question_lower = question.lower()
    # Includes Google Sheets and Spreadsheet support
    export_keywords = ["export", "download", "generate a report", "save as", "google sheet", "spreadsheet"]
    
    if any(kw in question_lower for kw in export_keywords):
        if "image" in question_lower or "png" in question_lower: return "image"
        if "html" in question_lower: return "html_table"
        # CSV handles "csv", "google sheet", and "spreadsheet"
        return "csv" 
        
    return None


# ==========================================
# 📦 STANDARD QUERY (JSON RESPONSE)
# ==========================================
@router.post("/ask", response_model=QueryResponse)
async def query_rag(request: QueryRequest):
    """
    Primary API Endpoint:
    1. Receives a user question via POST.
    2. Intercepts export/download intents (bypassing the LLM).
    3. Awaits the RAG (Retrieval-Augmented Generation) pipeline for standard chat.
    """
    try:
        logger.info(f"🔍 Processing user query: {request.question}")

        # 1. INTERCEPT: Check for Export Intent FIRST
        export_format = detect_export_intent(request.question)
        
        if export_format:
            logger.info(f"📥 Export Intent Detected. Routing to frontend download: {export_format}")
            # We must include "question" to satisfy the QueryResponse Pydantic model
            return {
                "question": request.question,  
                "answer": f"Preparing your {export_format.upper()} download now...",
                "sources": [],
                "action": "export",
                "export_format": export_format
            }

        # 2. STANDARD CHAT: Execute the normal query pipeline
        result = await ask_rag(question=request.question)

        # Ensure the dictionary result has the default 'chat' action and the original question
        if isinstance(result, dict):
            if "action" not in result:
                result["action"] = "chat"
            if "question" not in result:
                result["question"] = request.question

        return result

    except Exception as e:
        logger.error(f"❌ API Query Error: {str(e)}", exc_info=True)
        
        # Raise an HTTPException to provide a clean error message to the frontend
        raise HTTPException(
            status_code=500,
            detail=f"The AI query failed to process: {str(e)}"
        )