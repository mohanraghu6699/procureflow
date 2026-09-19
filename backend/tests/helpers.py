from datetime import datetime, timedelta

from app.auth import create_access_token

PASSWORD = "Passw0rd!"


def iso_date(days: int = 0) -> str:
    """A calendar date `days` from today, in the UTC-midnight form the frontend sends."""
    return (datetime.utcnow() + timedelta(days=days)).strftime("%Y-%m-%dT00:00:00Z")


def email(name: str) -> str:
    return f"{name}@procureflow.com"


class World:
    """Ids of the seeded master data and users, plus auth headers for any seeded user."""

    def __init__(self, dept: dict, cat: dict, vendor: dict, user: dict):
        self.dept, self.cat, self.vendor, self.user = dept, cat, vendor, user

    def headers(self, name: str) -> dict:
        return {"Authorization": f"Bearer {create_access_token(subject=self.user[name])}"}


class Api:
    """Thin wrappers over the endpoints; they return raw responses so tests can assert on failures."""

    def __init__(self, client, world: World):
        self.c, self.w = client, world

    def h(self, user: str) -> dict:
        return self.w.headers(user)

    # ----- purchase requests -----
    def pr_payload(self, **over) -> dict:
        payload = {
            "department_id": self.w.dept["ops"],
            "description": "Replacement pump parts",
            "category_id": self.w.cat["parts"],
            "amount": 500,
            "currency": "AED",
            "required_date": iso_date(7),
            "vendor_id": None,
        }
        payload.update(over)
        return payload

    def create_pr(self, user: str = "rohan", **over):
        return self.c.post("/api/purchase-requests", json=self.pr_payload(**over), headers=self.h(user))

    def get_pr(self, pr_id: str, user: str = "admin"):
        return self.c.get(f"/api/purchase-requests/{pr_id}", headers=self.h(user))

    def edit(self, pr_id: str, user: str = "rohan", **fields):
        return self.c.patch(f"/api/purchase-requests/{pr_id}", json=fields, headers=self.h(user))

    def submit(self, pr_id: str, user: str = "rohan"):
        return self.c.post(f"/api/purchase-requests/{pr_id}/submit", headers=self.h(user))

    def approve(self, pr_id: str, user: str = "sameer", comment: str | None = None):
        return self.c.post(f"/api/purchase-requests/{pr_id}/approve", json={"comment": comment}, headers=self.h(user))

    def reject(self, pr_id: str, user: str = "sameer", comment: str | None = "Please revise the amount"):
        return self.c.post(f"/api/purchase-requests/{pr_id}/reject", json={"comment": comment}, headers=self.h(user))

    def submitted_pr(self, user: str = "rohan", **over) -> dict:
        pr = self.create_pr(user, **over)
        assert pr.status_code == 201, pr.text
        r = self.submit(pr.json()["id"], user)
        assert r.status_code == 200, r.text
        return r.json()

    def approved_pr(self, user: str = "rohan", approver: str = "sameer", **over) -> dict:
        pr = self.submitted_pr(user, **over)
        r = self.approve(pr["id"], approver)
        assert r.status_code == 200, r.text
        return r.json()

    # ----- purchase orders and deliveries -----
    def create_po(self, pr_id: str, user: str = "sameer", vendor: str = "gulf", amount=500):
        return self.c.post(
            "/api/purchase-orders",
            json={"pr_id": pr_id, "vendor_id": self.w.vendor[vendor], "amount": amount},
            headers=self.h(user),
        )

    def po_for(self, user: str = "rohan", vendor: str = "gulf", amount=500, **pr_over) -> dict:
        pr = self.approved_pr(user, **pr_over)
        r = self.create_po(pr["id"], vendor=vendor, amount=amount)
        assert r.status_code == 201, r.text
        return r.json()

    def deliver(self, po_id: str, status: str, date: str | None = None, user: str = "sameer", remarks=None):
        body = {"status": status, "delivery_date": date, "remarks": remarks}
        return self.c.post(f"/api/purchase-orders/{po_id}/deliveries", json=body, headers=self.h(user))
