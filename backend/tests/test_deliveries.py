from tests.helpers import iso_date


def po_status(api, po_id):
    return api.c.get(f"/api/purchase-orders/{po_id}", headers=api.h("admin")).json()["status"]


def pr_status(api, pr_id):
    return api.get_pr(pr_id).json()["status"]


def test_delivery_updates_move_the_po_through_each_stage(api):
    po = api.po_for()
    expected = [
        ("IN_TRANSIT", "IN_TRANSIT"),
        ("PARTIAL", "PARTIALLY_DELIVERED"),
        ("IN_TRANSIT", "IN_TRANSIT"),  # updates may go back and forth until completion
        ("PARTIAL", "PARTIALLY_DELIVERED"),
    ]
    for delivery_status, resulting_po_status in expected:
        r = api.deliver(po["id"], delivery_status)
        assert r.status_code == 201, r.text
        assert r.json()["status"] == resulting_po_status
        assert po_status(api, po["id"]) == resulting_po_status
        assert pr_status(api, po["pr_id"]) == "APPROVED"  # not finished yet

    detail = api.c.get(f"/api/purchase-orders/{po['id']}", headers=api.h("admin")).json()
    assert [d["status"] for d in detail["deliveries"]] == ["IN_TRANSIT", "PARTIAL", "IN_TRANSIT", "PARTIAL"]


def test_delivered_completes_both_the_po_and_the_pr(api):
    po = api.po_for()
    api.deliver(po["id"], "IN_TRANSIT")
    r = api.deliver(po["id"], "DELIVERED", iso_date(0), remarks="All items received")
    assert r.status_code == 201
    assert r.json()["status"] == "COMPLETED"
    assert pr_status(api, po["pr_id"]) == "COMPLETED"


def test_no_updates_after_completion(api):
    po = api.po_for()
    api.deliver(po["id"], "DELIVERED", iso_date(0))
    r = api.deliver(po["id"], "IN_TRANSIT")
    assert r.status_code == 400
    assert "already completed" in r.json()["detail"]


def test_delivered_needs_a_date(api):
    po = api.po_for()
    r = api.deliver(po["id"], "DELIVERED")
    assert r.status_code == 400
    assert r.json()["detail"] == "delivery_date is required when marking as delivered"
    assert po_status(api, po["id"]) == "OPEN"


def test_transit_and_partial_do_not_need_a_date(api):
    po = api.po_for()
    assert api.deliver(po["id"], "IN_TRANSIT").status_code == 201
    assert api.deliver(po["id"], "PARTIAL").status_code == 201


def test_delivery_date_cannot_be_in_the_future(api):
    po = api.po_for()
    r = api.deliver(po["id"], "DELIVERED", iso_date(5))
    assert r.status_code == 400
    assert r.json()["detail"] == "Delivery date cannot be in the future"
    assert api.deliver(po["id"], "PARTIAL", iso_date(5)).status_code == 400


def test_delivery_date_cannot_precede_the_po(api):
    po = api.po_for()
    r = api.deliver(po["id"], "DELIVERED", iso_date(-10))
    assert r.status_code == 400
    assert r.json()["detail"] == "Delivery date cannot be before the purchase order was created"


def test_unknown_status_and_unknown_po(api):
    po = api.po_for()
    assert api.deliver(po["id"], "LOST").status_code == 422
    assert api.deliver("missing", "IN_TRANSIT").status_code == 404


def test_requesters_cannot_record_deliveries(api):
    po = api.po_for("rohan")
    assert api.deliver(po["id"], "IN_TRANSIT", user="rohan").status_code == 403
    assert po_status(api, po["id"]) == "OPEN"


def test_delivery_list_is_for_approvers_and_shows_po_numbers(api):
    po = api.po_for()
    api.deliver(po["id"], "IN_TRANSIT")
    api.deliver(po["id"], "PARTIAL")

    assert api.c.get("/api/deliveries", headers=api.h("rohan")).status_code == 403

    listed = api.c.get("/api/deliveries", headers=api.h("sameer")).json()
    assert len(listed) == 2
    assert {d["po_number"] for d in listed} == {po["po_number"]}

    partial = api.c.get("/api/deliveries", params={"status": "PARTIAL"}, headers=api.h("sameer")).json()
    assert [d["status"] for d in partial] == ["PARTIAL"]
    assert api.c.get("/api/deliveries", params={"limit": 0}, headers=api.h("sameer")).status_code == 422


def test_completed_pr_can_no_longer_take_a_new_po(api):
    po = api.po_for()
    api.deliver(po["id"], "DELIVERED", iso_date(0))
    r = api.create_po(po["pr_id"])
    assert r.status_code == 400
    assert "approved purchase request" in r.json()["detail"]
