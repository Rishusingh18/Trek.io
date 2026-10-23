"""
Content service (FR-201 to FR-203).
Public interface for content.
Caches catalog per course in Redis with expiry and database fallback (Redis rule).
"""
import uuid
import json
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from app.core.redis import get_redis_client
from app.core.logging import logger
from app.core.errors import NotFoundException
from app.modules.content.repository import ContentRepository
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
    TopicCatalogItem,
    RetireResponse,
)


class ContentService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = ContentRepository(db)

    def _invalidate_course_catalog_cache(self, course_id: uuid.UUID) -> None:
        """Invalidate Redis cache for course catalog on any catalog update."""
        cache_key = f"catalog:course:{course_id}"
        try:
            client = get_redis_client()
            client.delete(cache_key)
        except Exception as e:
            logger.warning(f"Failed to invalidate course catalog cache: {e}")

    # Course operations
    def create_course(self, payload: CourseCreate) -> CourseResponse:
        course = self.repo.create_course(title=payload.title, description=payload.description, instructor_id=payload.instructor_id)
        return CourseResponse.model_validate(course)

    def update_course(self, course_id: uuid.UUID, payload: CourseUpdate) -> CourseResponse:
        course = self.repo.update_course(
            course_id,
            title=payload.title,
            description=payload.description,
            instructor_id=payload.instructor_id
        )
        if not course:
            raise NotFoundException(f"Course {course_id} not found")
        self._invalidate_course_catalog_cache(course_id)
        return CourseResponse.model_validate(course)


    def retire_course(self, course_id: uuid.UUID) -> RetireResponse:
        course = self.repo.retire_course(course_id)
        if not course:
            raise NotFoundException(f"Course {course_id} not found")
        self._invalidate_course_catalog_cache(course_id)
        return RetireResponse(message="Course retired successfully", id=course_id, is_retired=True)

    def list_courses(self, include_retired: bool = False) -> List[CourseResponse]:
        courses = self.repo.list_courses(include_retired=include_retired)
        return [CourseResponse.model_validate(c) for c in courses]

    def get_course(self, course_id: uuid.UUID) -> CourseResponse:
        course = self.repo.get_course(course_id)
        if not course:
            raise NotFoundException(f"Course {course_id} not found")
        return CourseResponse.model_validate(course)

    # Topic operations
    def create_topic(self, payload: TopicCreate) -> TopicResponse:
        course = self.repo.get_course(payload.course_id)
        if not course:
            raise NotFoundException(f"Course {payload.course_id} not found")
        topic = self.repo.create_topic(
            course_id=payload.course_id,
            name=payload.name,
            prerequisite_topic_ids=payload.prerequisite_topic_ids
        )
        self._invalidate_course_catalog_cache(payload.course_id)
        return TopicResponse.model_validate(topic)

    def update_topic(self, topic_id: uuid.UUID, payload: TopicUpdate) -> TopicResponse:
        topic = self.repo.update_topic(
            topic_id=topic_id,
            name=payload.name,
            prerequisite_topic_ids=payload.prerequisite_topic_ids
        )
        if not topic:
            raise NotFoundException(f"Topic {topic_id} not found")
        self._invalidate_course_catalog_cache(topic.course_id)
        return TopicResponse.model_validate(topic)

    def retire_topic(self, topic_id: uuid.UUID) -> RetireResponse:
        topic = self.repo.retire_topic(topic_id)
        if not topic:
            raise NotFoundException(f"Topic {topic_id} not found")
        self._invalidate_course_catalog_cache(topic.course_id)
        return RetireResponse(message="Topic retired successfully", id=topic_id, is_retired=True)

    def get_topics_for_course(self, course_id: uuid.UUID, include_retired: bool = False) -> List[TopicResponse]:
        topics = self.repo.list_topics_for_course(course_id, include_retired=include_retired)
        return [TopicResponse.model_validate(t) for t in topics]

    # ContentItem operations
    def create_content_item(self, payload: ContentItemCreate) -> ContentItemResponse:
        topic = self.repo.get_topic(payload.topic_id)
        if not topic:
            raise NotFoundException(f"Topic {payload.topic_id} not found")
        item = self.repo.create_content_item(
            topic_id=payload.topic_id,
            title=payload.title,
            type_=payload.type,
            difficulty=payload.difficulty,
            duration=payload.duration,
            prerequisite_topic_ids=payload.prerequisite_topic_ids
        )
        self._invalidate_course_catalog_cache(topic.course_id)
        return ContentItemResponse.model_validate(item)

    def update_content_item(self, content_id: uuid.UUID, payload: ContentItemUpdate) -> ContentItemResponse:
        item = self.repo.update_content_item(
            content_id=content_id,
            title=payload.title,
            type_=payload.type,
            difficulty=payload.difficulty,
            duration=payload.duration,
            prerequisite_topic_ids=payload.prerequisite_topic_ids
        )
        if not item:
            raise NotFoundException(f"Content item {content_id} not found")
        topic = self.repo.get_topic(item.topic_id)
        if topic:
            self._invalidate_course_catalog_cache(topic.course_id)
        return ContentItemResponse.model_validate(item)

    def retire_content_item(self, content_id: uuid.UUID) -> RetireResponse:
        item = self.repo.retire_content_item(content_id)
        if not item:
            raise NotFoundException(f"Content item {content_id} not found")
        topic = self.repo.get_topic(item.topic_id)
        if topic:
            self._invalidate_course_catalog_cache(topic.course_id)
        return RetireResponse(message="Content item retired successfully", id=content_id, is_retired=True)

    def get_content_items_for_topic(self, topic_id: uuid.UUID, include_retired: bool = False) -> List[ContentItemResponse]:
        items = self.repo.list_content_items_by_topic(topic_id, include_retired=include_retired)
        return [ContentItemResponse.model_validate(i) for i in items]

    def get_all_content_items(self, include_retired: bool = False) -> List[ContentItemResponse]:
        items = self.repo.list_all_content_items(include_retired=include_retired)
        return [ContentItemResponse.model_validate(i) for i in items]

    # Question operations
    def create_question(self, payload: QuestionCreate) -> QuestionResponse:
        topic = self.repo.get_topic(payload.topic_id)
        if not topic:
            raise NotFoundException(f"Topic {payload.topic_id} not found")
        q = self.repo.create_question(
            topic_id=payload.topic_id,
            prompt=payload.prompt,
            difficulty=payload.difficulty,
            correct_answer=payload.correct_answer,
            options=payload.options
        )
        return QuestionResponse.model_validate(q)

    def update_question(self, question_id: uuid.UUID, payload: QuestionUpdate) -> QuestionResponse:
        q = self.repo.update_question(
            question_id=question_id,
            prompt=payload.prompt,
            difficulty=payload.difficulty,
            correct_answer=payload.correct_answer,
            options=payload.options
        )
        if not q:
            raise NotFoundException(f"Question {question_id} not found")
        return QuestionResponse.model_validate(q)

    def retire_question(self, question_id: uuid.UUID) -> RetireResponse:
        q = self.repo.retire_question(question_id)
        if not q:
            raise NotFoundException(f"Question {question_id} not found")
        return RetireResponse(message="Question retired successfully", id=question_id, is_retired=True)

    def get_questions_for_topic(self, topic_id: uuid.UUID, include_retired: bool = False) -> List[QuestionResponse]:
        questions = self.repo.get_questions_for_topic(topic_id, include_retired=include_retired)
        return [QuestionResponse.model_validate(q) for q in questions]

    def get_question(self, question_id: uuid.UUID) -> QuestionResponse:
        q = self.repo.get_question(question_id)
        if not q:
            raise NotFoundException(f"Question {question_id} not found")
        return QuestionResponse.model_validate(q)

    # Course Catalog with Redis Expiry and DB Fallback (Redis rule)
    def get_course_catalog(self, course_id: uuid.UUID) -> CourseCatalogResponse:
        cache_key = f"catalog:course:{course_id}"
        # 1. Try Redis cache
        try:
            client = get_redis_client()
            cached = client.get(cache_key)
            if cached:
                data = json.loads(cached)
                return CourseCatalogResponse(**data)
        except Exception as e:
            logger.warning(f"Redis cache lookup failed for course {course_id}: {e}")

        # 2. Fallback to PostgreSQL
        course = self.repo.get_course(course_id)
        if not course or course.is_retired:
            raise NotFoundException(f"Course {course_id} not found or retired")

        topics = self.repo.list_topics_for_course(course_id, include_retired=False)
        catalog_topics = []
        for t in topics:
            items = self.repo.list_content_items_by_topic(t.topic_id, include_retired=False)
            catalog_topics.append(
                TopicCatalogItem(
                    topic_id=t.topic_id,
                    name=t.name,
                    prerequisite_topic_ids=t.prerequisite_topic_ids,
                    content_items=[ContentItemResponse.model_validate(i) for i in items]
                )
            )

        catalog = CourseCatalogResponse(
            course_id=course.course_id,
            title=course.title,
            description=course.description,
            topics=catalog_topics
        )

        # 3. Store in Redis with TTL (3600 seconds)
        try:
            client = get_redis_client()
            client.set(cache_key, catalog.model_dump_json(), ex=3600)
        except Exception as e:
            logger.warning(f"Failed to cache course catalog in Redis: {e}")

        return catalog

    def get_tag_coverage_report(self) -> TagCoverageReportResponse:
        """FR-203: Report content items missing required tags or metadata."""
        all_items = self.repo.list_all_content_items(include_retired=False)
        missing: List[Any] = []
        for item in all_items:
            # Missing required tags: empty type, difficulty not in 1..5, duration <= 0, or empty topic
            if not item.type or item.difficulty < 1 or item.difficulty > 5 or item.duration <= 0 or not item.topic_id:
                missing.append(item)

        return TagCoverageReportResponse(
            total_items=len(all_items),
            missing_tag_items_count=len(missing),
            items_missing_tags=[ContentItemResponse.model_validate(m) for m in missing]
        )
