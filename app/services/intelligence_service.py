import json
import logging
import re
import inspect
from typing import Dict
from app.brain.llm_service import ask_llm

logger = logging.getLogger(__name__)

class DocumentIntelligence:
    """
    Converts unstructured raw text from multiple document sources 
    into structured, machine-readable JSON requirements.
    """

    async def extract_structured_data(self, raw_text: str) -> Dict:
        """
        Sends raw text to the LLM and parses the result into a clean 
        Project/Items JSON structure.
        """
        prompt = """
        Extract the following attributes into a strict JSON format:
        - project (The name of the RFQ/Project)
        - items (A list containing: name, qty, specification)
        
        Input Text:
        {text}
        
        Return ONLY valid JSON. Do not include conversational text or markdown blocks.
        """

        raw_json_str = ""
        try:
            # 1. Prepare Prompt (Limit to avoid overflow)
            formatted_prompt = prompt.format(text=raw_text[:8000])

            # 2. Call LLM
            result = ask_llm(formatted_prompt, context="")
            if inspect.isawaitable(result):
                raw_json_str = await result
            else:
                raw_json_str = result

            if not raw_json_str or not raw_json_str.strip():
                raise ValueError("LLM returned an empty response")

            # 3. Clean LLM Output (Remove markdown if present)
            clean_json = raw_json_str.strip()

            # Extract JSON inside ```json ... ``` OR ``` ... ```
            match = re.search(r"```(?:json)?\s*(.*?)\s*```", clean_json, re.DOTALL)

            if match:
                clean_json = match.group(1)

            # 4. Parse JSON
            structured_data = json.loads(clean_json)

            return structured_data

        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing failed: {e}")
            logger.error(f"Raw LLM output: {raw_json_str}")
            raise ValueError("Invalid JSON returned from LLM")

        except Exception as e:
            logger.error(f"Error in extract_structured_data: {e}")
            raise