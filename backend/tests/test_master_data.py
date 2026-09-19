import pytest

BASE = "/api/master-data"


def test_anyone_signed_in_can_read_master_data(api):
    for name in ("rohan", "sameer", "admin"):
        for path in ("departments", "categories", "vendors"):
            assert api.c.get(f"{BASE}/{path}", headers=api.h(name)).status_code == 200
    assert api.c.get(f"{BASE}/departments").status_code == 401


def test_lists_hide_inactive_rows_unless_asked(api):
    active = {v["name"] for v in api.c.get(f"{BASE}/vendors", headers=api.h("rohan")).json()}
    assert "Dormant Vendor" not in active

    everything = api.c.get(f"{BASE}/vendors", params={"include_inactive": True}, headers=api.h("admin")).json()
    assert "Dormant Vendor" in {v["name"] for v in everything}
    assert everything[-1]["name"] == "Dormant Vendor"  # inactive rows sort last


def test_vendors_can_be_filtered_by_category(api):
    def names(**params):
        r = api.c.get(f"{BASE}/vendors", params=params, headers=api.h("rohan")).json()
        return {v["name"] for v in r}

    assert names(category_id=api.w.cat["parts"]) == {"Gulf Marine Supplies", "Multi Supplier"}
    assert names(category_id=api.w.cat["hardware"]) == {"TechZone Computers", "Multi Supplier"}
    assert names(category_id=api.w.cat["catering"]) == {"Prime Catering"}
    assert names(category_id="missing") == set()


def test_vendor_output_lists_its_category_ids(api):
    vendors = {v["name"]: v for v in api.c.get(f"{BASE}/vendors", headers=api.h("rohan")).json()}
    assert set(vendors["Multi Supplier"]["category_ids"]) == {api.w.cat["parts"], api.w.cat["hardware"]}


@pytest.mark.parametrize(
    "method, path, body",
    [
        ("post", "departments", {"name": "Finance"}),
        ("post", "categories", {"name": "Stationery"}),
        ("post", "vendors", {"name": "Some Vendor"}),
        ("delete", "departments/x", None),
        ("delete", "categories/x", None),
        ("delete", "vendors/x", None),
        ("post", "departments/x/reactivate", None),
        ("post", "categories/x/reactivate", None),
        ("post", "vendors/x/reactivate", None),
        ("put", "vendors/x/categories", {"category_ids": []}),
    ],
)
def test_writes_are_admin_only(api, method, path, body):
    for name in ("rohan", "sameer"):
        r = getattr(api.c, method)(f"{BASE}/{path}", headers=api.h(name), **({"json": body} if body else {}))
        assert r.status_code == 403, f"{name} {method} {path}"


def test_admin_creates_a_vendor_with_categories(api):
    payload = {
        "name": "Fresh Vendor",
        "contact_email": "sales@fresh.com",
        "category_ids": [api.w.cat["parts"], api.w.cat["parts"], api.w.cat["catering"]],  # duplicates ignored
    }
    r = api.c.post(f"{BASE}/vendors", json=payload, headers=api.h("admin"))
    assert r.status_code == 201
    assert set(r.json()["category_ids"]) == {api.w.cat["parts"], api.w.cat["catering"]}

    bad = api.c.post(f"{BASE}/vendors", json={"name": "Bad Vendor", "category_ids": ["missing"]}, headers=api.h("admin"))
    assert bad.status_code == 400
    bad_email = api.c.post(f"{BASE}/vendors", json={"name": "Bad Email", "contact_email": "nope"}, headers=api.h("admin"))
    assert bad_email.status_code == 422


def test_vendor_categories_are_replaced_by_put(api):
    vendor_id = api.w.vendor["gulf"]
    r = api.c.put(
        f"{BASE}/vendors/{vendor_id}/categories", json={"category_ids": [api.w.cat["catering"]]}, headers=api.h("admin")
    )
    assert r.status_code == 200
    assert r.json()["category_ids"] == [api.w.cat["catering"]]

    # and it changes what the vendor can be ordered from
    pr = api.approved_pr()  # spare parts
    assert api.create_po(pr["id"], vendor="gulf").status_code == 400

    assert api.c.put(f"{BASE}/vendors/missing/categories", json={"category_ids": []}, headers=api.h("admin")).status_code == 404
    assert (
        api.c.put(f"{BASE}/vendors/{vendor_id}/categories", json={"category_ids": ["missing"]}, headers=api.h("admin")).status_code
        == 400
    )


@pytest.mark.parametrize("kind, key", [("departments", "ops"), ("categories", "parts"), ("vendors", "gulf")])
def test_deactivate_and_reactivate(api, kind, key):
    ids = {"departments": api.w.dept, "categories": api.w.cat, "vendors": api.w.vendor}[kind]
    item_id = ids[key]

    assert api.c.delete(f"{BASE}/{kind}/{item_id}", headers=api.h("admin")).status_code == 204
    active_ids = {i["id"] for i in api.c.get(f"{BASE}/{kind}", headers=api.h("admin")).json()}
    assert item_id not in active_ids

    r = api.c.post(f"{BASE}/{kind}/{item_id}/reactivate", headers=api.h("admin"))
    assert r.status_code == 200 and r.json()["is_active"] is True
    active_ids = {i["id"] for i in api.c.get(f"{BASE}/{kind}", headers=api.h("admin")).json()}
    assert item_id in active_ids

    assert api.c.delete(f"{BASE}/{kind}/missing", headers=api.h("admin")).status_code == 404
    assert api.c.post(f"{BASE}/{kind}/missing/reactivate", headers=api.h("admin")).status_code == 404


def test_deactivating_a_vendor_blocks_new_orders_to_it(api):
    pr = api.approved_pr()
    api.c.delete(f"{BASE}/vendors/{api.w.vendor['gulf']}", headers=api.h("admin"))
    r = api.create_po(pr["id"], vendor="gulf")
    assert r.status_code == 400 and "inactive" in r.json()["detail"]


@pytest.mark.parametrize("kind", ["departments", "categories"])
def test_adding_an_existing_name_conflicts_but_reactivates_a_deactivated_one(api, kind):
    created = api.c.post(f"{BASE}/{kind}", json={"name": "Brand New"}, headers=api.h("admin"))
    assert created.status_code == 201
    item = created.json()

    assert api.c.post(f"{BASE}/{kind}", json={"name": "Brand New"}, headers=api.h("admin")).status_code == 409

    api.c.delete(f"{BASE}/{kind}/{item['id']}", headers=api.h("admin"))
    again = api.c.post(f"{BASE}/{kind}", json={"name": "Brand New"}, headers=api.h("admin"))
    assert again.status_code == 201
    assert again.json()["id"] == item["id"] and again.json()["is_active"] is True


def test_short_names_are_rejected(api):
    assert api.c.post(f"{BASE}/departments", json={"name": "x"}, headers=api.h("admin")).status_code == 422
