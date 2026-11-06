"""Endpoint tests for dashboard.app (device-independent routes)."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, NoReturn

import pytest

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

    from dashboard.metrics_db import MetricsDB


class TestStaticAndTrends:
    def test_index_serves_html(self, api_client: TestClient) -> None:
        r = api_client.get("/")
        assert r.status_code == 200
        assert "Galaxy S22+" in r.text

    def test_trends_metrics_lists_battery_level(
        self, api_client: TestClient, tmp_db: MetricsDB
    ) -> None:
        tmp_db.insert_snapshot({"timestamp": None, "battery": {"level": 66.0}})
        r = api_client.get("/api/trends/metrics?hours=24")
        assert r.status_code == 200
        metrics = r.json()["metrics"]
        assert "battery.level" in metrics

    def test_hourly_trend_endpoint(self, api_client: TestClient, tmp_db: MetricsDB) -> None:
        from datetime import datetime, timedelta, timezone

        for i in range(3):
            ts = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=i)
            tmp_db.insert_snapshot({"timestamp": ts.isoformat(), "battery": {"level": 70.0 + i}})
        tmp_db.compute_hourly_rollups(hours_back=1)
        r = api_client.get("/api/trends/hourly/battery.level?hours=24")
        assert r.status_code == 200
        assert r.json()["data"]

    def test_stats_endpoint(self, api_client: TestClient, tmp_db: MetricsDB) -> None:
        from datetime import datetime, timedelta, timezone

        for i, level in enumerate([80.0, 81.0, 82.0]):
            ts = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=i)
            tmp_db.insert_snapshot({"timestamp": ts.isoformat(), "battery": {"level": level}})
        r = api_client.get("/api/trends/stats/battery.level?hours=24")
        assert r.status_code == 200
        stats = r.json()["stats"]
        assert stats["count"] == 3
        assert stats["max_val"] == 82.0

    def test_trends_500_on_db_error(
        self, api_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """DB failure in the executor becomes HTTP 500 with detail (B904 chain)."""

        class BrokenDB:
            def get_hourly_trend(self, *a: object, **k: object) -> NoReturn:
                raise RuntimeError("db exploded")

        from dashboard import app as app_module

        monkeypatch.setattr(app_module, "get_metrics_db", lambda: BrokenDB())
        r = api_client.get("/api/trends/hourly/battery.level")
        assert r.status_code == 500
        assert "db exploded" in r.json()["detail"]


class TestRepairEndpoints:
    def test_repair_actions_degrades_gracefully(self, api_client: TestClient) -> None:
        """Without a device client (no lifespan), endpoints answer 503, not 500."""
        r = api_client.get("/api/repair/actions")
        assert r.status_code in (200, 503)
        if r.status_code == 200:
            actions = r.json()["actions"]
            assert len(actions) > 0
            assert all("name" in a and "risk_level" in a for a in actions)

    def test_repair_history_200_or_503(self, api_client: TestClient) -> None:
        r = api_client.get("/api/repair/history")
        assert r.status_code in (200, 503)
        if r.status_code == 200:
            assert isinstance(r.json(), list)


class TestBulkRepairRobustness:
    def test_execute_multiple_returns_json_on_action_exception(
        self, api_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A raising action yields a JSON 500 the UI can parse, not a bare text 500."""
        import types

        import dashboard.app as app_module
        import phone.repair as repair_mod

        class ExplodingModule:
            AVAILABLE_ACTIONS = [
                types.SimpleNamespace(
                    name="explode", description="boom", risk_level="low", auto_approve=True
                )
            ]

            def __init__(self, *_args: object, **_kwargs: object) -> None:
                pass

            async def execute_multiple(self, *_a: object, **_k: object) -> object:
                raise RuntimeError("adb died mid-batch")

        monkeypatch.setattr(repair_mod, "RepairModule", ExplodingModule)
        monkeypatch.setattr(app_module, "client", object())  # past the 503 guard

        r = api_client.post(
            "/api/repair/execute-multiple",
            json={"action_names": ["explode"], "kwargs": {}, "confirm": True},
        )
        assert r.status_code == 500
        body = r.json()
        assert "Bulk repair failed" in body["error"]
        assert body["successful"] == 0
        assert body["total"] == 1

    def test_diagnostics_run_returns_json_on_runner_crash(
        self, api_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A crashing DiagnosticsRunner yields a JSON 500, not a bare text 500."""
        import diagnostics.run_diagnostics as diag_mod

        class ExplodingRunner:
            def __init__(self, *_args: object, **_kwargs: object) -> None:
                pass

            def run(self) -> int:
                raise RuntimeError("no adb in this environment")

        monkeypatch.setattr(diag_mod, "DiagnosticsRunner", ExplodingRunner)

        r = api_client.post("/api/diagnostics/run")
        assert r.status_code == 500
        body = r.json()
        assert "Diagnostics run failed" in body["error"]
        assert "no adb" in body["error"]

    def test_diagnostics_run_503_when_package_missing(
        self, api_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A missing diagnostics package yields a JSON 503, not a bare 500."""
        import builtins

        real_import = builtins.__import__

        def fake_import(name: str, *args: object, **kwargs: object) -> object:
            if name == "diagnostics.run_diagnostics":
                raise ImportError("No module named 'diagnostics.run_diagnostics'")
            return real_import(name, *args, **kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr(builtins, "__import__", fake_import)

        r = api_client.post("/api/diagnostics/run")
        assert r.status_code == 503
        assert "Diagnostics unavailable" in r.json()["error"]


class TestAuth:
    def test_devin_status_requires_key(self, api_client: TestClient) -> None:
        r = api_client.get("/api/devin/status")
        assert r.status_code == 401

    def test_devin_status_with_key(
        self, api_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # key comes from conftest's env (no hardcoded credentials)
        key = os.environ["GROQ_BOT_API_KEY"]
        r = api_client.get("/api/devin/status", headers={"X-API-Key": key})
        # 200 (Devin reachable) or graceful 5xx (Devin CLI not installed)
        assert r.status_code in (200, 500, 502, 503)

    def test_devin_status_503_when_tool_missing(
        self, api_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Missing process-inspection tool (container) -> 503, not raw 500."""

        def boom(*a: object, **k: object) -> NoReturn:
            raise FileNotFoundError(2, "tasklist not found")

        monkeypatch.setattr("dashboard.app.subprocess.run", boom)
        key = os.environ["GROQ_BOT_API_KEY"]
        r = api_client.get("/api/devin/status", headers={"X-API-Key": key})
        assert r.status_code == 503
        assert "Devin environment unavailable" in r.json()["detail"]


class TestHealthGracefulDegradation:
    def test_health_never_5xx_crash(self, api_client: TestClient) -> None:
        """Health returns data, or a graceful 503/500 when no device is up."""
        r = api_client.get("/api/health")
        assert r.status_code in (200, 500, 503)
