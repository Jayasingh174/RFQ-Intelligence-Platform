from fastapi import APIRouter, Body, Response

from app.services.export_service import generate_conflict_csv

router = APIRouter(prefix="/export", tags=["Export"])


@router.post("/conflicts")
async def export_conflicts_csv(analysis_data: dict = Body(...)):
    """
    Receives the JSON conflict report from the frontend and
    returns it as a downloadable CSV file.
    """
    output = generate_conflict_csv(analysis_data)

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="conflict_report.csv"'}
    )
