from openai import AsyncOpenAI
import logging

from app.config import (
    OPENAI_API_KEY,
    OPENAI_MODEL,
    OPENAI_TEMPERATURE,
    OPENAI_MAX_TOKENS,
)

logger = logging.getLogger(__name__)

client = AsyncOpenAI(api_key=OPENAI_API_KEY)

async def ask_llm(question: str, context: str = "", mode: str = "qa"):
    """
    Standardizes the LLM call. Adding 'mode' prevents the 
    unexpected keyword argument error.
    """
    # 1. Validation & Logging
    logger.info(f"Processing query. Context length: {len(context) if context else 0}")
    
    if not context or len(context.strip()) < 10:
        logger.warning("Empty context provided to LLM.")
        return "No relevant data found in uploaded documents. Please ensure your files contain readable text."

    try:
        # 2. Token Safety (Optimized for modern 128k context models)
        safe_context = context[:100000] 

        # 3. System Instructions (Updated for the RAG AI System)
        # 3. System Instructions (Enhanced for Engineering Data)
        system_prompt = (
            "You are an expert Engineering Assistant powering a RAG AI System.\n"
            "You will be provided with context chunks extracted from engineering documents, CAD drawings, and BOQs.\n\n"
            "INSTRUCTIONS:\n"
            "1. Answer strictly using the provided context. If the information is missing, "
            "state: 'Information not available in the documents.'\n"
            "2. Data may appear in pipe-delimited format (e.g., | Item | Qty |). Interpret these as tables.\n"
            "3. Cross-reference quantities across different context chunks if necessary.\n\n"
            "RULES:\n"
            "- Use markdown tables for any equipment or quantity lists.\n"
            "- Be highly precise with technical specs (tolerances, materials, etc.).\n"
            "- Maintain a professional, engineering-focused tone."
        )

        # 4. LLM Call
        response = await client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Context:\n{safe_context}\n\nQuestion: {question}"}
            ],
            temperature=OPENAI_TEMPERATURE,
            max_tokens=OPENAI_MAX_TOKENS,
        )

        # 5. Robust Extraction
        answer = response.choices[0].message.content

        if not answer or not answer.strip():
            return "Information not available in the documents."

        return answer.strip()

    except Exception as e:
        logger.error(f"LLM Integration Error: {str(e)}", exc_info=True)
        return "LLM processing failed. Please check API connectivity or model availability."