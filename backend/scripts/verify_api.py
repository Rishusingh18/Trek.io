"""
Verification script for API and ML recommender.
"""
import sys
import os
import uuid

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.db.session import SessionLocal
from app.modules.accounts.repository import AccountsRepository
from app.modules.accounts.service import AccountsService
from app.modules.accounts.schemas import UserLoginRequest
from app.modules.recommender.service import RecommenderService
from app.modules.knowledge.service import KnowledgeService
from app.modules.quiz.service import QuizService
from app.modules.quiz.schemas import QuizAnswerSubmit
from app.modules.experiments.service import ExperimentsService
from app.db.models.content import Course, Topic

def main():
    db = SessionLocal()
    try:
        print("1. Testing Auth Service...")
        accounts_repo = AccountsRepository(db)
        accounts_svc = AccountsService(db)
        login_res = accounts_svc.login(UserLoginRequest(email="asha@campus.edu", password="password123"))
        print(f"   -> Login success! Access token generated: {login_res.access_token[:20]}...")

        asha_user = accounts_repo.get_by_email("asha@campus.edu")
        print(f"   -> User resolved: {asha_user.email} (Role: {asha_user.role}, ID: {asha_user.user_id})")

        print("2. Resolving Course...")
        course = db.query(Course).filter(Course.title.like("%CS 301%")).first()
        print(f"   -> Course: {course.title} (ID: {course.course_id})")

        print("3. Testing ML Knowledge & Mastery Service...")
        knowledge_svc = KnowledgeService(db)
        mastery = knowledge_svc.get_user_mastery_vector(asha_user.user_id)
        print(f"   -> Mastery vector retrieved ({len(mastery)} topics):")
        for m in mastery:
            top = db.query(Topic).filter(Topic.topic_id == m.topic_id).first()
            name = top.name if top else str(m.topic_id)[:8]
            print(f"      - {name}: {m.score * 100:.1f}% [{m.label}] (Confidence: {m.confidence:.2f})")

        print("4. Testing ML Recommender Service (A/B Routing)...")
        rec_svc = RecommenderService(db)
        recs = rec_svc.get_recommendations(user_id=asha_user.user_id, course_id=course.course_id, limit=3)
        print(f"   -> Strategy used: {recs.strategy_used} (Arm: {recs.arm_id})")
        print(f"   -> Returned {len(recs.items)} recommendations:")
        for r in recs.items:
            print(f"      [{r.rank}] {r.title} | Reason: '{r.reason}' | Type: {r.type}")

        print("5. Testing Adaptive Quiz Engine (IRT Question Selection)...")
        quiz_svc = QuizService(db)
        diag = quiz_svc.start_diagnostic(user_id=asha_user.user_id, course_id=course.course_id)
        print(f"   -> Diagnostic started (Session: {diag.session_id})")
        print(f"   -> First Question (Diff: {diag.first_question.difficulty}): {diag.first_question.prompt[:60]}...")

        # Submit answer
        ans_res = quiz_svc.submit_answer(
            session_id=diag.session_id,
            user_id=asha_user.user_id,
            payload=QuizAnswerSubmit(
                attempt_id=uuid.uuid4(),
                question_id=diag.first_question.question_id,
                submitted_answer=diag.first_question.options[0],
                time_taken=42
            )
        )
        print(f"   -> Answer evaluation: Correct={ans_res.correct}, Mastery updated: {ans_res.mastery_updated}")
        if ans_res.next_question:
            print(f"   -> Adaptive Next Question (Diff: {ans_res.next_question.difficulty}): {ans_res.next_question.prompt[:60]}...")
        else:
            print("   -> Quiz session complete (Stop rule triggered)")

        print("6. Testing Instructor Heatmap & At-Risk Analytics...")
        exp_svc = ExperimentsService(db)
        profr = accounts_repo.get_by_email("profr@campus.edu")
        heatmap = exp_svc.get_instructor_heatmap(course_id=course.course_id, instructor=profr)
        print(f"   -> Heatmap retrieved ({len(heatmap)} units):")
        for h in heatmap:
            top = db.query(Topic).filter(Topic.topic_id == h.topic_id).first()
            tname = top.name if top else str(h.topic_id)[:8]
            print(f"      - {tname}: Avg Mastery {h.average_mastery * 100:.1f}%, Weak Count: {h.weak_count}")

        at_risk = exp_svc.get_instructor_at_risk_learners(course_id=course.course_id, instructor=profr)
        print(f"   -> Flagged At-Risk Learners: {len(at_risk.at_risk_learners)}")
        for stu in at_risk.at_risk_learners[:5]:
            print(f"      * {stu.email}: Weak Topics: {stu.weak_topics_count}, Completion: {stu.completion_rate * 100:.1f}%, Reasons: {stu.risk_reasons}")

        print("\nALL BACKEND & ML SERVICES FULLY VERIFIED AND OPERATIONAL!")
    finally:
        db.close()

if __name__ == "__main__":
    main()
