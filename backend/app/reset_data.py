"""Clear the business data for a fresh start: every purchase request, order, delivery and status-history row.

Accounts, departments, categories and vendors are kept, so the app is usable straight away. Numbering starts
again at PR-<year>-0001 / PO-<year>-0001, because the next number is worked out from what exists. Meant for demos
and rehearsals, so it refuses to run without confirmation.

Run from backend/:

    python -m app.reset_data          # shows what would be deleted and asks you to type RESET
    python -m app.reset_data --yes    # no prompt (deploy/gcp/update.sh --reset-data uses this)
"""
import sys
from typing import Callable

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Delivery, PRStatusHistory, PurchaseOrder, PurchaseRequest

# Children before parents, so foreign keys are never violated on the way.
TABLES = [
    ("deliveries", Delivery),
    ("purchase orders", PurchaseOrder),
    ("status history rows", PRStatusHistory),
    ("purchase requests", PurchaseRequest),
]


def count_rows(db: Session) -> dict[str, int]:
    return {label: db.query(model).count() for label, model in TABLES}


def reset_transactional_data(db: Session) -> dict[str, int]:
    """Delete all purchase requests, orders, deliveries and status history. Returns how many rows went."""
    counts = count_rows(db)
    for _label, model in TABLES:
        db.query(model).delete(synchronize_session=False)
    db.commit()
    return counts


def _describe(counts: dict[str, int]) -> str:
    return ", ".join(f"{n} {label}" for label, n in counts.items())


def main(argv: list[str] | None = None, ask: Callable[[str], str] = input) -> None:
    args = sys.argv[1:] if argv is None else argv
    unknown = [a for a in args if a != "--yes"]
    if unknown:
        raise SystemExit(f"Unknown argument(s): {' '.join(unknown)}. The only option is --yes.")

    with SessionLocal() as db:
        counts = count_rows(db)
        if not any(counts.values()):
            print("Nothing to clear: there are no purchase requests, orders or deliveries.")
            return
        if "--yes" not in args:
            print(f"This will permanently delete {_describe(counts)}. Accounts and master data are kept.")
            if ask("Type RESET to continue: ").strip() != "RESET":
                raise SystemExit("Cancelled. Nothing was deleted.")
        deleted = reset_transactional_data(db)

    print(f"Cleared {_describe(deleted)}. Accounts, departments, categories and vendors were kept.")


if __name__ == "__main__":
    main()
