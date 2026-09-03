import io
import csv


def generate_conflict_csv(analysis_data: dict):
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["Item Name", "Conflict Status", "Source Quantities"])

    matrix = analysis_data.get("full_matrix") or analysis_data.get("conflict_details") or []

    for item in matrix:
        name = item.get("entity", "Unknown")
        status = "⚠️ CONFLICT" if item.get("conflict_detected") else "✅ MATCH"

        quantities = item.get("quantities", {})
        qty_string = " | ".join(
            [f"{source}: {qty}" for source, qty in quantities.items()]
        )

        writer.writerow([name, status, qty_string])

    output.seek(0)
    return output
