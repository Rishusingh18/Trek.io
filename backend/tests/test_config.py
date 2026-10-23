"""
Config service tests adhering to NFR-13, FR-807, and NFR-06.
"""
import uuid
from fastapi.testclient import TestClient
from app.core.auth import create_access_token, get_password_hash
from app.modules.accounts.repository import AccountsRepository


def setup_users(db_session):
    repo = AccountsRepository(db_session)
    suffix = uuid.uuid4().hex[:8]
    admin = repo.create_user(f"cfg_admin_{suffix}@test.com", get_password_hash("pass123"), "administrator")
    learner = repo.create_user(f"cfg_learner_{suffix}@test.com", get_password_hash("pass123"), "learner")
    instructor = repo.create_user(f"cfg_inst_{suffix}@test.com", get_password_hash("pass123"), "instructor")
    return {
        "admin_token": create_access_token(admin.user_id, role="administrator"),
        "learner_token": create_access_token(learner.user_id, role="learner"),
        "instructor_token": create_access_token(instructor.user_id, role="instructor"),
        "admin_id": admin.user_id,
    }


def test_nfr13_admin_config_update_and_audit_logging(client: TestClient, db_session):
    """
    Verify NFR-13: Admin updates weights, thresholds, learning rate, decay, stretch,
    quiz step rules, quiet period, and retention period without redeploying.
    Verify audit log records who made the change and when.
    """
    users = setup_users(db_session)
    admin_auth = {"Authorization": f"Bearer {users['admin_token']}"}

    # 1. Update ranking weights (w1..w4)
    weights_payload = {
        "key": "ranking_weights",
        "value": {"w1": 0.45, "w2": 0.25, "w3": 0.20, "w4": 0.10},
        "description": "Adjusted fit and gap weights"
    }
    w_res = client.put("/v1/admin/config", json=weights_payload, headers=admin_auth)
    assert w_res.status_code == 200
    assert w_res.json()["value"]["w1"] == 0.45

    # 2. Update thresholds (weak below 0.40, strong 0.80 or above)
    thresh_payload = {
        "key": "mastery_thresholds",
        "value": {"weak_below": 0.40, "strong_above": 0.80},
        "description": "Mastery classification thresholds"
    }
    t_res = client.put("/v1/admin/config", json=thresh_payload, headers=admin_auth)
    assert t_res.status_code == 200
    assert t_res.json()["value"]["weak_below"] == 0.40

    # 3. Update learning parameters (learning rate, decay rate, stretch)
    params_payload = {
        "key": "mastery_parameters",
        "value": {"learning_rate": 0.12, "decay_rate": 0.015, "stretch": 0.10},
        "description": "Mastery update and decay rates"
    }
    p_res = client.put("/v1/admin/config", json=params_payload, headers=admin_auth)
    assert p_res.status_code == 200

    # 4. Update quiz step rules and periods
    rules_payload = {
        "key": "quiz_and_periods",
        "value": {
            "step_up_correct_in_row": 3,
            "step_down_incorrect_in_row": 2,
            "dismissal_quiet_period_days": 7,
            "retention_period_days": 90
        },
        "description": "Quiz adaptive steps and retention windows"
    }
    r_res = client.put("/v1/admin/config", json=rules_payload, headers=admin_auth)
    assert r_res.status_code == 200

    # 5. Verify audit history records who changed what and when (NFR-13)
    audits_res = client.get("/v1/admin/config-audits", headers=admin_auth)
    assert audits_res.status_code == 200
    audits = audits_res.json()
    assert len(audits) >= 4

    # Verify admin_id is stamped
    latest_audit = audits[0]
    assert latest_audit["changed_by_user_id"] == str(users["admin_id"])
    assert "changed_at" in latest_audit
    assert latest_audit["new_value"] is not None


def test_nfr13_strategy_toggle(client: TestClient, db_session):
    """Verify FR-807 & NFR-13: Switch strategy on or off without redeploying."""
    users = setup_users(db_session)
    admin_auth = {"Authorization": f"Bearer {users['admin_token']}"}

    # Enable embeddings strategy
    toggle_res = client.put(
        "/v1/admin/strategies/embeddings",
        json={"enabled": True},
        headers=admin_auth
    )
    assert toggle_res.status_code == 200
    assert toggle_res.json()["value"]["embeddings"] is True

    # Disable collaborative strategy
    disable_res = client.put(
        "/v1/admin/strategies/collaborative",
        json={"enabled": False},
        headers=admin_auth
    )
    assert disable_res.status_code == 200
    assert disable_res.json()["value"]["collaborative"] is False


def test_config_forbidden_for_non_admin(client: TestClient, db_session):
    """Verify FR-103, NFR-06: Learner and instructor are forbidden from updating config."""
    users = setup_users(db_session)
    learner_auth = {"Authorization": f"Bearer {users['learner_token']}"}
    instructor_auth = {"Authorization": f"Bearer {users['instructor_token']}"}

    payload = {"key": "weights", "value": {"w1": 0.9}}

    # Learner forbidden
    res1 = client.put("/v1/admin/config", json=payload, headers=learner_auth)
    assert res1.status_code == 403
    assert res1.json()["error"]["code"] == "FORBIDDEN"

    res2 = client.put("/v1/admin/strategies/rules", json={"enabled": False}, headers=learner_auth)
    assert res2.status_code == 403

    # Instructor forbidden
    res3 = client.put("/v1/admin/config", json=payload, headers=instructor_auth)
    assert res3.status_code == 403

    res4 = client.get("/v1/admin/config-audits", headers=instructor_auth)
    assert res4.status_code == 403
