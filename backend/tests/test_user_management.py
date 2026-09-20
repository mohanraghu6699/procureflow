import logging

import pytest

from tests.helpers import email

TEMP = "Temp-pass-1"


def make_user(api, address="newbie@procureflow.com", role="REQUESTER", password=TEMP):
    r = api.c.post(
        "/api/auth/users",
        json={"name": "Newbie", "email": address, "password": password, "role": role},
        headers=api.h("admin"),
    )
    assert r.status_code == 201, r.text
    return r.json()


def sign_in(api, address, password):
    return api.c.post("/api/auth/login", json={"email": address, "password": password})


def bearer(api, address, password):
    r = sign_in(api, address, password)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def post(api, path, user="admin", **kwargs):
    return api.c.post(path, headers=api.h(user), **kwargs)


# ---------- a required password change ----------


def test_a_new_user_must_change_their_password_before_anything_else(api):
    created = make_user(api)
    assert created["must_change_password"] is True and created["is_active"] is True

    headers = bearer(api, "newbie@procureflow.com", TEMP)  # signing in is allowed
    blocked = api.c.get("/api/purchase-requests", headers=headers)
    assert blocked.status_code == 403
    assert blocked.json()["detail"] == "You must change your password before continuing"
    assert api.c.get("/api/dashboard/summary", headers=headers).status_code == 403
    assert api.c.post("/api/purchase-requests", json=api.pr_payload(), headers=headers).status_code == 403

    me = api.c.get("/api/auth/me", headers=headers)  # the two endpoints that stay open
    assert me.status_code == 200 and me.json()["must_change_password"] is True
    changed = api.c.post("/api/auth/me/password", json={"current_password": TEMP, "new_password": "My-own-pass-9"}, headers=headers)
    assert changed.status_code == 204

    assert api.c.get("/api/purchase-requests", headers=headers).status_code == 200  # same token, now unblocked
    assert api.c.get("/api/auth/me", headers=headers).json()["must_change_password"] is False


def test_seeded_and_existing_users_are_not_forced(api):
    for name in ("rohan", "sameer", "admin"):
        assert api.c.get("/api/auth/me", headers=api.h(name)).json()["must_change_password"] is False


def test_the_password_change_still_needs_the_current_password(api):
    make_user(api)
    headers = bearer(api, "newbie@procureflow.com", TEMP)
    wrong = api.c.post("/api/auth/me/password", json={"current_password": "not-it", "new_password": "My-own-pass-9"}, headers=headers)
    assert wrong.status_code == 400
    assert api.c.get("/api/purchase-requests", headers=headers).status_code == 403  # still blocked


# ---------- reset password ----------


def test_admin_resets_a_password_and_the_user_must_replace_it(api):
    rohan = api.w.user["rohan"]
    old_headers = api.h("rohan")
    assert api.c.get("/api/purchase-requests", headers=old_headers).status_code == 200

    r = post(api, f"/api/auth/users/{rohan}/reset-password", json={"new_password": "Temporary-77"})
    assert r.status_code == 200 and r.json()["must_change_password"] is True

    assert api.c.get("/api/purchase-requests", headers=old_headers).status_code == 403  # the live session is stopped too
    assert sign_in(api, email("rohan"), "Passw0rd!").status_code == 401  # the old password is gone
    headers = bearer(api, email("rohan"), "Temporary-77")
    assert api.c.get("/api/purchase-requests", headers=headers).status_code == 403
    api.c.post("/api/auth/me/password", json={"current_password": "Temporary-77", "new_password": "Chosen-by-rohan-1"}, headers=headers)
    assert sign_in(api, email("rohan"), "Chosen-by-rohan-1").status_code == 200


def test_reset_rules(api):
    rohan = api.w.user["rohan"]
    path = f"/api/auth/users/{rohan}/reset-password"
    assert post(api, path, json={"new_password": "abc"}).status_code == 422  # too short
    assert post(api, "/api/auth/users/missing/reset-password", json={"new_password": "Temporary-77"}).status_code == 404
    own = post(api, f"/api/auth/users/{api.w.user['admin']}/reset-password", json={"new_password": "Temporary-77"})
    assert own.status_code == 400 and "your own account" in own.json()["detail"]


# ---------- deactivate / reactivate ----------


def test_deactivating_blocks_sign_in_and_live_sessions_and_keeps_history(api):
    pr = api.create_pr("rohan").json()
    rohan = api.w.user["rohan"]
    live = api.h("rohan")

    r = post(api, f"/api/auth/users/{rohan}/deactivate")
    assert r.status_code == 200 and r.json()["is_active"] is False

    assert sign_in(api, email("rohan"), "Passw0rd!").status_code == 403
    assert api.c.get("/api/purchase-requests", headers=live).status_code == 401  # the session dies at once
    assert api.get_pr(pr["id"], "admin").json()["requester_name"] == "Rohan"  # history is untouched
    listed = {u["email"]: u for u in api.c.get("/api/auth/users", headers=api.h("admin")).json()}
    assert listed[email("rohan")]["is_active"] is False


