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
        seed.main(env_file, [])
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
        seed.main(env_file, [])
    finally:
        os.environ.pop("SEED_ADMIN_PASSWORD", None)

    capsys.readouterr()
    with SessionLocal() as session:
        admin = session.query(User).filter(User.email == "admin@procureflow.com").one()
        assert verify_password("from-the-shell-1", admin.password_hash)
        assert not verify_password("from-the-file", admin.password_hash)


# ---------- --sync-passwords ----------


def test_explicit_passwords_only_include_roles_that_are_set():
    from app.seed import explicit_passwords

    assert explicit_passwords({"SEED_ADMIN_PASSWORD": "admin-pass-1", "SEED_APPROVER_PASSWORD": "  "}) == {
        UserRole.ADMIN: "admin-pass-1"
    }
    assert explicit_passwords({}) == {}  # nothing is generated
    with pytest.raises(ValueError, match="SEED_REQUESTER_PASSWORD"):
        explicit_passwords({"SEED_REQUESTER_PASSWORD": "short"})


def test_sync_updates_existing_accounts_for_the_roles_that_have_a_password(db):
    from app.seed import sync_passwords

    seed_database(db, resolve_passwords(ENV)[0])
    updated, current = sync_passwords(db, {UserRole.ADMIN: "brand-new-admin-1"})

    assert updated == ["admin@procureflow.com"] and current == []
    users = {u.email: u for u in db.query(User).all()}
    assert verify_password("brand-new-admin-1", users["admin@procureflow.com"].password_hash)
    assert not verify_password("admin-pass-1", users["admin@procureflow.com"].password_hash)
    # roles without a value are left exactly as they were
    assert verify_password("requester-pass-1", users["rohan.sharma@procureflow.com"].password_hash)
    assert verify_password("approver-pass-1", users["sameer.khan@procureflow.com"].password_hash)


def test_sync_covers_every_account_of_a_role_and_is_safe_to_repeat(db):
    from app.seed import sync_passwords

    seed_database(db, resolve_passwords(ENV)[0])
    wanted = {UserRole.REQUESTER: "new-requester-9", UserRole.APPROVER: "new-approver-9"}

    updated, current = sync_passwords(db, wanted)
    assert sorted(updated) == [
        "amit.patel@procureflow.com",
        "priya.nair@procureflow.com",
        "rohan.sharma@procureflow.com",
        "sameer.khan@procureflow.com",
    ]
    assert current == []

    again_updated, again_current = sync_passwords(db, wanted)  # nothing to do the second time
    assert again_updated == [] and len(again_current) == 4


def test_sync_creates_nothing_and_never_touches_other_users(db):
    from app.models import UserRole as Role
    from app.seed import sync_passwords

    assert sync_passwords(db, {Role.ADMIN: "whatever-pass-1"}) == ([], [])  # empty database: still empty
    assert db.query(User).count() == 0

    seed_database(db, resolve_passwords(ENV)[0])
    outsider = User(name="Outsider", email="outsider@example.com", password_hash="untouched-hash", role=Role.REQUESTER)
    db.add(outsider)
    db.commit()

    sync_passwords(db, {Role.REQUESTER: "new-requester-9"})
    assert db.query(User).filter(User.email == "outsider@example.com").one().password_hash == "untouched-hash"
    assert db.query(User).count() == len(ACCOUNTS) + 1


def test_synced_password_works_through_the_api_and_the_old_one_stops(client, db):
    from app.seed import sync_passwords

    seed_database(db, resolve_passwords(ENV)[0])
    sync_passwords(db, {UserRole.ADMIN: "synced-admin-pass"})
    login = lambda pw: client.post("/api/auth/login", json={"email": "admin@procureflow.com", "password": pw}).status_code
    assert login("synced-admin-pass") == 200
    assert login("admin-pass-1") == 401


def test_main_sync_reads_the_env_file_and_reports_without_printing_passwords(app_db, tmp_path, monkeypatch, capsys):
    import os

    from app import seed
    from app.database import SessionLocal

    with SessionLocal() as session:
        seed.seed_database(session, resolve_passwords(ENV)[0])

    env_file = tmp_path / ".env"
    env_file.write_text("SEED_ADMIN_PASSWORD=from-file-sync-1\n", encoding="utf-8")
    for variable in seed.PASSWORD_ENV.values():
        monkeypatch.delenv(variable, raising=False)
    try:
        seed.main(env_file, ["--sync-passwords"])
    finally:
        os.environ.pop("SEED_ADMIN_PASSWORD", None)

    out = capsys.readouterr().out
    assert "1 updated, 0 already current" in out
    assert "admin@procureflow.com" in out
    assert "SEED_REQUESTER_PASSWORD" in out and "SEED_APPROVER_PASSWORD" in out  # named as left alone
    assert "from-file-sync-1" not in out
    with SessionLocal() as session:
        admin = session.query(User).filter(User.email == "admin@procureflow.com").one()
        assert verify_password("from-file-sync-1", admin.password_hash)


def test_main_sync_needs_at_least_one_password_and_rejects_unknown_options(app_db, tmp_path, monkeypatch):
    from app import seed

    for variable in seed.PASSWORD_ENV.values():
        monkeypatch.delenv(variable, raising=False)
    empty = tmp_path / ".env"
    empty.write_text("", encoding="utf-8")
    with pytest.raises(SystemExit, match="Nothing to sync"):
        seed.main(empty, ["--sync-passwords"])
    with pytest.raises(SystemExit, match="Unknown argument"):
        seed.main(empty, ["--reset-everything"])
