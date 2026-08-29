import re

def extract_specs(text):
    """
    Extracts engineering specifications using flexible regex patterns.
    Handles variations like 'Material: Steel' or 'MATERIAL-ALUMINUM'.
    """
    specs = {}

    # Refined patterns:
    # 1. \s*[:\-=]\s* -> Handles colons, dashes, or equals signs
    # 2. ([^\n,;]+)    -> Stops at a new line, comma, or semicolon for cleaner values
    patterns = {
        "material": r"material\s*[:\-=]\s*([^\n,;]+)",
        "tolerance": r"tolerance\s*[:\-=]\s*([^\n,;]+)",
        "surface_finish": r"surface\s*finish\s*[:\-=]\s*([^\n,;]+)",
        "coating": r"coating\s*[:\-=]\s*([^\n,;]+)",
        "heat_treatment": r"heat\s*treatment\s*[:\-=]\s*([^\n,;]+)"
    }

    for key, pattern in patterns.items():
        # re.IGNORECASE (re.I) is crucial as CAD text is often ALL CAPS
        match = re.search(pattern, text, re.I)
        if match:
            # Clean up trailing periods or extra spaces
            value = match.group(1).strip().rstrip('.')
            specs[key] = value

    return specs