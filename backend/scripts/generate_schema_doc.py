"""Generate the database schema documentation from the SQLAlchemy models, so it cannot drift from the code.

Writes two things:
  - docs/DB_SCHEMA.md: the full reference (ER diagram, every table and column, indexes, enums, rules);
  - the diagram block in README.md, between the "schema-diagram" markers.

Run from backend/ (it needs the app's settings, e.g. backend/.env):

    python scripts/generate_schema_doc.py           # rewrite both files
    python scripts/generate_schema_doc.py --check   # exit 1 if either is out of date (a test does the same)
"""
import re
import sys
from pathlib import Path

from sqlalchemy import Enum
from sqlalchemy.dialects import postgresql

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app import models  # noqa: E402,F401  (importing registers every table on Base.metadata)
from app.database import Base  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
DOC_PATH = REPO_ROOT / "docs" / "DB_SCHEMA.md"
README_PATH = REPO_ROOT / "README.md"
START, END = "<!-- schema-diagram:start -->", "<!-- schema-diagram:end -->"

TABLE_NOTES = {
    "users": "Everyone who can sign in. The role (REQUESTER, APPROVER, ADMIN) drives what they may do; the department is optional.",
    "departments": "Master data. Deactivated (`is_active = false`) rather than deleted, so history keeps its department.",
    "categories": "Master data, deactivated rather than deleted. A vendor supplies one or more categories.",
    "vendors": "Master data, deactivated rather than deleted. A PR's or PO's vendor must be active and supply the PR's category.",
    "vendor_categories": "Many-to-many link: which categories a vendor supplies. Rows are removed with either side (`ON DELETE CASCADE`).",
    "purchase_requests": "The request that starts the flow. `status` moves DRAFT, SUBMITTED, APPROVED or REJECTED, then COMPLETED once its order is delivered.",
    "pr_status_history": "Append-only audit trail: one row per status change, with who changed it, when and why. Independent of the mutable `purchase_requests` row.",
    "purchase_orders": "The order raised against an approved PR. Keeps its own `amount` (at most the approved amount) and copies the PR's currency.",
    "deliveries": "Append-only delivery updates against a PO. Each update also moves the PO's `status`; DELIVERED completes the PO and its PR.",
}

COLUMN_NOTES = {
    ("purchase_requests", "amount"): "Requested amount, in `currency`.",
    ("purchase_requests", "required_date"): "A calendar date (sent as UTC midnight), not an instant.",
    ("purchase_requests", "revision_required"): "Set on rejection; cleared only by a real edit, so a rejected PR cannot simply be resubmitted.",
    ("purchase_requests", "vendor_id"): "Optional preferred vendor; a PO always has one.",
    ("purchase_orders", "amount"): "Order price. Never more than the approved PR amount.",
    ("purchase_orders", "currency"): "Copied from the PR.",
    ("pr_status_history", "from_status"): "Empty on the first row (creation).",
    ("deliveries", "delivery_date"): "Required when the status is DELIVERED; a calendar date.",
    ("users", "password_hash"): "bcrypt hash. The password itself is never stored.",
    ("users", "department_id"): "May be empty: a user need not belong to a department.",
}

RULES_IN_CODE = [
    "**One active PO per PR.** The schema allows several POs per PR (`purchase_orders.pr_id` is a plain foreign key); the API refuses a second unless the first is COMPLETED. A partial unique index would enforce it in the database (see the README's future enhancements).",
    "**Status transitions.** Which status may follow which is enforced by the API, not by database constraints. Every PR change is written to `pr_status_history`.",
    "**Vendor must supply the category.** `vendor_categories` records what a vendor supplies; the API checks it when a vendor is chosen on a PR or PO.",
    "**No self-approval, PO amount cap, delivery-date rules.** Business rules in the API layer.",
    "**Most foreign-key columns are not indexed.** Only the primary keys, the unique columns and `vendor_categories.category_id` have indexes. Fine at demo scale; the README lists indexing the rest as a future enhancement.",
]


def pg_type(column) -> str:
    return column.type.compile(dialect=postgresql.dialect())


def mermaid_type(column) -> str:
    if isinstance(column.type, Enum):
        return column.type.name
    sql = pg_type(column).upper()
    for prefix, name in (("VARCHAR", "string"), ("TEXT", "text"), ("NUMERIC", "numeric"), ("TIMESTAMP", "datetime"), ("BOOLEAN", "boolean")):
        if sql.startswith(prefix):
            return name
    return sql.lower()


def unique_columns(table) -> set[str]:
    cols: set[str] = set()
    for constraint in table.constraints:
        if constraint.__class__.__name__ == "UniqueConstraint":
            cols.update(c.name for c in constraint.columns)
    for index in table.indexes:
        if index.unique:
            cols.update(c.name for c in index.columns)
    return cols


def diagram() -> str:
    lines = ["```mermaid", "erDiagram"]
    tables = list(Base.metadata.sorted_tables)
    for table in tables:
        unique = unique_columns(table)
        fk_columns = {fk.parent.name for fk in table.foreign_keys}
        lines.append(f"    {table.name} {{")
        for column in table.columns:
            keys = []
            if column.primary_key:
                keys.append("PK")
            if column.name in fk_columns:
                keys.append("FK")
            if column.name in unique and not column.primary_key:
                keys.append("UK")
            if not keys and not isinstance(column.type, Enum):
                continue  # the diagram lists only keys and status/role columns; the full list is in DB_SCHEMA.md
            suffix = (" " + ", ".join(keys)) if keys else ""
            lines.append(f"        {mermaid_type(column)} {column.name}{suffix}")
        lines.append("    }")
    for table in tables:
        for fk in sorted(table.foreign_keys, key=lambda f: f.parent.name):
            parent = fk.column.table.name
            left = "|o" if fk.parent.nullable else "||"
            lines.append(f'    {parent} {left}--o{{ {table.name} : "{fk.parent.name}"')
    lines.append("```")
    return "\n".join(lines)


