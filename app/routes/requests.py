from fastapi import APIRouter, HTTPException

from app.models import ProcurementRequest, StatusUpdate
from app.data.commodity_groups import COMMODITY_GROUPS
from app.services import database as db

router = APIRouter(prefix="/api", tags=["requests"])


@router.get("/commodity-groups")
async def get_commodity_groups():
    """Get all available commodity groups"""
    return COMMODITY_GROUPS

#Create a new procurement request(1-Parses the JSON body, 2-Validates it against the Pydantic model, 3-Returns 422 error if validation fails)
@router.post("/requests")
async def create_request_endpoint(request: ProcurementRequest):
    """Create a new procurement request"""
    return db.create_request(request.model_dump())

#Get all requests (for the "All Requests" tab).
@router.get("/requests")
async def get_requests():
    """Get all procurement requests"""
    return db.get_all_requests()

#Get a single request with all details + status history
@router.get("/requests/{request_id}")
async def get_request_endpoint(request_id: str):
    """Get a specific procurement request"""
    result = db.get_request(request_id)
    if not result:
        raise HTTPException(status_code=404, detail="Request not found")
    return result

#Update request status (Open → In Progress → Closed).
@router.patch("/requests/{request_id}/status")
async def update_status(request_id: str, update: StatusUpdate):
    """Update the status of a procurement request"""
    result = db.update_request_status(request_id, update.status)
    if not result:
        raise HTTPException(status_code=404, detail="Request not found")
    return result
