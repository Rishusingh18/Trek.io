"""
Role dependency and RBAC tests adhering to FR-102, FR-103, and NFR-06.
"""
from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient
from app.core.dependencies import require_role
from app.core.auth import create_access_token
from app.modules.accounts.repository import AccountsRepository
from app.core.auth import get_password_hash

# Test routes exercising require_role
rbac_test_router = APIRouter()


@rbac_test_router.get("/test/learner-only")
def learner_only_endpoint(user=Depends(require_role("learner"))):
    return {"message": "Hello learner", "user_id": str(user.user_id)}


@rbac_test_router.get("/test/admin-only")
def admin_only_endpoint(user=Depends(require_role("administrator"))):
    return {"message": "Hello admin", "user_id": str(user.user_id)}


def test_fr102_fr103_nfr06_role_dependency(client: TestClient, db_session):
    """Verify FR-102, FR-103, NFR-06: Endpoint permissions gated strictly by role."""
    from app.main import app
    app.include_router(rbac_test_router)

    repo = AccountsRepository(db_session)
    learner = repo.create_user("learner@test.com", get_password_hash("pass123"), "learner")
    admin = repo.create_user("admin@test.com", get_password_hash("pass123"), "administrator")

    learner_token = create_access_token(learner.user_id, role="learner")
    admin_token = create_access_token(admin.user_id, role="administrator")

    # 1. Learner accessing learner route -> 200 OK
    res = client.get("/test/learner-only", headers={"Authorization": f"Bearer {learner_token}"})
    assert res.status_code == 200

    # 2. Learner accessing admin route -> 403 Forbidden (FR-103)
    res = client.get("/test/admin-only", headers={"Authorization": f"Bearer {learner_token}"})
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "FORBIDDEN"

    # 3. Admin accessing admin route -> 200 OK
    res = client.get("/test/admin-only", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200

    # 4. Unauthenticated request -> 401 Unauthorized
    res = client.get("/test/admin-only")
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "UNAUTHORIZED"
