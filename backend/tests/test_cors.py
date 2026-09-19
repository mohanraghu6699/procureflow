from app.config import Settings


def preflight(client, origin):
    return client.options(
        "/api/auth/login",
        headers={"Origin": origin, "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"},
    )


def test_default_origins_are_the_local_dev_servers(client):
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
        cors_origins=" https://app.example.com/ , https://other.example.com ,, ",
    )
    assert s.cors_origin_list == ["https://app.example.com", "https://other.example.com"]
