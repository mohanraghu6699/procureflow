import pytest

from tests.helpers import iso_date


# ---------- creation and validation ----------


def test_requester_creates_a_draft_with_history(api):
    r = api.create_pr()
    assert r.status_code == 201
    pr = r.json()
    assert pr["status"] == "DRAFT"
    assert pr["pr_number"].startswith("PR-") and pr["pr_number"].endswith("-0001")
    assert pr["requester_name"] == "Rohan"
    assert pr["revision_required"] is False

    history = api.get_pr(pr["id"]).json()["status_history"]
    assert [(h["from_status"], h["to_status"]) for h in history] == [(None, "DRAFT")]


def test_approver_cannot_create_a_pr(api):
    assert api.create_pr("sameer").status_code == 403


@pytest.mark.parametrize(
    "override",
    [
        {"amount": 0},
        {"amount": -10},
        {"description": "ab"},
        {"description": ""},
        {"required_date": iso_date(-3)},
        {"currency": "A"},
    ],
)
def test_invalid_payloads_are_rejected(api, override):
    assert api.create_pr(**override).status_code == 422


def test_unknown_department_category_or_vendor_is_rejected(api):
    assert api.create_pr(department_id="missing").status_code == 400
    assert api.create_pr(category_id="missing").status_code == 400
    assert api.create_pr(vendor_id="missing").status_code == 400


def test_preferred_vendor_must_supply_the_category(api):
    assert api.create_pr(vendor_id=api.w.vendor["gulf"]).status_code == 201
    r = api.create_pr(vendor_id=api.w.vendor["prime"])  # caterer for a spare-parts request
    assert r.status_code == 400
    assert "does not supply this category" in r.json()["detail"]


def test_inactive_vendor_cannot_be_chosen(api):
    r = api.create_pr(vendor_id=api.w.vendor["dormant"])
    assert r.status_code == 400
    assert "inactive" in r.json()["detail"]


def test_pr_numbers_are_sequential_and_not_reused_after_deleting_a_draft(api):
    first = api.create_pr().json()
    second = api.create_pr().json()
    third = api.create_pr().json()
    assert [p["pr_number"][-4:] for p in (first, second, third)] == ["0001", "0002", "0003"]

    assert api.c.delete(f"/api/purchase-requests/{second['id']}", headers=api.h("rohan")).status_code == 204
    fourth = api.create_pr().json()
    assert fourth["pr_number"][-4:] == "0004"
    assert len({p["pr_number"] for p in (first, third, fourth)}) == 3


# ---------- visibility ----------


def test_requesters_only_see_their_own_prs(api):
    mine = api.create_pr("rohan").json()
    theirs = api.create_pr("priya").json()

    listed = api.c.get("/api/purchase-requests", headers=api.h("rohan")).json()
    assert [p["id"] for p in listed["items"]] == [mine["id"]]

    assert api.get_pr(mine["id"], "rohan").status_code == 200
    assert api.get_pr(theirs["id"], "rohan").status_code == 403
    assert api.get_pr(theirs["id"], "sameer").status_code == 200  # approvers see everything
    assert api.get_pr("missing", "rohan").status_code == 404


def test_approver_mine_filter_limits_to_own_requests(api):
    api.create_pr("rohan")
    own = api.create_pr("admin").json()
    r = api.c.get("/api/purchase-requests", params={"mine": True}, headers=api.h("admin")).json()
    assert [p["id"] for p in r["items"]] == [own["id"]]


# ---------- editing ----------


def test_edit_changes_only_the_supplied_fields(api):
    pr = api.create_pr().json()
    r = api.edit(pr["id"], amount=750, description="  Updated pump parts  ")
    assert r.status_code == 200
    body = r.json()
    assert float(body["amount"]) == 750
    assert body["description"] == "Updated pump parts"
    assert body["category_id"] == pr["category_id"]


def test_edit_with_no_real_change_is_refused(api):
    pr = api.create_pr().json()
    for same in ({"amount": 500}, {"description": pr["description"]}, {"description": pr["description"] + "  "}):
        r = api.edit(pr["id"], **same)
        assert r.status_code == 400
        assert r.json()["detail"] == "No changes to save"


def test_same_day_timezone_shift_is_not_an_edit(api):
    pr = api.create_pr(required_date=iso_date(7)).json()
    shifted = iso_date(7).replace("T00:00:00Z", "T15:30:00Z")
    assert api.edit(pr["id"], required_date=shifted).status_code == 400
    assert api.edit(pr["id"], required_date=iso_date(8)).status_code == 200


