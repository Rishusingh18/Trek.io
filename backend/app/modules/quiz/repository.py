"""
Quiz repository.
Quiz module coordinates across content and knowledge service layers.
"""
from sqlalchemy.orm import Session


class QuizRepository:
    def __init__(self, db: Session):
        self.db = db
