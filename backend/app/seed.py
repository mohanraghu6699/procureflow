"""Seed the database with master data and login users.

Purchase requests, orders and deliveries are intentionally not seeded —
create them through the UI.

Passwords are never stored in the source. Set them per role with the environment variables
SEED_ADMIN_PASSWORD, SEED_REQUESTER_PASSWORD and SEED_APPROVER_PASSWORD (each at least 8 characters),
either in the real environment or in backend/.env. Any that is not set gets a random password, printed once
when the users are created.

Run with: venv\\Scripts\\python -m app.seed

Seeding only happens on an EMPTY database, so changing those variables later does not change accounts that
already exist. To make the existing seeded accounts match the variables, run:

    python -m app.seed --sync-passwords

It sets each seeded account's password to the one for its role, for the roles that have a variable set (nothing
is generated, no account is created, and other users are never touched). It is safe to repeat.
"""
import os
import secrets
import sys
from pathlib import Path
from typing import Mapping

from dotenv import load_dotenv
from sqlalchemy.orm import Session

from app.auth import hash_password, verify_password
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


def explicit_passwords(env: Mapping[str, str] = os.environ) -> dict[UserRole, str]:
    """Only the roles that have a password set in the environment. Nothing is generated."""
    passwords: dict[UserRole, str] = {}
    for role, variable in PASSWORD_ENV.items():
        value = (env.get(variable) or "").strip()
        if not value:
            continue
        if len(value) < MIN_PASSWORD_LENGTH:
            raise ValueError(f"{variable} must be at least {MIN_PASSWORD_LENGTH} characters")
        passwords[role] = value
    return passwords


def sync_passwords(db: Session, passwords: Mapping[UserRole, str]) -> tuple[list[str], list[str]]:
    """Set each existing seeded account's password to the one for its role.

    Only the accounts in ACCOUNTS whose role has a password are considered; nothing is created and no other user
    is touched. Returns (emails updated, emails that already had the right password).
    """
    role_by_email = {email: role for _name, email, role, _department in ACCOUNTS}
    updated: list[str] = []
    current: list[str] = []
    for user in db.query(User).filter(User.email.in_(list(role_by_email))).order_by(User.email).all():
        password = passwords.get(role_by_email[user.email])
        if password is None:
            continue
        if verify_password(password, user.password_hash):
            current.append(user.email)
        else:
            user.password_hash = hash_password(password)
            updated.append(user.email)
    db.commit()
    return updated, current


ENV_FILE = Path(__file__).resolve().parent.parent / ".env"  # backend/.env


def sync_main() -> None:
    passwords = explicit_passwords()
    if not passwords:
        raise SystemExit("Nothing to sync: set at least one of " + ", ".join(PASSWORD_ENV.values()) + ".")
    db = SessionLocal()
    try:
        updated, current = sync_passwords(db, passwords)
    finally:
        db.close()
    print(f"Passwords synced from the environment: {len(updated)} updated, {len(current)} already current.")
    for email in updated:
        print(f"  updated  {email}")
    unset = [PASSWORD_ENV[role] for role in PASSWORD_ENV if role not in passwords]
    if unset:
        print("Left alone (not set): " + ", ".join(unset))


def main(env_file: Path = ENV_FILE, argv: list[str] | None = None) -> None:
    args = sys.argv[1:] if argv is None else argv
    unknown = [a for a in args if a != "--sync-passwords"]
    if unknown:
        raise SystemExit(f"Unknown argument(s): {' '.join(unknown)}. The only option is --sync-passwords.")
    # Values from backend/.env are picked up too; a variable already set in the real environment wins.
    load_dotenv(env_file)
    if "--sync-passwords" in args:
        sync_main()
        return
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
