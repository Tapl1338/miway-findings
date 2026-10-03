"""Boot smoke test: the app must START.

The T122-A merge (2026-09-19) deleted ``_IDENTITY_MODULES`` while
``log_startup_identity()`` still referenced it - every real uvicorn boot
crashed with NameError before binding, yet all router-scoped gates passed
because they imported routers directly and never booted the app. This test
exists so that class of failure can never pass a builder gate again: it
boots the FULL app via TestClient (which runs the lifespan/startup path)
and asserts the health endpoint answers.

Rule for future builder rounds: any backend change touches
``backend/app/main.py`` or any included router -> this test must be in the
gate set. It is deliberately cheap (<2s, no data files needed: the health
endpoint does not require the leaderboard sample).
"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    # Import inside the fixture so a collection-time import error (the
    # T122-A failure shape) surfaces as THIS test's failure, not a suite
    # collection error that skips everything else.
    from app.main import app

    with TestClient(app) as c:  # context manager runs lifespan/startup
        yield c


def test_app_boots_and_lifespan_runs(client) -> None:
    """The full app must start: lifespan runs, no NameError/ImportError."""
    assert client.app is not None


def test_health_endpoint_answers(client) -> None:
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body.get("status") == "ok"


def test_every_included_router_registers_a_route(client) -> None:
    """A router wired in main.py must actually appear in the route table.

    Catches the silent-fallback shape: an include_router() call whose
    router failed to import contributes zero routes but raises nothing
    (observed on the stale VPS snapshot, 2026-09-19). Starlette wraps
    included routers in _IncludedRouter (sub-paths hidden from app.routes),
    so resolve via the OpenAPI schema, which flattens everything.
    """
    spec = client.get("/openapi.json").json()
    paths = list(spec["paths"].keys())
    # One representative endpoint per included router (main.py:157-172).
    expected = [
        "/api/health",
        "/api/routes/circuity",  # circuity router
        "/api/public/early-departures",  # public_leaderboard router (T122-A)
        "/api/forecast/scoreboard",  # forecast router (T125 live twin)
    ]
    missing = [p for p in expected if not any(p in path for path in paths)]
    assert not missing, (
        f"routers registered in main.py but missing from OpenAPI: {missing}"
    )