def test_edit_revalidates_vendor_against_category(api):
    pr = api.create_pr(vendor_id=api.w.vendor["gulf"]).json()
    r = api.edit(pr["id"], category_id=api.w.cat["catering"])  # gulf doesn't supply catering
    assert r.status_code == 400
    assert api.edit(pr["id"], category_id=api.w.cat["hardware"], vendor_id=api.w.vendor["tech"]).status_code == 200


def test_only_the_owner_can_edit_a_pr(api):
    pr = api.create_pr("rohan").json()
    assert api.edit(pr["id"], "priya", amount=1).status_code == 403


def test_submitted_and_approved_prs_cannot_be_edited(api):
    submitted = api.submitted_pr()
    assert api.edit(submitted["id"], amount=1).status_code == 400
    api.approve(submitted["id"])
    assert api.edit(submitted["id"], amount=1).status_code == 400


# ---------- workflow ----------


def test_full_approval_path_records_history(api):
    pr = api.submitted_pr()
    assert pr["status"] == "SUBMITTED"

    approved = api.approve(pr["id"], comment="Looks good")
    assert approved.status_code == 200 and approved.json()["status"] == "APPROVED"

    history = api.get_pr(pr["id"]).json()["status_history"]
    assert [h["to_status"] for h in history] == ["DRAFT", "SUBMITTED", "APPROVED"]
    assert history[-1]["comment"] == "Looks good"
    assert history[-1]["changed_by_name"] == "Sameer"
    assert history[-1]["changed_at"].endswith("+00:00")


def test_requester_cannot_approve_or_reject(api):
    pr = api.submitted_pr()
    assert api.approve(pr["id"], "priya").status_code == 403
    assert api.reject(pr["id"], "priya").status_code == 403


def test_approver_cannot_approve_their_own_request(api):
    pr = api.create_pr("admin").json()
    api.submit(pr["id"], "admin")
    r = api.approve(pr["id"], "admin")
    assert r.status_code == 400
    assert "own purchase request" in r.json()["detail"]
    assert api.reject(pr["id"], "admin").status_code == 400
    assert api.approve(pr["id"], "sameer").status_code == 200  # someone else can


def test_only_submitted_prs_can_be_decided(api):
    draft = api.create_pr().json()
    assert api.approve(draft["id"]).status_code == 400
    assert api.reject(draft["id"]).status_code == 400

    approved = api.approved_pr()
    assert api.approve(approved["id"]).status_code == 400
    assert api.reject(approved["id"]).status_code == 400
    assert api.submit(approved["id"]).status_code == 400


def test_someone_elses_pr_cannot_be_submitted(api):
    pr = api.create_pr("rohan").json()
    assert api.submit(pr["id"], "priya").status_code == 403


def test_reject_requires_a_reason(api):
    pr = api.submitted_pr()
    for blank in (None, "", "   "):
        r = api.reject(pr["id"], comment=blank)
        assert r.status_code == 400
        assert r.json()["detail"] == "A reason is required to reject a purchase request"
    assert api.get_pr(pr["id"]).json()["status"] == "SUBMITTED"


def test_rejection_stores_the_reason_and_flags_revision(api):
    pr = api.submitted_pr()
    r = api.reject(pr["id"], comment="Budget exceeded")
    assert r.status_code == 200
    assert r.json()["status"] == "REJECTED"
    assert r.json()["revision_required"] is True
    assert api.get_pr(pr["id"]).json()["status_history"][-1]["comment"] == "Budget exceeded"


def test_rejected_pr_cannot_be_resubmitted_without_a_real_edit(api):
    pr = api.submitted_pr()
    api.reject(pr["id"])

    blocked = api.submit(pr["id"])
    assert blocked.status_code == 400
    assert "address the rejection" in blocked.json()["detail"]

    assert api.edit(pr["id"], amount=500).status_code == 400  # a no-op edit doesn't count
    assert api.submit(pr["id"]).status_code == 400

    edited = api.edit(pr["id"], amount=450)
    assert edited.status_code == 200 and edited.json()["revision_required"] is False
    resubmitted = api.submit(pr["id"])
    assert resubmitted.status_code == 200 and resubmitted.json()["status"] == "SUBMITTED"


def test_resubmitted_pr_can_be_approved(api):
    pr = api.submitted_pr()
    api.reject(pr["id"])
    api.edit(pr["id"], description="Revised pump parts")
    api.submit(pr["id"])
    assert api.approve(pr["id"]).json()["status"] == "APPROVED"
    history = api.get_pr(pr["id"]).json()["status_history"]
    assert [h["to_status"] for h in history] == ["DRAFT", "SUBMITTED", "REJECTED", "SUBMITTED", "APPROVED"]


