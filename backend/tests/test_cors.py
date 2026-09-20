from app.config import Settings


def preflight(client, origin):
    return client.options(
        "/api/auth/login",
        headers={"Origin": origin, "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"},
    )


def test_configured_origins_may_call_the_api(client):
    allowed = preflight(client, "http://localhost:5173")
    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_unlisted_origins_are_not_allowed(client):
    blocked = preflight(client, "https://evil.example.com")
    assert "access-control-allow-origin" not in blocked.headers


def test_origins_come_from_a_comma_separated_setting():
    s = Settings(
        database_url="sqlite://",
        jwt_secret_key="x",
        jwt_algorithm="HS256",
        access_token_expire_minutes=60,
        log_level="INFO",
        cors_origins=" https://app.example.com/ , https://other.example.com ,, ",
    )
    assert s.cors_origin_list == ["https://app.example.com", "https://other.example.com"]


def test_unknown_keys_in_the_env_file_do_not_break_the_settings(tmp_path, monkeypatch):
    monkeypatch.delenv("ACCESS_TOKEN_EXPIRE_MINUTES")  # the tests pin it; a real variable outranks the file
    env_file = tmp_path / ".env"
    lines = [
        "DATABASE_URL=sqlite://",
        "JWT_SECRET_KEY=x",
        "JWT_ALGORITHM=HS256",
        "ACCESS_TOKEN_EXPIRE_MINUTES=123",
        "LOG_LEVEL=INFO",
        "CORS_ORIGINS=http://localhost:5173",
        "SEED_ADMIN_PASSWORD=whatever-1",
        "SOME_OTHER_TOOL_SETTING=1",
    ]
    env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    s = Settings(_env_file=env_file)
    assert s.access_token_expire_minutes == 123  # proves the file was read, and the extra keys were ignored
