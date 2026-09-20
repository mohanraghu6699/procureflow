import pytest

from app import reset_data
from app.models import Category, Delivery, Department, PRStatusHistory, PurchaseOrder, PurchaseRequest, User, Vendor
from tests.conftest import TestingSession
from tests.helpers import iso_date


def populate(api):
    """A bit of everything: drafts, a rejected PR, a cancelled and a replacement PO, deliveries, a completed order."""
    api.create_pr("rohan")
    rejected = api.submitted_pr("rohan")
    api.reject(rejected["id"])
    cancelled = api.po_for("priya")
    api.c.post(f"/api/purchase-orders/{cancelled['id']}/cancel", json={"reason": "Wrong vendor"}, headers=api.h("sameer"))
    api.create_po(cancelled["pr_id"], vendor="multi")
    moving = api.po_for("rohan")
    api.deliver(moving["id"], "IN_TRANSIT")
    finished = api.po_for("priya")
    api.deliver(finished["id"], "DELIVERED", iso_date(0))


def counts(db):
    return {
        "deliveries": db.query(Delivery).count(),
        "orders": db.query(PurchaseOrder).count(),
        "history": db.query(PRStatusHistory).count(),
        "requests": db.query(PurchaseRequest).count(),
    }


def kept(db):
    return {
        "users": db.query(User).count(),
        "departments": db.query(Department).count(),
        "categories": db.query(Category).count(),
        "vendors": db.query(Vendor).count(),
        "vendor_category_links": sum(len(v.categories) for v in db.query(Vendor).all()),
    }


@pytest.fixture()
def use_test_db(monkeypatch):
    """Point the command-line entry point at the test database."""
    monkeypatch.setattr(reset_data, "SessionLocal", TestingSession)


def test_reset_clears_the_business_data_and_keeps_everything_else(api, db):
    populate(api)
    before, master_before = counts(db), kept(db)
    assert all(n > 0 for n in before.values())

    deleted = reset_data.reset_transactional_data(db)

    assert deleted == {
        "deliveries": before["deliveries"],
        "purchase orders": before["orders"],
        "status history rows": before["history"],
        "purchase requests": before["requests"],
    }
    assert counts(db) == {"deliveries": 0, "orders": 0, "history": 0, "requests": 0}
    assert kept(db) == master_before  # accounts, departments, categories, vendors and their links are untouched


def test_numbering_starts_again_and_the_app_is_immediately_usable(api, db):
    populate(api)
    reset_data.reset_transactional_data(db)

    pr = api.create_pr("rohan")
    assert pr.status_code == 201 and pr.json()["pr_number"].endswith("-0001")
    po = api.po_for("rohan")
    assert po["po_number"].endswith("-0001")  # the same accounts sign in and work, no re-seeding needed


def test_the_dashboard_is_empty_afterwards(api, db):
    populate(api)
    reset_data.reset_transactional_data(db)
    summary = api.c.get("/api/dashboard/summary", headers=api.h("admin")).json()
    assert summary["total_purchase_requests"] == 0 and summary["total_purchase_orders"] == 0
    assert summary["pr_amounts"] == [] and summary["po_amounts"] == [] and float(summary["total_spend_approved"]) == 0
    assert api.c.get("/api/dashboard/recent-activity", headers=api.h("admin")).json() == []
    assert api.c.get("/api/deliveries", headers=api.h("admin")).json()["total"] == 0


def test_running_it_twice_is_harmless(api, db):
    populate(api)
    reset_data.reset_transactional_data(db)
    again = reset_data.reset_transactional_data(db)
    assert set(again.values()) == {0}


# ---------- the command-line entry point ----------


def test_yes_skips_the_prompt(api, db, use_test_db, capsys):
    populate(api)

    def must_not_ask(_prompt):
        raise AssertionError("--yes must not prompt")

    reset_data.main(["--yes"], ask=must_not_ask)
    assert counts(db)["requests"] == 0
    assert "Cleared" in capsys.readouterr().out


def test_without_yes_it_needs_the_word_reset(api, db, use_test_db, capsys):
    populate(api)
    before = counts(db)

    for wrong in ("", "yes", "reset", "y"):
        with pytest.raises(SystemExit, match="Nothing was deleted"):
            reset_data.main([], ask=lambda _prompt, w=wrong: w)
        assert counts(db) == before  # nothing was touched

    reset_data.main([], ask=lambda _prompt: "RESET")
    assert counts(db)["requests"] == 0
    out = capsys.readouterr().out
    assert "This will permanently delete" in out and "Accounts and master data are kept" in out


def test_nothing_to_clear_does_not_prompt(api, db, use_test_db, capsys):
    def must_not_ask(_prompt):
        raise AssertionError("nothing to delete, so no prompt")

    reset_data.main([], ask=must_not_ask)
    assert "Nothing to clear" in capsys.readouterr().out


def test_unknown_options_are_rejected(use_test_db):
    with pytest.raises(SystemExit, match="Unknown argument"):
        reset_data.main(["--everything"])
