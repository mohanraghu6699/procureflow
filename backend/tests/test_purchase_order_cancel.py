import logging

from tests.helpers import iso_date


def cancel(api, po_id, reason="Wrong vendor chosen", user="sameer"):
    return api.c.post(f"/api/purchase-orders/{po_id}/cancel", json={"reason": reason}, headers=api.h(user))


def get_po(api, po_id, user="admin"):
    return api.c.get(f"/api/purchase-orders/{po_id}", headers=api.h(user)).json()


def summary(api, user="admin"):
    return api.c.get("/api/dashboard/summary", headers=api.h(user)).json()


# ---------- the cancellation itself ----------


def test_an_approver_cancels_an_open_order_with_a_reason(api):
    po = api.po_for()
    r = cancel(api, po["id"], "Ordered from the wrong vendor")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "CANCELLED"
    assert body["cancel_reason"] == "Ordered from the wrong vendor"
    assert body["cancelled_by_name"] == "Sameer"
    assert body["cancelled_at"].endswith("+00:00")
    assert get_po(api, po["id"])["status"] == "CANCELLED"


def test_the_reason_is_required_and_trimmed(api):
    po = api.po_for()
    for blank in (None, "", "   "):
        r = api.c.post(f"/api/purchase-orders/{po['id']}/cancel", json={"reason": blank}, headers=api.h("sameer"))
        assert r.status_code == 400
        assert r.json()["detail"] == "A reason is required to cancel a purchase order"
    assert api.c.post(f"/api/purchase-orders/{po['id']}/cancel", json={}, headers=api.h("sameer")).status_code == 400
    assert get_po(api, po["id"])["status"] == "OPEN"
    assert cancel(api, po["id"], "  padded reason  ").json()["cancel_reason"] == "padded reason"


def test_only_approvers_and_admins_can_cancel(api):
    po = api.po_for("rohan")
    assert cancel(api, po["id"], user="rohan").status_code == 403  # the requester who owns the PR
    assert cancel(api, po["id"], user="priya").status_code == 403
    assert api.c.post(f"/api/purchase-orders/{po['id']}/cancel", json={"reason": "x"}).status_code == 401
    assert cancel(api, po["id"], user="amit").status_code == 200  # any approver, not only the creator
    assert get_po(api, po["id"])["cancelled_by_name"] == "Amit"


def test_admin_can_cancel_too(api):
    po = api.po_for()
    assert cancel(api, po["id"], user="admin").status_code == 200


def test_unknown_order(api):
    assert cancel(api, "missing").status_code == 404


def test_a_cancelled_order_cannot_be_cancelled_again(api):
    po = api.po_for()
    cancel(api, po["id"])
    r = cancel(api, po["id"])
    assert r.status_code == 400 and "already cancelled" in r.json()["detail"]


# ---------- what may not be cancelled ----------


def test_an_order_that_is_on_its_way_cannot_be_cancelled(api):
    for status in ("IN_TRANSIT", "PARTIAL"):
        po = api.po_for()
        api.deliver(po["id"], status)
        r = cancel(api, po["id"])
        assert r.status_code == 400
        assert "open purchase order with no delivery updates" in r.json()["detail"]
        assert get_po(api, po["id"])["status"] != "CANCELLED"


def test_an_order_with_any_delivery_update_cannot_be_cancelled(api):
    po = api.po_for()
    assert api.deliver(po["id"], "PENDING").status_code == 201  # still OPEN, but an update exists
    assert get_po(api, po["id"])["status"] == "OPEN"
    assert cancel(api, po["id"]).status_code == 400


def test_a_completed_order_cannot_be_cancelled(api):
    po = api.po_for()
    api.deliver(po["id"], "DELIVERED", iso_date(0))
    assert cancel(api, po["id"]).status_code == 400
    assert get_po(api, po["id"])["status"] == "COMPLETED"


# ---------- what cancelling frees up ----------


