"""
RAG AI System - Query Pipeline
Implements the RAG (Retrieval-Augmented Generation) flow:
1. Embed the user's question.
2. Search the vector database for relevant chunks.
3. Build a context window for the LLM.
4. Generate a grounded answer based on the retrieved documents.
"""

import os
import logging
from typing import Dict, Any, List  

from app.brain.embedding_service import embed_query
from app.brain.llm_service import ask_llm
from app.brain.vector_service import vector_store 

logger = logging.getLogger(__name__)

def safe_get(d: dict, key: str, default=None):
    """Safely retrieves a key from a dictionary with a fallback."""
    try:
        return d.get(key, default)
    except Exception:
        return default

async def ask_rag(question: str, top_k: int = 8) -> Dict[str, Any]:
    """
    Orchestrates the full RAG query pipeline.
    """
    try:
        logger.info("RAG Query received: %s", question)

        # --------------------------------------------------
        # 1️⃣ STAGE: Generate embedding for the question
        # --------------------------------------------------
        embedding = await embed_query(question)

        # --------------------------------------------------
        # 2️⃣ STAGE: Hybrid retrieval from Vector Store
        # --------------------------------------------------
        # Performs both semantic and keyword search
        results = vector_store.hybrid_search(
            query=question, 
            query_embedding=embedding.tolist(), 
            top_k=top_k
        ) or []

        logger.info(f"Retrieved {len(results)} relevant document chunks.")

        if not results:
            return {
                "question": question,
                "answer": "No relevant information found in the documents.",
                "sources": [],
                "chunks_used": 0,
                "context_preview": ""
            }

        # --------------------------------------------------
        # 3️⃣ STAGE: Process results (Deduplication & Metadata)
        # --------------------------------------------------
        sources: List[str] = []
        context_parts: List[str] = []
        seen_texts = set()

        for r in results:
            text = safe_get(r, "text", "") or ""
            text = text.strip()

            # Skip empty or duplicate chunks
            if not text or text in seen_texts:
                continue

            seen_texts.add(text)
            context_parts.append(text)

            # Extract source filename from various possible metadata keys
            meta = safe_get(r, "metadata", {}) or {}
            source_path = (
                meta.get("source")
                or meta.get("file")
                or meta.get("file_path")
                or meta.get("file_name")
            )

            if isinstance(source_path, str):
                filename = os.path.basename(source_path.strip())
                if filename and filename.lower() not in ["unknown", "none"]:
                    if filename not in sources:
                        sources.append(filename)

        # --------------------------------------------------
        # 4️⃣ STAGE: Smart context building
        # --------------------------------------------------
        # Limit the context size to fit within the LLM's prompt window
        MAX_CONTEXT_CHARS = 4000
        context = ""
        chunks_used = 0

        for chunk in context_parts:
            if len(context) + len(chunk) > MAX_CONTEXT_CHARS:
                break
            context += chunk + "\n\n"
            chunks_used += 1

        # --------------------------------------------------
        # 5️⃣ STAGE: Context Guard
        # --------------------------------------------------
        # Check if the retrieved data is substantial enough
        if len(context.strip()) < 20: 
            logger.warning("⚠️ Weak context detected for query: %s", question)
            return {
                "question": question,
                "answer": "I found some data, but it's not enough to form a complete answer.",
                "sources": sources,
                "chunks_used": chunks_used,
                "context_preview": context[:500]
            }

        # --------------------------------------------------
        # 6️⃣ STAGE: Generate Answer via LLM
        # --------------------------------------------------
        answer = await ask_llm(question, context)
        logger.info("✅ Grounded answer generated successfully.")

        return {
            "question": question,
            "answer": answer,
            "sources": sources,
            "chunks_used": chunks_used,
            "context_preview": context[:500]
        }

    except Exception as e:
        logger.exception("❌ Query processing failed: %s", str(e))
        return {
            "question": question,
            "answer": "I encountered an error while analyzing the documents.",
            "error": str(e),
            "sources": [],
            "chunks_used": 0,
            "context_preview": ""
        }