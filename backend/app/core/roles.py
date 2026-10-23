"""
Role-based access control definitions adhering to FR-102, FR-103, and NFR-06.
"""
from enum import Enum


class UserRole(str, Enum):
    LEARNER = "learner"
    INSTRUCTOR = "instructor"
    ADMINISTRATOR = "administrator"
