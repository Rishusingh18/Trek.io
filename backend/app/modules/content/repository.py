"""
Content repository (FR-201 to FR-203).
Only this file touches the content tables (courses, topics, content_items, questions).
Uses strictly parameterized SQLAlchemy queries.
"""
import uuid
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.db.models.content import Course, Topic, ContentItem, Question


class ContentRepository:
    def __init__(self, db: Session):
        self.db = db

    # Course operations
    def get_course(self, course_id: uuid.UUID) -> Optional[Course]:
        return self.db.execute(select(Course).where(Course.course_id == course_id)).scalar_one_or_none()

    def list_courses(self, include_retired: bool = False) -> List[Course]:
        stmt = select(Course)
        if not include_retired:
            stmt = stmt.where(Course.is_retired.is_(False))
        return list(self.db.execute(stmt).scalars().all())

    def create_course(self, title: str, description: Optional[str], instructor_id: Optional[uuid.UUID] = None) -> Course:
        course = Course(title=title, description=description, instructor_id=instructor_id, is_retired=False)
        self.db.add(course)
        self.db.commit()
        self.db.refresh(course)
        return course

    def update_course(
        self,
        course_id: uuid.UUID,
        title: Optional[str],
        description: Optional[str],
        instructor_id: Optional[uuid.UUID] = None
    ) -> Optional[Course]:
        course = self.get_course(course_id)
        if not course:
            return None
        if title is not None:
            course.title = title
        if description is not None:
            course.description = description
        if instructor_id is not None:
            course.instructor_id = instructor_id
        self.db.commit()
        self.db.refresh(course)
        return course


    def retire_course(self, course_id: uuid.UUID) -> Optional[Course]:
        course = self.get_course(course_id)
        if course:
            course.is_retired = True
            self.db.commit()
            self.db.refresh(course)
        return course

    # Topic operations
    def get_topic(self, topic_id: uuid.UUID) -> Optional[Topic]:
        return self.db.execute(select(Topic).where(Topic.topic_id == topic_id)).scalar_one_or_none()

    def list_topics_for_course(self, course_id: uuid.UUID, include_retired: bool = False) -> List[Topic]:
        stmt = select(Topic).where(Topic.course_id == course_id)
        if not include_retired:
            stmt = stmt.where(Topic.is_retired.is_(False))
        return list(self.db.execute(stmt).scalars().all())

    def create_topic(self, course_id: uuid.UUID, name: str, prerequisite_topic_ids: list) -> Topic:
        topic = Topic(course_id=course_id, name=name, prerequisite_topic_ids=prerequisite_topic_ids, is_retired=False)
        self.db.add(topic)
        self.db.commit()
        self.db.refresh(topic)
        return topic

    def update_topic(self, topic_id: uuid.UUID, name: Optional[str], prerequisite_topic_ids: Optional[list]) -> Optional[Topic]:
        topic = self.get_topic(topic_id)
        if not topic:
            return None
        if name is not None:
            topic.name = name
        if prerequisite_topic_ids is not None:
            topic.prerequisite_topic_ids = prerequisite_topic_ids
        self.db.commit()
        self.db.refresh(topic)
        return topic

    def retire_topic(self, topic_id: uuid.UUID) -> Optional[Topic]:
        topic = self.get_topic(topic_id)
        if topic:
            topic.is_retired = True
            self.db.commit()
            self.db.refresh(topic)
        return topic

    # ContentItem operations
    def get_content_item(self, content_id: uuid.UUID) -> Optional[ContentItem]:
        return self.db.execute(select(ContentItem).where(ContentItem.content_id == content_id)).scalar_one_or_none()

    def create_content_item(
        self,
        topic_id: uuid.UUID,
        title: str,
        type_: str,
        difficulty: int,
        duration: int,
        prerequisite_topic_ids: list
    ) -> ContentItem:
        item = ContentItem(
            topic_id=topic_id,
            title=title,
            type=type_,
            difficulty=difficulty,
            duration=duration,
            prerequisite_topic_ids=prerequisite_topic_ids,
            is_retired=False
        )
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def update_content_item(
        self,
        content_id: uuid.UUID,
        title: Optional[str] = None,
        type_: Optional[str] = None,
        difficulty: Optional[int] = None,
        duration: Optional[int] = None,
        prerequisite_topic_ids: Optional[list] = None
    ) -> Optional[ContentItem]:
        item = self.get_content_item(content_id)
        if not item:
            return None
        if title is not None:
            item.title = title
        if type_ is not None:
            item.type = type_
        if difficulty is not None:
            item.difficulty = difficulty
        if duration is not None:
            item.duration = duration
        if prerequisite_topic_ids is not None:
            item.prerequisite_topic_ids = prerequisite_topic_ids
        self.db.commit()
        self.db.refresh(item)
        return item

    def retire_content_item(self, content_id: uuid.UUID) -> Optional[ContentItem]:
        item = self.get_content_item(content_id)
        if item:
            item.is_retired = True
            self.db.commit()
            self.db.refresh(item)
        return item

    def list_content_items_by_topic(self, topic_id: uuid.UUID, include_retired: bool = False) -> List[ContentItem]:
        stmt = select(ContentItem).where(ContentItem.topic_id == topic_id)
        if not include_retired:
            stmt = stmt.where(ContentItem.is_retired.is_(False))
        return list(self.db.execute(stmt).scalars().all())

    def list_all_content_items(self, include_retired: bool = False) -> List[ContentItem]:
        stmt = select(ContentItem)
        if not include_retired:
            stmt = stmt.where(ContentItem.is_retired.is_(False))
        return list(self.db.execute(stmt).scalars().all())

    # Question operations
    def get_question(self, question_id: uuid.UUID) -> Optional[Question]:
        return self.db.execute(select(Question).where(Question.question_id == question_id)).scalar_one_or_none()

    def create_question(
        self,
        topic_id: uuid.UUID,
        prompt: str,
        difficulty: float,
        correct_answer: str,
        options: list
    ) -> Question:
        question = Question(
            topic_id=topic_id,
            prompt=prompt,
            difficulty=difficulty,
            correct_answer=correct_answer,
            options=options,
            is_retired=False
        )
        self.db.add(question)
        self.db.commit()
        self.db.refresh(question)
        return question

    def update_question(
        self,
        question_id: uuid.UUID,
        prompt: Optional[str] = None,
        difficulty: Optional[float] = None,
        correct_answer: Optional[str] = None,
        options: Optional[list] = None
    ) -> Optional[Question]:
        q = self.get_question(question_id)
        if not q:
            return None
        if prompt is not None:
            q.prompt = prompt
        if difficulty is not None:
            q.difficulty = difficulty
        if correct_answer is not None:
            q.correct_answer = correct_answer
        if options is not None:
            q.options = options
        self.db.commit()
        self.db.refresh(q)
        return q

    def retire_question(self, question_id: uuid.UUID) -> Optional[Question]:
        q = self.get_question(question_id)
        if q:
            q.is_retired = True
            self.db.commit()
            self.db.refresh(q)
        return q

    def get_questions_for_topic(self, topic_id: uuid.UUID, include_retired: bool = False) -> List[Question]:
        stmt = select(Question).where(Question.topic_id == topic_id)
        if not include_retired:
            stmt = stmt.where(Question.is_retired.is_(False))
        return list(self.db.execute(stmt).scalars().all())
