from tests.helpers import iso_date


def summary(api, user="admin"):
    r = api.c.get("/api/dashboard/summary", headers=api.h(user))
    assert r.status_code == 200, r.text
    return r.json()


def counts(rows):
    return {row["status"]: row["count"] for row in rows}


def test_empty_dashboard_is_all_zeroes(api):
    data = summary(api)
    assert data["total_purchase_requests"] == 0
    assert data["total_purchase_orders"] == 0
    assert float(data["total_spend_approved"]) == 0
    assert set(counts(data["pr_by_status"])) == {"DRAFT", "SUBMITTED", "APPROVED", "REJECTED", "COMPLETED"}
    assert all(v == 0 for v in counts(data["pr_by_status"]).values())
    assert counts(data["po_by_status"]) == {"OPEN": 0, "IN_TRANSIT": 0, "PARTIALLY_DELIVERED": 0, "COMPLETED": 0}
    assert len(data["monthly_trend"]) == 9
    assert api.c.get("/api/dashboard/recent-activity", headers=api.h("admin")).json() == []


def test_counts_follow_the_workflow(api):
    api.create_pr()  # draft
    api.submitted_pr()  # submitted
    rejected = api.submitted_pr()
    api.reject(rejected["id"])
    api.po_for()  # approved with an open PO
    finished = api.po_for()
    api.deliver(finished["id"], "DELIVERED", iso_date(0))
    in_transit = api.po_for()
    api.deliver(in_transit["id"], "IN_TRANSIT")

    data = summary(api)
    assert data["total_purchase_requests"] == 6
    assert data["pending_approval"] == 1
    assert data["total_purchase_orders"] == 3
    assert data["pending_delivery"] == 2
    assert counts(data["pr_by_status"]) == {"DRAFT": 1, "SUBMITTED": 1, "APPROVED": 2, "REJECTED": 1, "COMPLETED": 1}
    assert counts(data["po_by_status"]) == {"OPEN": 1, "IN_TRANSIT": 1, "PARTIALLY_DELIVERED": 0, "COMPLETED": 1}


def test_spend_uses_the_po_amount_once_ordered(api):
    api.approved_pr(amount=1000)  # no PO yet: counts at the approved amount
    ordered = api.approved_pr(amount=2000)
    api.create_po(ordered["id"], amount=1800)  # negotiated below the approved amount
    api.submitted_pr(amount=9999)  # not approved: excluded

    assert float(summary(api)["total_spend_approved"]) == 2800


def test_requesters_only_see_their_own_numbers(api):
    api.po_for("rohan")
    api.submitted_pr("priya")
    api.submitted_pr("priya")

    rohan, priya = summary(api, "rohan"), summary(api, "priya")
    assert (rohan["total_purchase_requests"], rohan["total_purchase_orders"], rohan["pending_approval"]) == (1, 1, 0)
    assert (priya["total_purchase_requests"], priya["total_purchase_orders"], priya["pending_approval"]) == (2, 0, 2)
    assert summary(api, "sameer")["total_purchase_requests"] == 3


def test_trends_compare_this_period_to_the_last(api):
    approved = api.approved_pr(amount=700)
    api.create_po(approved["id"], amount=650)
    api.submitted_pr()

    trends = summary(api)["trends"]
    assert float(trends["prs_created_month"]["current"]) >= 0
    assert float(trends["submitted_week"]["current"]) == 2
    assert float(trends["submitted_week"]["previous"]) == 0
    assert float(trends["ordered_week"]["current"]) == 1
    assert float(trends["approved_spend_month"]["current"]) in (0, 650)  # 0 only if now is the 1st before the month started
    assert set(trends) == {
        "prs_created_month",
        "pos_created_month",
        "submitted_week",
        "ordered_week",
        "approved_spend_month",
    }


def test_monthly_trend_counts_this_months_records(api):
    api.create_pr()
    api.po_for()
    last = summary(api)["monthly_trend"][-1]
    assert last["pr_count"] == 2 and last["po_count"] == 1


