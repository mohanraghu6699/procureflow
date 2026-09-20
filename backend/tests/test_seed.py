import pytest

from app.auth import verify_password
from app.models import Category, Department, User, UserRole, Vendor
from app.seed import ACCOUNTS, MIN_PASSWORD_LENGTH, random_password, resolve_passwords, seed_database

ENV = {
    "SEED_ADMIN_PASSWORD": "admin-pass-1",
    "SEED_REQUESTER_PASSWORD": "requester-pass-1",
    "SEED_APPROVER_PASSWORD": "approver-pass-1",
}


@pytest.fixture()
def app_db():
    """The app's own database (what seed.main() writes to), emptied afterwards so tests stay independent."""
    from app.database import Base, engine

    Base.metadata.create_all(engine)
    yield
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())


def test_passwords_come_from_the_environment():
    passwords, generated = resolve_passwords(ENV)
    assert passwords == {
        UserRole.ADMIN: "admin-pass-1",
        UserRole.REQUESTER: "requester-pass-1",
        UserRole.APPROVER: "approver-pass-1",
    }
    assert generated == set()


def test_unset_or_blank_variables_get_a_random_password():
    passwords, generated = resolve_passwords({"SEED_ADMIN_PASSWORD": "admin-pass-1", "SEED_REQUESTER_PASSWORD": "   "})
    assert passwords[UserRole.ADMIN] == "admin-pass-1"
    assert generated == {UserRole.REQUESTER, UserRole.APPROVER}
    for role in generated:
        assert len(passwords[role]) >= 12
    assert passwords[UserRole.REQUESTER] != passwords[UserRole.APPROVER]


def test_generated_passwords_are_random_and_typable():
    samples = {random_password() for _ in range(50)}
    assert len(samples) == 50
    assert not set("".join(samples)) & set("0O1lI")  # no look-alike characters


def test_short_passwords_are_rejected():
    with pytest.raises(ValueError, match="SEED_ADMIN_PASSWORD"):
        resolve_passwords({"SEED_ADMIN_PASSWORD": "x" * (MIN_PASSWORD_LENGTH - 1)})


def test_seeding_creates_master_data_and_users_with_those_passwords(db):
    passwords, _ = resolve_passwords(ENV)
    assert seed_database(db, passwords) is True

    assert db.query(Department).count() == 6
    assert db.query(Category).count() == 6
    assert db.query(Vendor).count() == 6
    users = {u.email: u for u in db.query(User).all()}
    assert len(users) == len(ACCOUNTS)
    for _name, email, role, _department in ACCOUNTS:
        assert users[email].role == role
        assert verify_password(passwords[role], users[email].password_hash)
        assert not verify_password("wrong-password", users[email].password_hash)


def test_no_well_known_default_password_is_accepted(db):
    seed_database(db, resolve_passwords(ENV)[0])
    for user in db.query(User).all():
        for old_default in ("Admin@123", "Requester@123", "Approver@123"):
            assert not verify_password(old_default, user.password_hash)


def test_seeding_twice_changes_nothing(db):
    passwords, _ = resolve_passwords(ENV)
    assert seed_database(db, passwords) is True
    assert seed_database(db, {role: "another-pass-9" for role in passwords}) is False
    assert db.query(User).count() == len(ACCOUNTS)
    admin = db.query(User).filter(User.email == "admin@procureflow.com").one()
    assert verify_password("admin-pass-1", admin.password_hash)  # first run's password is untouched


def test_seeded_users_can_log_in_through_the_api(client, db):
    passwords, _ = resolve_passwords(ENV)
    seed_database(db, passwords)
    ok = client.post("/api/auth/login", json={"email": "sameer.khan@procureflow.com", "password": "approver-pass-1"})
    assert ok.status_code == 200 and ok.json()["user"]["role"] == "APPROVER"
    bad = client.post("/api/auth/login", json={"email": "sameer.khan@procureflow.com", "password": "Approver@123"})
    assert bad.status_code == 401


def test_main_reads_passwords_from_an_env_file(app_db, tmp_path, monkeypatch, capsys):
    import os

    from app import seed
    from app.database import SessionLocal

    env_file = tmp_path / ".env"
    env_file.write_text("SEED_ADMIN_PASSWORD=from-env-file-1\n", encoding="utf-8")
    for variable in seed.PASSWORD_ENV.values():
        monkeypatch.delenv(variable, raising=False)  # start with none set in the real environment
    try:
        seed.main(env_file)
    finally:
        os.environ.pop("SEED_ADMIN_PASSWORD", None)  # load_dotenv put it into the real environment

    out = capsys.readouterr().out
    assert "ADMIN password: taken from SEED_ADMIN_PASSWORD" in out
    assert "Generated REQUESTER password" in out and "Generated APPROVER password" in out
    with SessionLocal() as session:
        admin = session.query(User).filter(User.email == "admin@procureflow.com").one()
        assert verify_password("from-env-file-1", admin.password_hash)


def test_a_real_environment_variable_beats_the_env_file(app_db, tmp_path, monkeypatch, capsys):
    import os

    from app import seed
    from app.database import SessionLocal

    env_file = tmp_path / ".env"
    env_file.write_text("SEED_ADMIN_PASSWORD=from-the-file\n", encoding="utf-8")
    monkeypatch.setenv("SEED_ADMIN_PASSWORD", "from-the-shell-1")
    try:
        seed.main(env_file)
    finally:
        os.environ.pop("SEED_ADMIN_PASSWORD", None)

    capsys.readouterr()
    with SessionLocal() as session:
        admin = session.query(User).filter(User.email == "admin@procureflow.com").one()
        assert verify_password("from-the-shell-1", admin.password_hash)
        assert not verify_password("from-the-file", admin.password_hash)