def column_notes(table, column) -> str:
    notes = []
    if column.primary_key:
        notes.append("primary key")
    for fk in column.foreign_keys:
        cascade = f", on delete {fk.ondelete.lower()}" if fk.ondelete else ""
        notes.append(f"foreign key to `{fk.column.table.name}.{fk.column.name}`{cascade}")
    if column.name in unique_columns(table) and not column.primary_key:
        notes.append("unique")
    if column.server_default is not None:
        notes.append("default `false`" if "false" in str(column.server_default.arg).lower() else "has a server default")
    extra = COLUMN_NOTES.get((table.name, column.name))
    if extra:
        notes.append(extra)
    return "; ".join(notes)


def table_section(table) -> str:
    out = [f"### `{table.name}`", "", TABLE_NOTES[table.name], "", "| Column | Type | Null | Notes |", "|---|---|---|---|"]
    for column in table.columns:
        out.append(f"| `{column.name}` | `{pg_type(column)}` | {'yes' if column.nullable else 'no'} | {column_notes(table, column)} |")
    indexes = sorted(table.indexes, key=lambda i: i.name)
    if indexes:
        out += ["", "Indexes: " + "; ".join(f"`{i.name}` on ({', '.join(c.name for c in i.columns)}){' (unique)' if i.unique else ''}" for i in indexes) + "."]
    return "\n".join(out)


def enums_section() -> str:
    seen: dict[str, list[str]] = {}
    for table in Base.metadata.sorted_tables:
        for column in table.columns:
            if isinstance(column.type, Enum):
                seen.setdefault(column.type.name, list(column.type.enums))
    rows = ["| PostgreSQL type | Values |", "|---|---|"]
    rows += [f"| `{name}` | {', '.join(f'`{v}`' for v in values)} |" for name, values in sorted(seen.items())]
    note = (
        "`pr_status_from` and `pr_status_to` are separate PostgreSQL types with the same values as `pr_status`: "
        "each of the two status columns of `pr_status_history` declares its own enum."
    )
    return "\n".join(rows) + "\n\n" + note


def render_doc() -> str:
    parts = [
        "# Database schema",
        "",
        "> Generated from the SQLAlchemy models by `backend/scripts/generate_schema_doc.py`. Do not edit by hand: run the script,",
        "> and see `backend/tests/test_schema_doc.py`, which fails when this file is out of date.",
        "",
        "PostgreSQL 16, managed with Alembic migrations (`backend/alembic/versions`). Ids are UUID strings generated by the",
        "application. Timestamps (`created_at`, `updated_at`, `changed_at`) are stored as UTC; dates chosen by a user (required",
        "date, delivery date) are calendar dates, not instants.",
        "",
        "## Relationships",
        "",
        "`||--o{` is one-to-many; `|o--o{` is one-to-many where the link is optional. The diagram lists only keys and status/role",
        "columns; every column is in the tables below.",
        "",
        diagram(),
        "",
        "## Tables",
        "",
        "\n\n".join(table_section(t) for t in Base.metadata.sorted_tables),
        "",
        "## Enumerated types",
        "",
        enums_section(),
        "",
        "## Rules enforced in the application, not the schema",
        "",
        "\n".join(f"- {rule}" for rule in RULES_IN_CODE),
        "",
    ]
    return "\n".join(parts)


def render_readme(current: str) -> str:
    block = f"{START}\n{diagram()}\n{END}"
    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.S)
    if not pattern.search(current):
        raise SystemExit(f"README.md has no {START} ... {END} block to update.")
    return pattern.sub(lambda _m: block, current)


def normalise(text: str) -> str:
    return text.replace("\r\n", "\n")


def stale_files() -> list[str]:
    """Paths (relative to the repo) whose committed content differs from what the models generate."""
    stale = []
    if not DOC_PATH.exists() or normalise(DOC_PATH.read_text(encoding="utf-8")) != render_doc():
        stale.append("docs/DB_SCHEMA.md")
    readme = normalise(README_PATH.read_text(encoding="utf-8"))
    if readme != render_readme(readme):
        stale.append("README.md")
    return stale


def main() -> None:
    if "--check" in sys.argv[1:]:
        stale = stale_files()
        if stale:
            raise SystemExit("Out of date: " + ", ".join(stale) + ". Run: python scripts/generate_schema_doc.py")
        print("Schema documentation is up to date.")
        return
    DOC_PATH.parent.mkdir(parents=True, exist_ok=True)
    DOC_PATH.write_text(render_doc(), encoding="utf-8", newline="\n")
    readme = normalise(README_PATH.read_text(encoding="utf-8"))
    README_PATH.write_text(render_readme(readme), encoding="utf-8", newline="\n")
    print(f"Wrote {DOC_PATH.relative_to(REPO_ROOT)} and updated the diagram in README.md")


if __name__ == "__main__":
    main()
