"""Test setup.

Tests run against an isolated database and never touch the development one. By default that is an
in-memory SQLite database; set TEST_DATABASE_URL to a PostgreSQL URL to run the same suite on Postgres.
"""
import os

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-pytest")
TEST_DB_URL = os.environ.get("TEST_DATABASE_URL", "sqlite://")
os.environ["DATABASE_URL"] = TEST_DB_URL  # satisfies app settings; the app's own engine is unused in tests
# The app has no built-in defaults, so the tests pin every setting: they never depend on someone's .env or shell.
os.environ.update(
    JWT_ALGORITHM="HS256",
    ACCESS_TOKEN_EXPIRE_MINUTES="480",
    LOG_LEVEL="INFO",
    CORS_ORIGINS="http://localhost:5173,http://127.0.0.1:5173",
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app import models  # noqa: E402
from app.auth import hash_password  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from tests.helpers import PASSWORD, Api, World, email  # noqa: E402

if TEST_DB_URL.startswith("sqlite"):
    engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool)
else:
    engine = create_engine(TEST_DB_URL)
TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)

_PASSWORD_HASH = hash_password(PASSWORD)  # bcrypt is slow, so hash once and share it


@pytest.fixture(scope="session", autouse=True)
def _schema():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture()
def db(_schema):
    session = TestingSession()
    yield session
    session.rollback()
    session.close()
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())


@pytest.fixture()
def client(db):
    def override_get_db():
        session = TestingSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def world(db) -> World:
    """Two departments, three categories, five vendors and one user per role/persona."""
    depts = {"ops": models.Department(name="Operations"), "it": models.Department(name="IT")}
    cats = {
        "parts": models.Category(name="Spare Parts"),
        "hardware": models.Category(name="IT Hardware"),
        "catering": models.Category(name="Catering Services"),
    }
    db.add_all([*depts.values(), *cats.values()])
    db.flush()

    vendor_specs = {
        "gulf": ("Gulf Marine Supplies", ["parts"], True),
        "tech": ("TechZone Computers", ["hardware"], True),
        "prime": ("Prime Catering", ["catering"], True),
        "multi": ("Multi Supplier", ["parts", "hardware"], True),
        "dormant": ("Dormant Vendor", ["parts"], False),
    }
    vendors = {}
    for key, (name, category_keys, active) in vendor_specs.items():
        vendor = models.Vendor(name=name, is_active=active)
        vendor.categories = [cats[c] for c in category_keys]
        vendors[key] = vendor
    db.add_all(vendors.values())

    user_specs = {
        "admin": models.UserRole.ADMIN,
        "rohan": models.UserRole.REQUESTER,
        "priya": models.UserRole.REQUESTER,
        "sameer": models.UserRole.APPROVER,
        "amit": models.UserRole.APPROVER,
    }
    users = {
        key: models.User(
            name=key.title(), email=email(key), password_hash=_PASSWORD_HASH, role=role, department_id=depts["ops"].id
        )
        for key, role in user_specs.items()
    }
    db.add_all(users.values())
    db.commit()

    return World(
        dept={k: v.id for k, v in depts.items()},
        cat={k: v.id for k, v in cats.items()},
        vendor={k: v.id for k, v in vendors.items()},
        user={k: v.id for k, v in users.items()},
    )


@pytest.fixture()
def api(client, world) -> Api:
    return Api(client, world)
