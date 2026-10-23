"""
Content entity models: Course, Topic, ContentItem, Question (SRS section 5.1, FR-201 to FR-203).
Supports retirement (is_retired) instead of deletion.
"""
import uuid
from typing import List, Optional
from sqlalchemy import String, Integer, Float, Text, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin


class Course(Base, TimestampMixin):
    """
    Course entity.
    Traces to FR-201.
    """
    __tablename__ = "courses"

    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_retired: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    instructor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True, index=True
    )

    topics: Mapped[List["Topic"]] = relationship("Topic", back_populates="course", cascade="all, delete-orphan")



class Topic(Base, TimestampMixin):
    """
    Topic entity belonging to a Course.
    Traces to FR-201, FR-202.
    """
    __tablename__ = "topics"

    topic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("courses.course_id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # List of prerequisite topic UUIDs stored as JSONB
    prerequisite_topic_ids: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    is_retired: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    course: Mapped["Course"] = relationship("Course", back_populates="topics")
    content_items: Mapped[List["ContentItem"]] = relationship("ContentItem", back_populates="topic", cascade="all, delete-orphan")
    questions: Mapped[List["Question"]] = relationship("Question", back_populates="topic", cascade="all, delete-orphan")


class ContentItem(Base, TimestampMixin):
    """
    Content item carrying topic, difficulty (1 to 5), type, estimated duration,
    and prerequisite topic IDs.
    Traces to FR-201, FR-202.
    """
    __tablename__ = "content_items"

    content_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("topics.topic_id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g., "video", "article", "exercise"
    difficulty: Mapped[int] = mapped_column(Integer, nullable=False)  # 1 to 5 scale
    duration: Mapped[int] = mapped_column(Integer, nullable=False)  # in seconds
    prerequisite_topic_ids: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    is_retired: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    topic: Mapped["Topic"] = relationship("Topic", back_populates="content_items")


class Question(Base, TimestampMixin):
    """
    Quiz question with difficulty, prompt, and correct answer.
    Traces to FR-201, FR-602, FR-603.
    """
    __tablename__ = "questions"

    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("topics.topic_id", ondelete="CASCADE"), nullable=False, index=True
    )
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    difficulty: Mapped[float] = mapped_column(Float, nullable=False)  # difficulty d in [0, 1]
    correct_answer: Mapped[str] = mapped_column(String(255), nullable=False)
    options: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    is_retired: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    topic: Mapped["Topic"] = relationship("Topic", back_populates="questions")
