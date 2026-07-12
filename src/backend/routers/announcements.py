"""
Announcement endpoints for the High School Management System API
"""

from datetime import date
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ..database import announcements_collection, teachers_collection

router = APIRouter(
    prefix="/announcements",
    tags=["announcements"]
)


class AnnouncementPayload(BaseModel):
    """Announcement create/update payload."""

    title: str = Field(..., min_length=3, max_length=120)
    message: str = Field(..., min_length=3, max_length=500)
    expiration_date: str = Field(..., description="YYYY-MM-DD")
    start_date: Optional[str] = Field(None, description="YYYY-MM-DD")


def validate_date_string(field_name: str, value: Optional[str]) -> None:
    """Validate date string format where value is provided."""
    if value is None:
        return
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} must be in YYYY-MM-DD format"
        ) from exc


def require_signed_in_user(teacher_username: Optional[str]) -> Dict[str, Any]:
    """Validate that a signed-in teacher exists."""
    if not teacher_username:
        raise HTTPException(
            status_code=401,
            detail="Authentication required for this action"
        )

    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Invalid teacher credentials")

    return teacher


def serialize_announcement(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize MongoDB announcement document for API responses."""
    return {
        "id": doc["_id"],
        "title": doc["title"],
        "message": doc["message"],
        "start_date": doc.get("start_date"),
        "expiration_date": doc["expiration_date"],
    }


@router.get("", response_model=List[Dict[str, Any]])
@router.get("/", response_model=List[Dict[str, Any]])
def get_active_announcements() -> List[Dict[str, Any]]:
    """Get currently active announcements for all users."""
    today = date.today().isoformat()
    query = {
        "expiration_date": {"$gte": today},
        "$or": [
            {"start_date": {"$exists": False}},
            {"start_date": None},
            {"start_date": {"$lte": today}}
        ]
    }

    items = announcements_collection.find(query).sort(
        [
            ("expiration_date", 1),
            ("_id", 1)
        ]
    )

    return [serialize_announcement(item) for item in items]


@router.get("/manage", response_model=List[Dict[str, Any]])
def get_all_announcements(teacher_username: Optional[str] = Query(None)) -> List[Dict[str, Any]]:
    """Get all announcements for management UI (requires sign-in)."""
    require_signed_in_user(teacher_username)

    items = announcements_collection.find({}).sort(
        [
            ("expiration_date", 1),
            ("_id", 1)
        ]
    )
    return [serialize_announcement(item) for item in items]


@router.post("", response_model=Dict[str, Any])
@router.post("/", response_model=Dict[str, Any])
def create_announcement(payload: AnnouncementPayload, teacher_username: Optional[str] = Query(None)) -> Dict[str, Any]:
    """Create a new announcement (requires sign-in)."""
    require_signed_in_user(teacher_username)

    validate_date_string("start_date", payload.start_date)
    validate_date_string("expiration_date", payload.expiration_date)

    if payload.start_date and payload.start_date > payload.expiration_date:
        raise HTTPException(status_code=400, detail="Start date cannot be after expiration date")

    announcement_id = str(uuid4())
    document = {
        "_id": announcement_id,
        "title": payload.title.strip(),
        "message": payload.message.strip(),
        "start_date": payload.start_date,
        "expiration_date": payload.expiration_date,
    }
    announcements_collection.insert_one(document)

    return serialize_announcement(document)


@router.put("/{announcement_id}", response_model=Dict[str, Any])
def update_announcement(
    announcement_id: str,
    payload: AnnouncementPayload,
    teacher_username: Optional[str] = Query(None)
) -> Dict[str, Any]:
    """Update an announcement by id (requires sign-in)."""
    require_signed_in_user(teacher_username)

    validate_date_string("start_date", payload.start_date)
    validate_date_string("expiration_date", payload.expiration_date)

    if payload.start_date and payload.start_date > payload.expiration_date:
        raise HTTPException(status_code=400, detail="Start date cannot be after expiration date")

    existing = announcements_collection.find_one({"_id": announcement_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Announcement not found")

    updated = {
        "title": payload.title.strip(),
        "message": payload.message.strip(),
        "start_date": payload.start_date,
        "expiration_date": payload.expiration_date,
    }
    announcements_collection.update_one({"_id": announcement_id}, {"$set": updated})

    return serialize_announcement({"_id": announcement_id, **updated})


@router.delete("/{announcement_id}")
def delete_announcement(announcement_id: str, teacher_username: Optional[str] = Query(None)) -> Dict[str, str]:
    """Delete an announcement by id (requires sign-in)."""
    require_signed_in_user(teacher_username)

    result = announcements_collection.delete_one({"_id": announcement_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")

    return {"message": "Announcement deleted"}