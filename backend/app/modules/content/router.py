"""
Content router (FR-201 to FR-203).
Thin HTTP handlers: validate input, call one service function, shape the response.
All admin routes are strictly protected by require_role('administrator') (FR-103, NFR-06).
"""
import uuid
from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.dependencies import require_role
from app.modules.content.service import ContentService
from app.modules.content.schemas import (
    CourseCreate,
    CourseUpdate,
    CourseResponse,
    TopicCreate,
    TopicUpdate,
    TopicResponse,
    ContentItemCreate,
    ContentItemUpdate,
    ContentItemResponse,
    QuestionCreate,
    QuestionUpdate,
    QuestionResponse,
    TagCoverageReportResponse,
    CourseCatalogResponse,
    RetireResponse,
)

router = APIRouter(tags=["Content Management"])

# Dependency shortcut for admin role
admin_required = Depends(require_role("administrator"))


# ---------------- Courses Endpoints (FR-201) ----------------
@router.post("/admin/courses", response_model=CourseResponse, status_code=status.HTTP_201_CREATED, dependencies=[admin_required])
def create_course(payload: CourseCreate, db: Session = Depends(get_db)):
    """FR-201: Admin creates course."""
    return ContentService(db).create_course(payload)


@router.get("/admin/courses", response_model=List[CourseResponse], dependencies=[admin_required])
def list_courses(db: Session = Depends(get_db)):
    """FR-201: Admin lists all courses."""
    return ContentService(db).list_courses(include_retired=True)


@router.get("/admin/courses/{course_id}", response_model=CourseResponse, dependencies=[admin_required])
def get_course(course_id: uuid.UUID, db: Session = Depends(get_db)):
    """FR-201: Admin retrieves course by ID."""
    return ContentService(db).get_course(course_id)


@router.put("/admin/courses/{course_id}", response_model=CourseResponse, dependencies=[admin_required])
def update_course(course_id: uuid.UUID, payload: CourseUpdate, db: Session = Depends(get_db)):
    """FR-201: Admin updates course."""
    return ContentService(db).update_course(course_id, payload)


@router.delete("/admin/courses/{course_id}", response_model=RetireResponse, dependencies=[admin_required])
def retire_course(course_id: uuid.UUID, db: Session = Depends(get_db)):
    """FR-201: Admin retires course."""
    return ContentService(db).retire_course(course_id)


# ---------------- Topics Endpoints (FR-201, FR-202) ----------------
@router.post("/admin/topics", response_model=TopicResponse, status_code=status.HTTP_201_CREATED, dependencies=[admin_required])
def create_topic(payload: TopicCreate, db: Session = Depends(get_db)):
    """FR-201, FR-202: Admin creates topic."""
    return ContentService(db).create_topic(payload)


@router.get("/admin/courses/{course_id}/topics", response_model=List[TopicResponse], dependencies=[admin_required])
def list_topics(course_id: uuid.UUID, db: Session = Depends(get_db)):
    """FR-201: Admin lists topics for course."""
    return ContentService(db).get_topics_for_course(course_id, include_retired=True)


@router.put("/admin/topics/{topic_id}", response_model=TopicResponse, dependencies=[admin_required])
def update_topic(topic_id: uuid.UUID, payload: TopicUpdate, db: Session = Depends(get_db)):
    """FR-201: Admin updates topic."""
    return ContentService(db).update_topic(topic_id, payload)


@router.delete("/admin/topics/{topic_id}", response_model=RetireResponse, dependencies=[admin_required])
def retire_topic(topic_id: uuid.UUID, db: Session = Depends(get_db)):
    """FR-201: Admin retires topic."""
    return ContentService(db).retire_topic(topic_id)


# ---------------- Content Items Endpoints (FR-201, FR-202) ----------------
@router.post("/admin/content", response_model=ContentItemResponse, status_code=status.HTTP_201_CREATED, dependencies=[admin_required])
def create_content_item(payload: ContentItemCreate, db: Session = Depends(get_db)):
    """FR-201, FR-202: Admin creates content item."""
    return ContentService(db).create_content_item(payload)


@router.get("/admin/content", response_model=List[ContentItemResponse], dependencies=[admin_required])
def list_content_items(db: Session = Depends(get_db)):
    """FR-201: Admin lists all content items."""
    return ContentService(db).get_all_content_items(include_retired=True)


@router.put("/admin/content/{content_id}", response_model=ContentItemResponse, dependencies=[admin_required])
def update_content_item(content_id: uuid.UUID, payload: ContentItemUpdate, db: Session = Depends(get_db)):
    """FR-201: Admin updates content item."""
    return ContentService(db).update_content_item(content_id, payload)


@router.delete("/admin/content/{content_id}", response_model=RetireResponse, dependencies=[admin_required])
def retire_content_item(content_id: uuid.UUID, db: Session = Depends(get_db)):
    """FR-201: Admin retires content item."""
    return ContentService(db).retire_content_item(content_id)


# ---------------- Questions Endpoints (FR-201, FR-602) ----------------
@router.post("/admin/questions", response_model=QuestionResponse, status_code=status.HTTP_201_CREATED, dependencies=[admin_required])
def create_question(payload: QuestionCreate, db: Session = Depends(get_db)):
    """FR-201: Admin creates question."""
    return ContentService(db).create_question(payload)


@router.get("/admin/questions/{question_id}", response_model=QuestionResponse, dependencies=[admin_required])
def get_question(question_id: uuid.UUID, db: Session = Depends(get_db)):
    """FR-201: Admin retrieves question."""
    return ContentService(db).get_question(question_id)


@router.put("/admin/questions/{question_id}", response_model=QuestionResponse, dependencies=[admin_required])
def update_question(question_id: uuid.UUID, payload: QuestionUpdate, db: Session = Depends(get_db)):
    """FR-201: Admin updates question."""
    return ContentService(db).update_question(question_id, payload)


@router.delete("/admin/questions/{question_id}", response_model=RetireResponse, dependencies=[admin_required])
def retire_question(question_id: uuid.UUID, db: Session = Depends(get_db)):
    """FR-201: Admin retires question."""
    return ContentService(db).retire_question(question_id)


# ---------------- Tag Coverage Report (FR-203) ----------------
@router.get("/admin/content/tag-coverage", response_model=TagCoverageReportResponse, dependencies=[admin_required])
def get_tag_coverage(db: Session = Depends(get_db)):
    """FR-203: Report content items missing required tags."""
    return ContentService(db).get_tag_coverage_report()


# ---------------- Public / Learner Course Catalog (Cached in Redis) ----------------
@router.get("/courses/{course_id}/catalog", response_model=CourseCatalogResponse)
def get_course_catalog(course_id: uuid.UUID, db: Session = Depends(get_db)):
    """Public / Learner catalog cached in Redis with PostgreSQL fallback."""
    return ContentService(db).get_course_catalog(course_id)
