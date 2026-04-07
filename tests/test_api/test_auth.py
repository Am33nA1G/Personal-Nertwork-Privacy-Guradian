"""Tests for JWT auth and first-run setup."""

import json

import pytest


@pytest.mark.asyncio
async def test_login_success(client):
    response = await client.post("/api/v1/auth/login", json={"password": "testpass"})

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["access_token"]
    assert payload["refresh_token"]
    assert payload["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    response = await client.post("/api/v1/auth/login", json={"password": "wrongpass"})

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_protected_route_no_token(client):
    response = await client.get("/api/v1/status")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_protected_route_valid_token(client, auth_headers):
    response = await client.get("/api/v1/status", headers=auth_headers)

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_health_no_auth_required(client):
    response = await client.get("/api/v1/health")

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_setup_creates_auth_file(tmp_path, mock_db_pool, test_config):
    from fastapi import FastAPI

    from pnpg.api.auth import router as auth_router
    from pnpg.api.middleware import setup_rate_limiting

    app = FastAPI()
    setup_rate_limiting(app)
    app.state.db_pool = mock_db_pool
    app.state.config = test_config
    app.state.config["auth_file"] = str(tmp_path / "data" / "auth.json")
    app.state.detector_state = None
    app.state.password_hash = None
    app.state.needs_setup = True
    app.state.probe_type = "libpcap"
    app.state.drop_counter = [0]
    app.state.stop_event = None
    app.include_router(auth_router, prefix="/api/v1")

    async with pytest.importorskip("httpx").AsyncClient(
        transport=pytest.importorskip("httpx").ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post("/api/v1/auth/setup", json={"password": "newpass"})

    assert response.status_code == 200
    auth_file = tmp_path / "data" / "auth.json"
    assert auth_file.exists()
    assert "hash" in json.loads(auth_file.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# resolve_jwt_secret paths
# ---------------------------------------------------------------------------


def test_resolve_jwt_secret_from_config():
    """If jwt_secret is already in config, return it without env/file lookup."""
    from pnpg.api.auth import resolve_jwt_secret

    config = {"jwt_secret": "already-set"}

    secret = resolve_jwt_secret(config)

    assert secret == "already-set"


def test_resolve_jwt_secret_from_env(monkeypatch, tmp_path):
    """jwt_secret is loaded from PNPG_JWT_SECRET env var when not in config."""
    from pnpg.api.auth import resolve_jwt_secret

    monkeypatch.setenv("PNPG_JWT_SECRET", "env-secret")
    config = {"jwt_secret": ""}

    secret = resolve_jwt_secret(config)

    assert secret == "env-secret"
    assert config["jwt_secret"] == "env-secret"


def test_resolve_jwt_secret_from_file(tmp_path, monkeypatch):
    """jwt_secret is loaded from data/secrets.json when env var is absent."""
    import json as _json
    from pnpg.api.auth import resolve_jwt_secret
    from unittest.mock import patch

    monkeypatch.delenv("PNPG_JWT_SECRET", raising=False)
    secrets_file = tmp_path / "data" / "secrets.json"
    secrets_file.parent.mkdir(parents=True)
    secrets_file.write_text(_json.dumps({"jwt_secret": "file-secret"}))

    config = {"jwt_secret": ""}

    with patch("pnpg.api.auth.Path", side_effect=lambda p: tmp_path / p if p == "data/secrets.json" else __import__("pathlib").Path(p)):
        # Directly test by temporarily changing the path referenced in the function
        import pnpg.api.auth as auth_mod
        original_path = auth_mod.Path

        class PatchedPath:
            def __init__(self, p):
                if p == "data/secrets.json":
                    self._path = secrets_file
                else:
                    self._path = __import__("pathlib").Path(p)

            def exists(self):
                return self._path.exists()

            def read_text(self, encoding="utf-8"):
                return self._path.read_text(encoding=encoding)

            @property
            def parent(self):
                return self._path.parent

        auth_mod.Path = PatchedPath
        try:
            secret = resolve_jwt_secret(config)
        finally:
            auth_mod.Path = original_path

    assert secret == "file-secret"
    assert config["jwt_secret"] == "file-secret"


def test_resolve_jwt_secret_autogenerate(tmp_path, monkeypatch):
    """jwt_secret is auto-generated and written to data/secrets.json."""
    import pnpg.api.auth as auth_mod
    from unittest.mock import patch

    monkeypatch.delenv("PNPG_JWT_SECRET", raising=False)
    config = {"jwt_secret": ""}

    secrets_file = tmp_path / "data" / "secrets.json"

    original_path = auth_mod.Path

    class PatchedPath:
        def __init__(self, p):
            if p == "data/secrets.json":
                self._path = secrets_file
            else:
                self._path = __import__("pathlib").Path(p)

        def exists(self):
            return self._path.exists()

        def read_text(self, encoding="utf-8"):
            return self._path.read_text(encoding=encoding)

        def write_text(self, text, encoding="utf-8"):
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(text, encoding=encoding)

        @property
        def parent(self):
            class _Parent:
                def __init__(self, p):
                    self._p = p

                def mkdir(self, parents=False, exist_ok=False):
                    self._p.mkdir(parents=parents, exist_ok=exist_ok)

            return _Parent(self._path.parent)

    auth_mod.Path = PatchedPath
    try:
        secret = auth_mod.resolve_jwt_secret(config)
    finally:
        auth_mod.Path = original_path

    assert secret
    assert len(secret) == 64  # token_hex(32) produces 64 hex chars
    assert config["jwt_secret"] == secret


# ---------------------------------------------------------------------------
# get_current_user edge cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_protected_route_invalid_jwt(client):
    """Invalid JWT signature returns 401."""
    response = await client.get(
        "/api/v1/status",
        headers={"Authorization": "Bearer not.a.valid.jwt"},
    )

    assert response.status_code == 401


# ---------------------------------------------------------------------------
# setup_auth already configured returns 409
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_setup_auth_already_configured(client):
    """POST /auth/setup returns 409 when needs_setup is False."""
    response = await client.post("/api/v1/auth/setup", json={"password": "newpass"})

    assert response.status_code == 409


# ---------------------------------------------------------------------------
# login when needs_setup is True returns 503
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_login_needs_setup_returns_503(app_with_state, tmp_path):
    """POST /auth/login returns 503 when needs_setup is True."""
    import httpx

    app_with_state.state.needs_setup = True

    transport = httpx.ASGITransport(app=app_with_state)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        response = await c.post("/api/v1/auth/login", json={"password": "testpass"})

    assert response.status_code == 503
