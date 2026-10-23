"""
Content module schemas (FR-201 to FR-203).
"""
import uuid
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


# Course Schemas
class CourseCreate(BaseModel):
    title: str
    description: Optional[str] = None
    instructor_id: Optional[uuid.UUID] = None


class CourseUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    instructor_id: Optional[uuid.UUID] = None


class CourseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    course_id: uuid.UUID
    title: str
    description: Optional[str] = None
    instructor_id: Optional[uuid.UUID] = None
    is_retired: bool = False



# Topic Schemas
class TopicCreate(BaseModel):
    course_id: uuid.UUID
    name: str
    prerequisite_topic_ids: List[str] = []


class TopicUpdate(BaseModel):
    name: Optional[str] = None
    prerequisite_topic_ids: Optional[List[str]] = None


class TopicResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    topic_id: uuid.UUID
    course_id: uuid.UUID
    name: str
    prerequisite_topic_ids: list
    is_retired: bool = False


# ContentItem Schemas
class ContentItemCreate(BaseModel):
    topic_id: uuid.UUID
    title: str
    type: str  # video, article, exercise, etc.
    difficulty: int = Field(..., ge=1, le=5, description="Difficulty 1 to 5 scale")
    duration: int = Field(..., gt=0, description="Estimated duration in seconds")
    prerequisite_topic_ids: List[str] = []


class ContentItemUpdate(BaseModel):
    title: Optional[str] = None
    type: Optional[str] = None
    difficulty: Optional[int] = Field(None, ge=1, le=5)
    duration: Optional[int] = Field(None, gt=0)
    prerequisite_topic_ids: Optional[List[str]] = None


class ContentItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    content_id: uuid.UUID
    topic_id: uuid.UUID
    title: str
    type: str
    difficulty: int
    duration: int
    prerequisite_topic_ids: list = []
    is_retired: bool = False


# Question Schemas
class QuestionCreate(BaseModel):
    topic_id: uuid.UUID
    prompt: str
    difficulty: float = Field(..., ge=0.0, le=1.0, description="Difficulty d in [0, 1]")
    correct_answer: str
    options: list = []


class QuestionUpdate(BaseModel):
    prompt: Optional[str] = None
    difficulty: Optional[float] = Field(None, ge=0.0, le=1.0)
    correct_answer: Optional[str] = None
    options: Optional[list] = None


class QuestionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    question_id: uuid.UUID
    topic_id: uuid.UUID
    prompt: str
    difficulty: float
    correct_answer: str = ""
    options: list = []
    is_retired: bool = False


# Tag Coverage & Retirement Schemas
class TagCoverageReportResponse(BaseModel):
    """FR-203: Report content items missing required tags."""
    total_items: int
    missing_tag_items_count: int
    items_missing_tags: List[ContentItemResponse]


class RetireResponse(BaseModel):
    message: str
    id: uuid.UUID
    is_retired: bool


class TopicCatalogItem(BaseModel):
    topic_id: uuid.UUID
    name: str
    prerequisite_topic_ids: list
    content_items: List[ContentItemResponse]


class CourseCatalogResponse(BaseModel):
    course_id: uuid.UUID
    title: str
    description: Optional[str] = None
    topics: List[TopicCatalogItem]
