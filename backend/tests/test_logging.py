import logging

import pytest

from tests.helpers import PASSWORD, email, iso_date


@pytest.fixture()
def logs(caplog):
    caplog.set_level(logging.DEBUG, logger="procureflow")
    return caplog


def messages(caplog, logger_name=None):
    return [
        r.getMessage()
        for r in caplog.records
        if r.name.startswith("procureflow") and (logger_name is None or r.name == f"procureflow.{logger_name}")
    ]


def test_every_response_carries_a_request_id(client):
    r = client.get("/api/health")
    assert len(r.headers["X-Request-ID"]) == 8
    assert client.get("/api/health").headers["X-Request-ID"] != r.headers["X-Request-ID"]


def test_requests_are_logged_with_status_and_duration(client, world, logs):
    client.get("/api/auth/me", headers=world.headers("rohan"))
    client.get("/api/auth/me")  # no token

    lines = messages(logs, "http")
    assert any("GET /api/auth/me -> 200" in line and " ms)" in line for line in lines)
    assert any("GET /api/auth/me -> 401" in line for line in lines)


def test_health_checks_only_log_at_debug(client, logs):
    logs.set_level(logging.INFO, logger="procureflow")
    client.get("/api/health")
    assert not any("/api/health" in line for line in messages(logs, "http"))


def test_login_events_are_logged_without_the_password(client, world, logs):
    client.post("/api/auth/login", json={"email": email("rohan"), "password": "totally-wrong-pw"})
    client.post("/api/auth/login", json={"email": email("rohan"), "password": PASSWORD})

    lines = messages(logs, "auth")
    assert f"Login failed for {email('rohan')}" in lines
    assert f"Login succeeded for {email('rohan')} (REQUESTER)" in lines
    everything = " ".join(r.getMessage() for r in logs.records)
    assert "totally-wrong-pw" not in everything and PASSWORD not in everything


def test_failed_logins_are_warnings(client, world, logs):
    client.post("/api/auth/login", json={"email": email("rohan"), "password": "nope-nope"})
    failed = [r for r in logs.records if r.name == "procureflow.auth"]
    assert failed and all(r.levelno == logging.WARNING for r in failed)


def test_workflow_events_are_logged(api, logs):
    po = api.po_for()
    api.deliver(po["id"], "DELIVERED", iso_date(0))

    pr_lines = messages(logs, "purchase_requests")
    assert any(f"{po['pr_number']} created by {email('rohan')}" in line for line in pr_lines)
    assert f"{po['pr_number']} submitted by {email('rohan')}" in pr_lines
    assert f"{po['pr_number']} approved by {email('sameer')}" in pr_lines

    assert any(line.startswith(f"{po['po_number']} created for {po['pr_number']}") for line in messages(logs, "purchase_orders"))
    delivery_lines = messages(logs, "deliveries")
    assert f"{po['po_number']} delivery marked DELIVERED by {email('sameer')}" in delivery_lines
    assert f"{po['po_number']} and {po['pr_number']} completed" in delivery_lines


def test_rejection_reason_is_logged(api, logs):
    pr = api.submitted_pr()
    api.reject(pr["id"], comment="Budget exceeded")
    assert f"{pr['pr_number']} rejected by {email('sameer')}: Budget exceeded" in messages(logs, "purchase_requests")


def test_refused_actions_are_not_logged_as_successes(api, logs):
    pr = api.create_pr().json()
    logs.clear()
    api.edit(pr["id"], amount=500)  # no-op edit is refused
    assert not any("edited" in line for line in messages(logs, "purchase_requests"))


def test_admin_changes_are_logged(api, logs):
    vendor_id = api.w.vendor["gulf"]
    api.c.delete(f"/api/master-data/vendors/{vendor_id}", headers=api.h("admin"))
    api.c.post(f"/api/master-data/vendors/{vendor_id}/reactivate", headers=api.h("admin"))

    lines = messages(logs, "master_data")
    assert f"Vendor Gulf Marine Supplies deactivated by {email('admin')}" in lines
    assert f"Vendor Gulf Marine Supplies reactivated by {email('admin')}" in lines
