"""The Redis rate limiter must be an optional dependency.

transfers.py uses a Redis sliding-window limiter with an in-memory fallback.
The first version imported ``redis.asyncio`` at module top, so the whole API
failed to start on any environment without redis installed (bare venv, CI)
even though the fallback was fully implemented. These tests pin the contract:
the module imports with redis absent, and the fallback actually enforces the
POST limit.

Both tests run the assertion in a **subprocess**: the parent pytest process
may already have ``redis`` imported (real installs), and Python caches
modules, so only a fresh interpreter can prove the no-redis import path.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]

NO_REDIS_PROBE = """
import builtins, sys

real = builtins.__import__
def blocked(name, *a, **k):
    if name.split(".")[0] == "redis":
        raise ModuleNotFoundError(f"blocked: {name}")
    return real(name, *a, **k)
builtins.__import__ = blocked
sys.modules.pop("redis", None)
sys.modules.pop("redis.asyncio", None)

import app.routers.transfers as t
assert t.redis is None, "redis module should be None when not installed"
print("IMPORT-OK")
"""


def test_module_imports_without_redis_installed():
    r = subprocess.run(
        [sys.executable, "-c", NO_REDIS_PROBE],
        cwd=BACKEND,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert r.returncode == 0, f"import failed without redis:\n{r.stderr[-1500:]}"
    assert "IMPORT-OK" in r.stdout


def test_in_memory_fallback_enforces_limit_without_redis():
    """20-request POST limit: requests 21+ must 429 via the fallback path."""
    probe = NO_REDIS_PROBE.replace(
        'print("IMPORT-OK")',
        """
import asyncio, time
from types import SimpleNamespace
from fastapi import HTTPException

async def main():
    t._RATE_LIMIT_WINDOW = 60.0
    t._RATE_LIMIT_MAX_POST = 5  # small for a fast test
    req = SimpleNamespace(client=SimpleNamespace(host="198.51.100.7"))
    blocked = 0
    for i in range(8):
        try:
            await t._check_rate_limit(req, "probe")
        except HTTPException as e:
            assert e.status_code == 429
            blocked += 1
    assert blocked == 3, f"expected 3 blocked of 8, got {blocked}"

asyncio.run(main())
print("FALLBACK-OK")
""",
    )
    r = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=BACKEND,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert r.returncode == 0, f"fallback failed:\n{r.stderr[-1500:]}"
    assert "FALLBACK-OK" in r.stdout
