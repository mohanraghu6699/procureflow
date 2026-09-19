from tests.helpers import iso_date


def test_po_is_created_against_an_approved_pr(api):
    pr = api.approved_pr(amount=500)
    r = api.create_po(pr["id"], amount=450)
    assert r.status_code == 201
    po = r.json()
    assert po["status"] == "OPEN"
    assert po["po_number"].endswith("-0001")
    assert po["pr_number"] == pr["pr_number"]
    assert po["vendor_name"] == "Gulf Marine Supplies"
    assert po["created_by_name"] == "Sameer"
    assert float(po["amount"]) == 450
    assert po["required_date"][:10] == pr["required_date"][:10]  # inherited from the PR


def test_currency_is_copied_from_the_pr(api):
    pr = api.approved_pr(currency="USD")
    assert api.create_po(pr["id"]).json()["currency"] == "USD"


def test_po_needs_an_approved_pr(api):
    draft = api.create_pr().json()
    submitted = api.submitted_pr()
    rejected = api.submitted_pr()
    api.reject(rejected["id"])

    for pr in (draft, submitted, rejected):
        r = api.create_po(pr["id"])
        assert r.status_code == 400
        assert "approved purchase request" in r.json()["detail"]

    assert api.create_po("missing").status_code == 400


def test_po_amount_cannot_exceed_the_approved_amount(api):
    pr = api.approved_pr(amount=500)
    r = api.create_po(pr["id"], amount=500.01)
    assert r.status_code == 400
    assert r.json()["detail"] == "PO amount cannot exceed the approved amount of AED 500.00"
    assert api.create_po(pr["id"], amount=500).status_code == 201  # equal is fine


def test_po_amount_must_be_positive(api):
    pr = api.approved_pr()
    assert api.create_po(pr["id"], amount=0).status_code == 422
    assert api.create_po(pr["id"], amount=-5).status_code == 422


def test_po_vendor_must_be_active_and_supply_the_category(api):
    pr = api.approved_pr()  # spare parts
    wrong = api.create_po(pr["id"], vendor="prime")
    assert wrong.status_code == 400
    assert "does not supply this category" in wrong.json()["detail"]

    dormant = api.create_po(pr["id"], vendor="dormant")
    assert dormant.status_code == 400
    assert "inactive" in dormant.json()["detail"]

    assert api.create_po(pr["id"], vendor="multi").status_code == 201


def test_a_pr_can_only_have_one_active_po(api):
    pr = api.approved_pr()
    assert api.create_po(pr["id"]).status_code == 201
    r = api.create_po(pr["id"])
    assert r.status_code == 400
    assert "already has an active purchase order" in r.json()["detail"]


def test_only_approvers_and_admins_can_create_pos(api):
    pr = api.approved_pr()
    assert api.create_po(pr["id"], user="rohan").status_code == 403  # the requester
    assert api.create_po(pr["id"], user="priya").status_code == 403
    assert api.create_po(pr["id"], user="amit").status_code == 201  # any approver, not only the one who approved


def test_requesters_only_see_pos_for_their_own_prs(api):
    mine = api.po_for("rohan")
    theirs = api.po_for("priya")

    listed = api.c.get("/api/purchase-orders", headers=api.h("rohan")).json()
    assert [p["id"] for p in listed["items"]] == [mine["id"]]

    assert api.c.get(f"/api/purchase-orders/{mine['id']}", headers=api.h("rohan")).status_code == 200
    assert api.c.get(f"/api/purchase-orders/{theirs['id']}", headers=api.h("rohan")).status_code == 403
    assert api.c.get(f"/api/purchase-orders/{theirs['id']}", headers=api.h("sameer")).status_code == 200
    assert api.c.get("/api/purchase-orders/missing", headers=api.h("sameer")).status_code == 404


def test_po_detail_includes_deliveries_with_po_number(api):
    po = api.po_for()
    api.deliver(po["id"], "IN_TRANSIT")
    detail = api.c.get(f"/api/purchase-orders/{po['id']}", headers=api.h("sameer")).json()
    assert len(detail["deliveries"]) == 1
    assert detail["deliveries"][0]["po_number"] == po["po_number"]
    assert detail["deliveries"][0]["updated_by_name"] == "Sameer"


def test_po_list_filters_search_and_sorting(api):
    small = api.po_for(description="Small order", amount=100, required_date=iso_date(20))
    large = api.po_for(description="Large order", amount=400, vendor="multi", required_date=iso_date(5))
    api.deliver(large["id"], "IN_TRANSIT")

    def ids(**params):
        r = api.c.get("/api/purchase-orders", params=params, headers=api.h("admin")).json()
        return [p["id"] for p in r["items"]]

    assert ids(status="IN_TRANSIT") == [large["id"]]
    assert ids(status="OPEN") == [small["id"]]
    assert ids(vendor_id=api.w.vendor["multi"]) == [large["id"]]
    assert ids(search=small["po_number"]) == [small["id"]]
    assert ids(search=large["pr_number"]) == [large["id"]]
    assert ids(sort_by="amount", sort_dir="desc") == [large["id"], small["id"]]
    assert ids(sort_by="amount", sort_dir="asc") == [small["id"], large["id"]]
    assert ids(sort_by="required_date", sort_dir="asc") == [large["id"], small["id"]]
    assert ids(sort_by="po_number", sort_dir="asc") == [small["id"], large["id"]]


def test_po_list_pagination(api):
    for _ in range(3):
        api.po_for()
    r = api.c.get("/api/purchase-orders", params={"page": 2, "page_size": 2}, headers=api.h("admin")).json()
    assert r["total"] == 3 and len(r["items"]) == 1
    assert api.c.get("/api/purchase-orders", params={"sort_by": "vendor"}, headers=api.h("admin")).status_code == 422
