def extract_bom(text):
    """
    Extracts BOM (Bill of Materials) data from text with improved robustness.
    
    Handles:
    - Extra columns
    - Whitespace and casing
    - Non-numeric quantities (graceful failure)
    - Column headers (skipping)
    """
    parts = []

    for line in text.splitlines():
        line = line.strip()
        
        # Skip empty lines or lines without delimiters
        if not line or "|" not in line:
            continue

        # Split and clean cells
        cells = [c.strip() for c in line.split("|")]

        # Skip typical header rows
        if "part" in cells[0].lower() or "material" in cells[1].lower():
            continue

        # Validate structure: Need at least 3 columns
        if len(cells) >= 3:
            try:
                # Use a more flexible quantity check (handles "10.0" or " 10 ")
                raw_qty = cells[2].split()[0] # Take first part if '10 NO' or '10 kgs'
                qty = int(float(raw_qty))

                parts.append({
                    "part": cells[0],
                    "material": cells[1],
                    "qty": qty
                })
            except (ValueError, IndexError):
                # Log or skip rows that don't have a valid number in the 3rd column
                continue

    return parts