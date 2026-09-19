from tests.helpers import PASSWORD, email


def login(client, name, password=PASSWORD):
    return client.post("/api/auth/login", json={"email": email(name), "password": password})


def test_login_returns_token_and_user(client, world):
    r = login(client, "rohan")
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["email"] == email("rohan")
    assert body["user"]["role"] == "REQUESTER"
    assert body["user"]["department_name"] == "Operations"


def test_login_rejects_wrong_password_and_unknown_user(client, world):
    assert login(client, "rohan", "wrong-password").status_code == 401
    assert login(client, "nobody").status_code == 401


def test_login_rejects_inactive_user(client, world, db):
    from app.models import User

    db.query(User).filter(User.email == email("rohan")).update({"is_active": False})
    db.commit()
    assert login(client, "rohan").status_code == 403


def test_protected_routes_need_a_valid_token(client, world):
    assert client.get("/api/auth/me").status_code == 401
    r = client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert r.status_code == 401


def test_me_returns_the_current_user(client, world):
    token = login(client, "sameer").json()["access_token"]
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["role"] == "APPROVER"


def test_change_password_flow(client, world):
    headers = world.headers("rohan")
    new_password = "Brand-new-1"

    wrong = client.post("/api/auth/me/password", json={"current_password": "nope", "new_password": new_password}, headers=headers)
    assert wrong.status_code == 400

    same = client.post("/api/auth/me/password", json={"current_password": PASSWORD, "new_password": PASSWORD}, headers=headers)
    assert same.status_code == 400

    ok = client.post("/api/auth/me/password", json={"current_password": PASSWORD, "new_password": new_password}, headers=headers)
    assert ok.status_code == 204
    assert login(client, "rohan", PASSWORD).status_code == 401
    assert login(client, "rohan", new_password).status_code == 200


def test_only_admin_can_create_and_list_users(client, world):
    payload = {"name": "New Person", "email": "new.person@procureflow.com", "password": "secret1", "role": "REQUESTER"}

    for name in ("rohan", "sameer"):
        assert client.post("/api/auth/users", json=payload, headers=world.headers(name)).status_code == 403
        assert client.get("/api/auth/users", headers=world.headers(name)).status_code == 403

    created = client.post("/api/auth/users", json=payload, headers=world.headers("admin"))
    assert created.status_code == 201
    assert created.json()["department_id"] is None  # a department is optional

    listed = client.get("/api/auth/users", headers=world.headers("admin"))
    assert "new.person@procureflow.com" in {u["email"] for u in listed.json()}

    new_login = client.post("/api/auth/login", json={"email": payload["email"], "password": "secret1"})
    assert new_login.status_code == 200


def test_duplicate_user_email_is_rejected(client, world):
    payload = {"name": "Clash", "email": email("rohan"), "password": "secret1", "role": "REQUESTER"}
    r = client.post("/api/auth/users", json=payload, headers=world.headers("admin"))
    assert r.status_code == 409