def test_reactivating_restores_access(api):
    rohan = api.w.user["rohan"]
    post(api, f"/api/auth/users/{rohan}/deactivate")
    r = post(api, f"/api/auth/users/{rohan}/reactivate")
    assert r.status_code == 200 and r.json()["is_active"] is True
    assert sign_in(api, email("rohan"), "Passw0rd!").status_code == 200
    assert post(api, f"/api/auth/users/{rohan}/reactivate").status_code == 200  # harmless to repeat


def test_an_admin_cannot_deactivate_their_own_account(api):
    r = post(api, f"/api/auth/users/{api.w.user['admin']}/deactivate")
    assert r.status_code == 400 and "your own account" in r.json()["detail"]
    assert post(api, "/api/auth/users/missing/deactivate").status_code == 404
    assert post(api, "/api/auth/users/missing/reactivate").status_code == 404


# ---------- delete ----------


def test_a_user_with_no_activity_can_be_deleted_and_recreated(api):
    created = make_user(api, "typo@procureflow.com")
    r = api.c.delete(f"/api/auth/users/{created['id']}", headers=api.h("admin"))
    assert r.status_code == 204
    assert "typo@procureflow.com" not in {u["email"] for u in api.c.get("/api/auth/users", headers=api.h("admin")).json()}
    assert sign_in(api, "typo@procureflow.com", TEMP).status_code == 401
    assert make_user(api, "typo@procureflow.com", password="Second-try-9")["email"] == "typo@procureflow.com"  # the address is free again


def test_a_user_with_records_cannot_be_deleted(api):
    api.create_pr("rohan")
    r = api.c.delete(f"/api/auth/users/{api.w.user['rohan']}", headers=api.h("admin"))
    assert r.status_code == 400
    assert "has 2 records" in r.json()["detail"] and "deactivate" in r.json()["detail"]  # the PR and its creation history
    assert api.c.get("/api/auth/users", headers=api.h("admin")).status_code == 200


@pytest.mark.parametrize("action", ["approve", "order", "deliver"])
def test_any_kind_of_activity_blocks_deletion(api, action):
    pr = api.submitted_pr("priya")
    doer = "amit"
    if action == "approve":
        api.approve(pr["id"], doer)
    else:
        api.approve(pr["id"], "sameer")
        po = api.create_po(pr["id"], user=doer).json()
        if action == "deliver":
            api.deliver(po["id"], "IN_TRANSIT", user=doer)
    r = api.c.delete(f"/api/auth/users/{api.w.user[doer]}", headers=api.h("admin"))
    assert r.status_code == 400, f"{action}: {r.text}"


def test_a_cancelled_order_counts_as_activity_too(api):
    po = api.po_for("priya")
    api.c.post(f"/api/purchase-orders/{po['id']}/cancel", json={"reason": "Wrong vendor"}, headers=api.h("amit"))
    assert api.c.delete(f"/api/auth/users/{api.w.user['amit']}", headers=api.h("admin")).status_code == 400


def test_delete_rules(api):
    own = api.c.delete(f"/api/auth/users/{api.w.user['admin']}", headers=api.h("admin"))
    assert own.status_code == 400 and "your own account" in own.json()["detail"]
    assert api.c.delete("/api/auth/users/missing", headers=api.h("admin")).status_code == 404


# ---------- who may do it ----------


@pytest.mark.parametrize("who", ["rohan", "sameer"])
def test_only_admins_can_manage_users(api, who):
    target = api.w.user["priya"]
    for path in ("reset-password", "deactivate", "reactivate"):
        r = post(api, f"/api/auth/users/{target}/{path}", user=who, json={"new_password": "Temporary-77"})
        assert r.status_code == 403, path
    assert api.c.delete(f"/api/auth/users/{target}", headers=api.h(who)).status_code == 403
    assert api.c.get("/api/auth/users", headers=api.h(who)).status_code == 403


def test_unauthenticated_requests_are_refused(client):
    assert client.post("/api/auth/users/x/deactivate").status_code == 401
    assert client.delete("/api/auth/users/x").status_code == 401


# ---------- logging ----------


def test_administration_is_logged(api, caplog):
    caplog.set_level(logging.INFO, logger="procureflow")
    made = make_user(api, "logged@procureflow.com")
    post(api, f"/api/auth/users/{made['id']}/reset-password", json={"new_password": "Temporary-77"})
    post(api, f"/api/auth/users/{made['id']}/deactivate")
    post(api, f"/api/auth/users/{made['id']}/reactivate")
    api.c.delete(f"/api/auth/users/{made['id']}", headers=api.h("admin"))

    lines = [r.getMessage() for r in caplog.records if r.name == "procureflow.auth"]
    admin = email("admin")
    assert f"Password of logged@procureflow.com reset by {admin} (change required at next sign-in)" in lines
    assert f"User logged@procureflow.com deactivated by {admin}" in lines
    assert f"User logged@procureflow.com reactivated by {admin}" in lines
    assert f"User logged@procureflow.com deleted by {admin}" in lines
    assert "Temporary-77" not in " ".join(r.getMessage() for r in caplog.records)  # never the password
