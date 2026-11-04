"""Shared fixtures for dashboard tests.

Importing dashboard.app is safe without a device: the phone client is
created in the FastAPI lifespan, which TestClient does not trigger.
"""

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (
    str(REPO_ROOT),
    str(REPO_ROOT / "phone-lib" / "src"),
    str(REPO_ROOT / "dashboard"),
):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Auth key must exist before dashboard.app is imported.
os.environ.setdefault("GROQ_BOT_API_KEY", "test-key-12345")

import pytest  # noqa: E402

from dashboard import metrics_db as metrics_db_mod  # noqa: E402


@pytest.fixture()
def tmp_db(tmp_path):
    """Fresh MetricsDB in a temp directory."""
    db = metrics_db_mod.MetricsDB(db_path=tmp_path / "metrics.db")
    yield db
    db.close()


@pytest.fixture()
def api_client(tmp_db, monkeypatch):
    """TestClient with get_metrics_db patched to the temp database."""
    from dashboard import app as app_module

    monkeypatch.setattr(app_module, "get_metrics_db", lambda: tmp_db)

    from fastapi.testclient import TestClient

    return TestClient(app_module.app)