def test_recent_activity_reads_as_sentences_newest_first(api):
    po = api.po_for()
    api.deliver(po["id"], "PARTIAL")

    items = api.c.get("/api/dashboard/recent-activity", headers=api.h("admin")).json()
    messages = [i["message"] for i in items]
    assert messages[0] == f"{po['po_number']} delivery marked partial"
    assert f"{po['pr_number']} approved" in messages
    assert f"{po['pr_number']} submitted for approval" in messages
    assert f"{po['pr_number']} created" in messages
    assert all(i["timestamp"].endswith("+00:00") for i in items)
    stamps = [i["timestamp"] for i in items]
    assert stamps == sorted(stamps, reverse=True)


def test_in_transit_activity_has_no_underscore(api):
    po = api.po_for()
    api.deliver(po["id"], "IN_TRANSIT")
    messages = [i["message"] for i in api.c.get("/api/dashboard/recent-activity", headers=api.h("admin")).json()]
    assert f"{po['po_number']} delivery marked in transit" in messages


def test_recent_activity_is_scoped_for_requesters(api):
    api.create_pr("rohan")
    other = api.create_pr("priya").json()

    rohan_messages = [i["message"] for i in api.c.get("/api/dashboard/recent-activity", headers=api.h("rohan")).json()]
    assert len(rohan_messages) == 1
    assert other["pr_number"] not in " ".join(rohan_messages)


def test_dashboard_requires_authentication(client):
    assert client.get("/api/dashboard/summary").status_code == 401
    assert client.get("/api/dashboard/recent-activity").status_code == 401


def totals(rows):
    return {row["currency"]: float(row["amount"]) for row in rows}


def order(api, pr_amount, po_amount, currency="AED", user="rohan"):
    """An approved request for pr_amount that has been ordered at po_amount."""
    pr = api.approved_pr(user, amount=pr_amount, currency=currency)
    assert api.create_po(pr["id"], amount=po_amount).status_code == 201


def test_amounts_are_empty_with_no_data(api):
    data = summary(api)
    assert data["pr_amounts"] == [] and data["po_amounts"] == []


def test_amounts_total_every_request_and_order(api):
    api.create_pr(amount=100)  # a draft still counts, like it does in the request count
    rejected = api.submitted_pr(amount=250)
    api.reject(rejected["id"])
    order(api, pr_amount=900, po_amount=800)  # ordered below the approved amount

    data = summary(api)
    assert data["total_purchase_requests"] == 3
    assert totals(data["pr_amounts"]) == {"AED": 100 + 250 + 900}
    assert totals(data["po_amounts"]) == {"AED": 800}  # the PO's own price, not the PR's


def test_amounts_are_kept_per_currency_largest_first(api):
    api.create_pr(amount=100, currency="AED")
    api.create_pr(amount=50, currency="USD")
    api.create_pr(amount=300, currency="USD")
    order(api, pr_amount=40, po_amount=40, currency="EUR")

    data = summary(api)
    assert [r["currency"] for r in data["pr_amounts"]] == ["USD", "AED", "EUR"]  # 350, 100, 40
    assert totals(data["pr_amounts"]) == {"USD": 350, "AED": 100, "EUR": 40}
    assert totals(data["po_amounts"]) == {"EUR": 40}  # the order inherits its PR's currency


def test_amounts_only_include_the_requesters_own_records(api):
    order(api, pr_amount=500, po_amount=500, user="rohan")
    api.create_pr("priya", amount=70)

    assert totals(summary(api, "rohan")["pr_amounts"]) == {"AED": 500}
    assert totals(summary(api, "rohan")["po_amounts"]) == {"AED": 500}
    assert totals(summary(api, "priya")["pr_amounts"]) == {"AED": 70}
    assert summary(api, "priya")["po_amounts"] == []
    assert totals(summary(api, "sameer")["pr_amounts"]) == {"AED": 570}
