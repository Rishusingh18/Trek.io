"""
Trek.io Unified Application Launcher
Integrates FastAPI Backend, ML Recommendation Engine, and Stitch Frontend Portal.
"""
import os
import sys
import argparse

# Add backend directory to sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.core.config import settings
from app.core.logging import setup_logging, logger
from app.db.session import engine, SessionLocal
from app.db.base import Base
import app.db.models


def check_and_seed_database():
    """
    Ensure database has initial seed data only when the database is completely empty (no users and no courses).
    When users exist, skip automatic seeding to preserve user data.
    """
    from app.db.models.content import Course
    from app.db.models.accounts import User
    db = SessionLocal()
    try:
        user_count = db.query(User).count()
        course_count = db.query(Course).count()
        if user_count == 0 and course_count == 0:
            print("[Trek.io] Database completely empty. Running initial automated seed...")
            from scripts.seed_stitch_demo import seed_stitch_data
            summary = seed_stitch_data(db)
            print(f"[Trek.io] Database initialized: {summary['topics']} topics, {summary['students']} cohort students.")
        else:
            first_course = db.query(Course).first()
            course_title = first_course.title if first_course else "None"
            print(f"[Trek.io] Database populated ({user_count} users, {course_count} courses). Active Course: {course_title}")
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Run Trek.io Unified Application")
    parser.add_argument("--host", default="0.0.0.0", help="Host address (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="Port (default: 8000)")
    parser.add_argument("--reload", action="store_true", default=False, help="Enable hot reload")
    parser.add_argument("--seed-only", action="store_true", default=False, help="Only seed database and exit")

    args = parser.parse_args()
    setup_logging()

    print("=" * 70)
    print("  TREK.IO — ACADEMIC MANAGEMENT PORTAL & ADAPTIVE LEARNING ENGINE")
    print("=" * 70)

    # 1. Initialize Database & Seed
    Base.metadata.create_all(bind=engine)

    if args.seed_only:
        print("[Trek.io] Explicit seed requested (--seed-only). Explicitly regenerating dataset...")
        from scripts.seed_stitch_demo import seed_stitch_data
        db = SessionLocal()
        try:
            summary = seed_stitch_data(db)
            print(f"[Trek.io] Dataset regenerated: {summary['topics']} topics, {summary['students']} cohort students. Exiting.")
        finally:
            db.close()
        return

    # Normal startup: check and safely seed only if database is completely empty
    check_and_seed_database()

    # 2. Launch FastAPI with Mounted Frontend
    print("\n[Trek.io] Starting unified server...")
    print(f"  * Web Portal:    http://localhost:{args.port}/")
    print(f"  * Portal Hub:    http://localhost:{args.port}/portal/index.html")
    print(f"  * API Docs:      http://localhost:{args.port}/docs")
    print(f"  * API Health:    http://localhost:{args.port}/health")
    print("=" * 70)

    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        app_dir=backend_dir,
        reload=args.reload
    )


if __name__ == "__main__":
    main()

