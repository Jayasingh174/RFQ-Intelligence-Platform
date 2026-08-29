def extract_tables(text: str):
    """
    Groups adjacent pipe-delimited lines into structured table blocks.
    Returns: A list of lists, where each sub-list is a single table.
    """
    if not text:
        return []

    all_tables = []
    current_table = []

    for line in text.splitlines():
        line = line.strip()

        # Identify a table line (needs a pipe and a minimum length)
        if "|" in line and len(line) > 3:
            current_table.append(line)
        else:
            # If we were building a table and hit a non-table line, save it
            if current_table:
                all_tables.append(current_table)
                current_table = []

    # Final check to catch a table that ends at the very last line of text
    if current_table:
        all_tables.append(current_table)

    return all_tables