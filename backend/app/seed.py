"""Seed the database with master data and login users.

Purchase requests, orders and deliveries are intentionally not seeded —
create them through the UI.

Passwords are never stored in the source. Set them per role with the environment variables
SEED_ADMIN_PASSWORD, SEED_REQUESTER_PASSWORD and SEED_APPROVER_PASSWORD (each at least 8 characters),
either in the real environment or in backend/.env. Any that is not set gets a random password, printed once
when the users are created.

Run with: venv\\Scripts\\python -m app.seed
"""
import os
import secrets
from pathlib import Path
from typing import Mapping

from dotenv import load_dotenv
from sqlalchemy.orm import Session

from app.auth import hash_password
from app.database import Base, SessionLocal, engine
from app.models import Category, Department, User, UserRole, Vendor

PASSWORD_ENV = {
    UserRole.ADMIN: "SEED_ADMIN_PASSWORD",
    UserRole.REQUESTER: "SEED_REQUESTER_PASSWORD",
    UserRole.APPROVER: "SEED_APPROVER_PASSWORD",
}
MIN_PASSWORD_LENGTH = 8
# No look-alike characters (0/O, 1/l/I), so a printed password can be typed by hand.
_ALPHABET = "abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"

DEPARTMENTS = ["Operations", "HSSE", "IT", "Administration", "Marine", "Finance"]
CATEGORIES = [
    "Spare Parts",
    "Safety Equipment",
    "IT Hardware",
    "Office Furniture",
    "Catering Services",
    "Professional Services",
]
VENDORS = [
    ("Gulf Marine Supplies LLC", "sales@gulfmarine.ae", ["Spare Parts", "Safety Equipment"]),
    ("SafetyFirst Equipment Trading", "info@safetyfirst.ae", ["Safety Equipment"]),
    ("TechZone Computers", "orders@techzone.ae", ["IT Hardware"]),
    ("Al Futtaim Office Solutions", "contact@affice.ae", ["Office Furniture", "IT Hardware"]),
    ("Prime Catering Co.", "events@primecatering.ae", ["Catering Services"]),
    ("Gulf Advisory Partners", "engage@gulfadvisory.ae", ["Professional Services"]),
]
# (name, email, role, department)
ACCOUNTS = [
    ("Admin User", "admin@procureflow.com", UserRole.ADMIN, "Administration"),
    ("Rohan Sharma", "rohan.sharma@procureflow.com", UserRole.REQUESTER, "Operations"),
    ("Priya Nair", "priya.nair@procureflow.com", UserRole.REQUESTER, "HSSE"),
    ("Sameer Khan", "sameer.khan@procureflow.com", UserRole.APPROVER, "IT"),
    ("Amit Patel", "amit.patel@procureflow.com", UserRole.APPROVER, "Marine"),
]


def random_password(length: int = 14) -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(length))


def resolve_passwords(env: Mapping[str, str] = os.environ) -> tuple[dict[UserRole, str], set[UserRole]]:
    """One password per role from the environment, generating a random one for any role left unset.

    Returns the passwords and the set of roles whose password was generated (so it can be shown once).
    """
    passwords: dict[UserRole, str] = {}
    generated: set[UserRole] = set()
    for role, variable in PASSWORD_ENV.items():
        value = (env.get(variable) or "").strip()
        if not value:
            passwords[role] = random_password()
            generated.add(role)
        elif len(value) < MIN_PASSWORD_LENGTH:
            raise ValueError(f"{variable} must be at least {MIN_PASSWORD_LENGTH} characters")
        else:
            passwords[role] = value
    return passwords, generated


def seed_database(db: Session, passwords: Mapping[UserRole, str]) -> bool:
    """Create the master data and login users. Does nothing (returns False) if any user already exists."""
    if db.query(User).count() > 0:
        return False

    departments = {name: Department(name=name) for name in DEPARTMENTS}
    db.add_all(departments.values())
    categories = {name: Category(name=name) for name in CATEGORIES}
    db.add_all(categories.values())

    for name, email, category_names in VENDORS:
        vendor = Vendor(name=name, contact_email=email, contact_phone="+971-4-1234567")
        vendor.categories = [categories[c] for c in category_names]
        db.add(vendor)
    db.flush()

    hashes = {role: hash_password(password) for role, password in passwords.items()}  # bcrypt is slow: once per role
    db.add_all(
        User(
            name=name,
            email=email,
            password_hash=hashes[role],
            role=role,
            department_id=departments[department].id,
        )
        for name, email, role, department in ACCOUNTS
    )
    db.commit()
    return True


ENV_FILE = Path(__file__).resolve().parent.parent / ".env"  # backend/.env


def main(env_file: Path = ENV_FILE) -> None:
    # Values from backend/.env are picked up too; a variable already set in the real environment wins.
    load_dotenv(env_file)
    passwords, generated = resolve_passwords()
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if not seed_database(db, passwords):
            print("Database already seeded. Skipping.")
            return
    finally:
        db.close()

    print("Database seeded successfully.")
    print("Login accounts:")
    for _name, email, role, _department in ACCOUNTS:
        print(f"  {role.value:<10} {email}")
    for role in PASSWORD_ENV:
        if role in generated:
            print(f"Generated {role.value} password (shown once, note it now): {passwords[role]}")
        else:
            print(f"{role.value} password: taken from {PASSWORD_ENV[role]}")


if __name__ == "__main__":
    main()