def test_only_drafts_can_be_deleted(api):
    draft = api.create_pr().json()
    assert api.c.delete(f"/api/purchase-requests/{draft['id']}", headers=api.h("priya")).status_code == 403

    submitted = api.submitted_pr()
    r = api.c.delete(f"/api/purchase-requests/{submitted['id']}", headers=api.h("rohan"))
    assert r.status_code == 400

    assert api.c.delete(f"/api/purchase-requests/{draft['id']}", headers=api.h("rohan")).status_code == 204
    assert api.get_pr(draft["id"]).status_code == 404


# ---------- listing ----------


def _make_prs(api):
    api.create_pr(description="Alpha pump", amount=100, required_date=iso_date(10))
    api.create_pr(description="Bravo laptop", amount=300, category_id=api.w.cat["hardware"], required_date=iso_date(5))
    api.create_pr(description="Charlie lunch", amount=200, category_id=api.w.cat["catering"], required_date=iso_date(20))


def test_search_matches_description_and_number(api):
    _make_prs(api)
    hits = api.c.get("/api/purchase-requests", params={"search": "laptop"}, headers=api.h("admin")).json()
    assert [p["description"] for p in hits["items"]] == ["Bravo laptop"]

    by_number = api.c.get("/api/purchase-requests", params={"search": "-0002"}, headers=api.h("admin")).json()
    assert [p["description"] for p in by_number["items"]] == ["Bravo laptop"]

    assert api.c.get("/api/purchase-requests", params={"search": "zzz"}, headers=api.h("admin")).json()["total"] == 0


def test_filter_by_status_category_and_department(api):
    _make_prs(api)
    pr = api.submitted_pr(description="Delta submitted")

    def total(**params):
        return api.c.get("/api/purchase-requests", params=params, headers=api.h("admin")).json()["total"]

    assert total() == 4
    assert total(status="SUBMITTED") == 1
    assert total(status="DRAFT") == 3
    assert total(category_id=api.w.cat["hardware"]) == 1
    assert total(department_id=api.w.dept["it"]) == 0
    assert total(department_id=api.w.dept["ops"]) == 4
    assert pr["status"] == "SUBMITTED"


def test_sorting_by_amount_required_date_and_number(api):
    _make_prs(api)

    def order(sort_by, sort_dir):
        r = api.c.get(
            "/api/purchase-requests", params={"sort_by": sort_by, "sort_dir": sort_dir}, headers=api.h("admin")
        ).json()
        return [p["description"].split()[0] for p in r["items"]]

    assert order("amount", "asc") == ["Alpha", "Charlie", "Bravo"]
    assert order("amount", "desc") == ["Bravo", "Charlie", "Alpha"]
    assert order("required_date", "asc") == ["Bravo", "Alpha", "Charlie"]
    assert order("pr_number", "asc") == ["Alpha", "Bravo", "Charlie"]


def test_invalid_sort_parameters_are_rejected(api):
    assert api.c.get("/api/purchase-requests", params={"sort_by": "password"}, headers=api.h("admin")).status_code == 422
    assert api.c.get("/api/purchase-requests", params={"sort_dir": "sideways"}, headers=api.h("admin")).status_code == 422


def test_pagination(api):
    for i in range(5):
        api.create_pr(description=f"Item number {i}")

    def page(n, size=2):
        return api.c.get(
            "/api/purchase-requests",
            params={"page": n, "page_size": size, "sort_by": "pr_number", "sort_dir": "asc"},
            headers=api.h("admin"),
        ).json()

    first, second, third = page(1), page(2), page(3)
    assert first["total"] == 5 and first["page"] == 1 and first["page_size"] == 2
    assert [len(p["items"]) for p in (first, second, third)] == [2, 2, 1]
    numbers = [i["pr_number"] for p in (first, second, third) for i in p["items"]]
    assert numbers == sorted(numbers) and len(set(numbers)) == 5

    assert api.c.get("/api/purchase-requests", params={"page": 0}, headers=api.h("admin")).status_code == 422
    assert api.c.get("/api/purchase-requests", params={"page_size": 101}, headers=api.h("admin")).status_code == 422


def test_awaiting_po_excludes_prs_that_already_have_one(api):
    ordered = api.approved_pr()
    waiting = api.approved_pr()
    assert api.create_po(ordered["id"]).status_code == 201

    r = api.c.get(
        "/api/purchase-requests", params={"status": "APPROVED", "awaiting_po": True}, headers=api.h("sameer")
    ).json()
    assert [p["id"] for p in r["items"]] == [waiting["id"]]
