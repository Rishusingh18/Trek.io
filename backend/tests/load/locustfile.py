"""
Locust Load Test Suite for NFR-01 and NFR-02.

Requirements:
- NFR-01: GET /v1/courses/{id}/recommendations p95 latency < 500ms with 1,000 concurrent learners.
- NFR-02: GET /v1/instructor/courses/{id}/heatmap latency < 3.0s for 500-learner class.
"""
import os
import random
import uuid
from typing import List, Dict
from locust import HttpUser, task, between, events
from locust.runners import MasterRunner

# Pre-computed tokens can be injected via env or fetched at startup
from app.core.auth import create_access_token
from app.db.session import SessionLocal
from app.db.models.accounts import User
from app.db.models.content import Course


COURSE_ID: str = ""
LEARNER_TOKENS: List[str] = []
INSTRUCTOR_TOKEN: str = ""


@events.init.add_listener
def on_locust_init(environment, **kwargs):
    """
    Load seeded users and courses on locust initialization to ensure realistic load
    without benchmarking password-hashing latency.
    """
    global COURSE_ID, LEARNER_TOKENS, INSTRUCTOR_TOKEN

    db = SessionLocal()
    try:
        # 1. Fetch Primary Course
        course = db.query(Course).filter(Course.title == "Comprehensive Python Mastery").first()
        if not course:
            course = db.query(Course).first()

        if course:
            COURSE_ID = str(course.course_id)
        else:
            COURSE_ID = os.environ.get("LOAD_TEST_COURSE_ID", str(uuid.uuid4()))

        # 2. Fetch seeded instructor
        instructor = db.query(User).filter(User.role.in_(["instructor", "administrator"])).first()
        if instructor:
            INSTRUCTOR_TOKEN = create_access_token(instructor.user_id, role=instructor.role)
        else:
            dummy_inst_id = uuid.uuid4()
            INSTRUCTOR_TOKEN = create_access_token(dummy_inst_id, role="instructor")

        # 3. Fetch seeded learners (up to 1,000)
        learners = db.query(User).filter(User.role == "learner").limit(1000).all()
        if learners:
            LEARNER_TOKENS = [create_access_token(u.user_id, role="learner") for u in learners]
        else:
            # Fallback mock tokens for 1,000 concurrent learners
            LEARNER_TOKENS = [create_access_token(uuid.uuid4(), role="learner") for _ in range(1000)]

        print(f"[Locust Init] Loaded Course ID: {COURSE_ID}")
        print(f"[Locust Init] Generated {len(LEARNER_TOKENS)} learner tokens and instructor token.")
    except Exception as e:
        print(f"[Locust Init] Warning during DB setup: {e}. Using synthetic fallback tokens.")
        COURSE_ID = str(uuid.uuid4())
        INSTRUCTOR_TOKEN = create_access_token(uuid.uuid4(), role="instructor")
        LEARNER_TOKENS = [create_access_token(uuid.uuid4(), role="learner") for _ in range(1000)]
    finally:
        db.close()


class LearnerUser(HttpUser):
    """
    Simulates 1,000 concurrent learners requesting personalized recommendations (NFR-01).
    Target: p95 latency < 500 ms.
    """
    weight = 10  # 90%+ traffic is learners
    wait_time = between(0.1, 0.5)

    def on_start(self):
        # Assign a random learner identity from the 1,000 seeded pool
        if LEARNER_TOKENS:
            token = random.choice(LEARNER_TOKENS)
        else:
            token = create_access_token(uuid.uuid4(), role="learner")
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json"
        }

    @task(5)
    def get_recommendations(self):
        """NFR-01: GET /v1/courses/{id}/recommendations"""
        url = f"/v1/courses/{COURSE_ID}/recommendations"
        with self.client.get(url, headers=self.headers, name="GET /v1/courses/{id}/recommendations", catch_response=True) as res:
            if res.status_code == 200:
                res.success()
            else:
                res.failure(f"Status code {res.status_code}: {res.text[:200]}")


class InstructorUser(HttpUser):
    """
    Simulates instructors viewing class topic mastery heatmap for 500+ learners (NFR-02).
    Target: Response time < 3.0 seconds (read from precomputed rollups).
    """
    weight = 1  # 5-10% traffic
    wait_time = between(1.0, 3.0)

    def on_start(self):
        self.headers = {
            "Authorization": f"Bearer {INSTRUCTOR_TOKEN}",
            "Accept": "application/json"
        }

    @task(1)
    def get_course_heatmap(self):
        """NFR-02: GET /v1/instructor/courses/{id}/heatmap"""
        url = f"/v1/instructor/courses/{COURSE_ID}/heatmap"
        with self.client.get(url, headers=self.headers, name="GET /v1/instructor/courses/{id}/heatmap", catch_response=True) as res:
            if res.status_code == 200:
                res.success()
            else:
                res.failure(f"Status code {res.status_code}: {res.text[:200]}")
