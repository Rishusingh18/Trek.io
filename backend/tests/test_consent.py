"""
Consent requirement tests adhering to FR-104 and NFR-07.
Tracking endpoints refuse requests until consent is recorded.
"""
import uuid
from fastapi.testclient import TestClient
from app.core.auth import create_access_token, get_password_hash
from app.modules.accounts.repository import AccountsRepository


def test_fr104_nfr07_tracking_refused_without_consent(client: TestClient, db_session):
    """Verify FR-104, NFR-07: Tracking endpoints refuse requests until learner records consent."""
    repo = AccountsRepository(db_session)
    user = repo.create_user("noconsent@test.com", get_password_hash("pass123"), "learner")
    token = create_access_token(user.user_id, role="learner")

    content_id = uuid.uuid4()
    payload = {
        "event_type": "opened",
        "duration": 45.0
    }

    # 1. Attempt tracking without consent -> 403 Forbidden with CONSENT_REQUIRED
    res = client.post(
        f"/v1/content/{content_id}/events",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 403
    data = res.json()
    assert data["error"]["code"] == "CONSENT_REQUIRED"
    assert "consent" in data["error"]["message"].lower()

    # 2. Record consent via POST /v1/me/consent (FR-104)
    consent_res = client.post(
        "/v1/me/consent",
        json={"consent_given": True},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert consent_res.status_code == 200
    consent_data = consent_res.json()
    assert consent_data["consent_recorded"] is True
    assert consent_data["consent_at"] is not None

    # 3. Retry tracking endpoint -> 200 OK
    res_after = client.post(
        f"/v1/content/{content_id}/events",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res_after.status_code == 200
    event_data = res_after.json()
    assert event_data["event_type"] == "opened"
    assert event_data["user_id"] == str(user.user_id)