def test_the_pr_can_get_a_new_order_after_its_po_is_cancelled(api):
    po = api.po_for()
    pr_id = po["pr_id"]
    assert api.create_po(pr_id).status_code == 400  # blocked while the first is active

    cancel(api, po["id"])
    assert api.get_pr(pr_id).json()["status"] == "APPROVED"  # the request itself is untouched

    replacement = api.create_po(pr_id, vendor="multi", amount=450)
    assert replacement.status_code == 201
    assert replacement.json()["po_number"] != po["po_number"]
    assert api.create_po(pr_id).status_code == 400  # and the new one blocks again

    listed = api.c.get("/api/purchase-orders", params={"search": po["pr_number"]}, headers=api.h("admin")).json()
    assert {p["status"] for p in listed["items"]} == {"CANCELLED", "OPEN"}  # the cancelled order stays on record


def test_a_pr_with_only_a_cancelled_po_is_awaiting_a_po_again(api):
    po = api.po_for()

    def awaiting():
        r = api.c.get(
            "/api/purchase-requests", params={"status": "APPROVED", "awaiting_po": True}, headers=api.h("sameer")
        )
        return [p["id"] for p in r.json()["items"]]

    assert awaiting() == []
    cancel(api, po["id"])
    assert awaiting() == [po["pr_id"]]


def test_no_delivery_updates_on_a_cancelled_order(api):
    po = api.po_for()
    cancel(api, po["id"])
    r = api.deliver(po["id"], "IN_TRANSIT")
    assert r.status_code == 400 and "cancelled" in r.json()["detail"]


# ---------- visibility ----------


def test_a_requester_sees_the_cancellation_on_their_own_order_only(api):
    mine = api.po_for("rohan")
    theirs = api.po_for("priya")
    cancel(api, mine["id"], "Vendor could not supply")
    cancel(api, theirs["id"])

    detail = api.c.get(f"/api/purchase-orders/{mine['id']}", headers=api.h("rohan")).json()
    assert detail["status"] == "CANCELLED" and detail["cancel_reason"] == "Vendor could not supply"
    assert api.c.get(f"/api/purchase-orders/{theirs['id']}", headers=api.h("rohan")).status_code == 403


def test_cancelled_orders_can_be_filtered(api):
    kept = api.po_for()
    gone = api.po_for()
    cancel(api, gone["id"])
    r = api.c.get("/api/purchase-orders", params={"status": "CANCELLED"}, headers=api.h("admin")).json()
    assert [p["id"] for p in r["items"]] == [gone["id"]]
    assert kept["id"] not in [p["id"] for p in r["items"]]


# ---------- dashboard ----------


def test_the_dashboard_counts_a_cancelled_order_but_not_its_money(api):
    live = api.approved_pr(amount=1000)
    api.create_po(live["id"], amount=900)
    doomed = api.approved_pr(amount=2000)
    doomed_po = api.create_po(doomed["id"], amount=1800).json()
    cancel(api, doomed_po["id"])

    data = summary(api)
    by_status = {row["status"]: row["count"] for row in data["po_by_status"]}
    assert by_status["OPEN"] == 1 and by_status["CANCELLED"] == 1
    assert data["total_purchase_orders"] == 2  # still listed, so still counted
    assert data["pending_delivery"] == 1  # but nothing is awaited from it
    assert {r["currency"]: float(r["amount"]) for r in data["po_amounts"]} == {"AED": 900}  # no money on order
    # spend: the live PO price, plus the cancelled order's request back at its own approved amount
    assert float(data["total_spend_approved"]) == 900 + 2000


def test_the_activity_feed_shows_the_cancellation(api):
    po = api.po_for()
    cancel(api, po["id"])
    messages = [i["message"] for i in api.c.get("/api/dashboard/recent-activity", headers=api.h("admin")).json()]
    assert f"{po['po_number']} cancelled" in messages
    own = [i["message"] for i in api.c.get("/api/dashboard/recent-activity", headers=api.h("priya")).json()]
    assert f"{po['po_number']} cancelled" not in own  # scoped like the rest of the feed


def test_the_cancellation_is_logged(api, caplog):
    caplog.set_level(logging.INFO, logger="procureflow")
    po = api.po_for()
    cancel(api, po["id"], "Duplicate order")
    lines = [r.getMessage() for r in caplog.records if r.name == "procureflow.purchase_orders"]
    assert f"{po['po_number']} cancelled by sameer@procureflow.com: Duplicate order" in lines
