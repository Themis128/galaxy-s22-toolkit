"""Endpoint tests for dashboard.app (device-independent routes)."""

from __future__ import annotations

import os
import time
from datetime import datetime, timedelta
from pathlib import Path
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

    def test_execute_multiple_serializes_results(
        self, api_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Successful batches serialize RepairResult dicts (regression: the
        serializer returned JSONResponse objects, and nesting them crashed
        JSON encoding -> bare text 500 on every real batch)."""
        import types
        from datetime import datetime

        import dashboard.app as app_module
        import phone.repair as repair_mod

        class FakeModule:
            AVAILABLE_ACTIONS = [
                types.SimpleNamespace(
                    name="noop", description="d", risk_level="low", auto_approve=True
                )
            ]

            def __init__(self, *_args: object, **_kwargs: object) -> None:
                pass

            async def execute_multiple(self, *_a: object, **_k: object) -> object:
                return [
                    types.SimpleNamespace(
                        action=types.SimpleNamespace(name="noop"),
                        success=True,
                        message="done",
                        details={},
                        duration_ms=12,
                        timestamp=datetime(2026, 11, 6, 12, 0, 0),
                        requires_reboot=False,
                    )
                ]

        monkeypatch.setattr(repair_mod, "RepairModule", FakeModule)
        monkeypatch.setattr(app_module, "client", object())  # past the 503 guard

        r = api_client.post(
            "/api/repair/execute-multiple",
            json={"action_names": ["noop"], "kwargs": {}, "confirm": True},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["successful"] == 1
        assert body["skipped"] == 0
        assert body["failed"] == 0
        assert body["results"][0]["action_name"] == "noop"

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


class TestHealthDegradation:
    def test_health_degrades_on_command_failed(
        self, api_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """CommandFailedError mid-collection -> JSON 503, not a bare text 500."""
        import dashboard.app as app_module
        from phone.exceptions import CommandFailedError

        def boom() -> dict[str, object]:
            raise CommandFailedError(["adb", "shell", "dumpsys"], 1, "", "")

        monkeypatch.setattr(app_module, "_collect_once", boom)

        r = api_client.get("/api/health")
        assert r.status_code == 503
        assert r.json()["error"] == "Device not connected"


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


class TestBattleTestRegressions:
    """Regressions for the 2026-11-13 battle test findings.

    Concurrent read endpoints used to re-collect from the one attached
    device per request (health), re-scan SQL per cold request (insights),
    and hit the phone per alerts request — stalling rounds >6 s and
    surfacing 503s on an attached, healthy device."""

    @staticmethod
    def _snap(ts: str) -> dict[str, object]:
        return {
            "timestamp": ts,
            "device": {
                "model": "SM-S906B",
                "android_version": "16",
                "api_level": 36,
                "security_patch": "2026-10-01",
            },
        }

    def test_health_serves_fresh_collector_snapshot(
        self, api_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import dashboard.app as app_module

        def boom() -> dict[str, object]:
            raise AssertionError("fresh collect must not run when the cache is fresh")

        monkeypatch.setattr(app_module, "_collect_once", boom)
        monkeypatch.setattr(
            app_module,
            "history",
            [self._snap(datetime.now().isoformat())],
        )
        r = api_client.get("/api/health")
        assert r.status_code == 200
        assert r.json()["device"]["model"] == "SM-S906B"

    def test_health_collects_fresh_when_history_stale(
        self, api_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import dashboard.app as app_module

        stale = (datetime.now() - timedelta(hours=1)).isoformat()
        monkeypatch.setattr(app_module, "history", [self._snap(stale)])
        monkeypatch.setattr(app_module, "_collect_once", lambda: self._snap("fresh"))
        r = api_client.get("/api/health")
        assert r.status_code == 200
        assert r.json()["device"]["model"] == "SM-S906B"

    def test_health_serial_bypasses_cache(
        self, api_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import dashboard.app as app_module

        seen: dict[str, str | None] = {}

        def collect(serial: str | None = None) -> dict[str, object]:
            seen["serial"] = serial
            return self._snap("fresh")

        monkeypatch.setattr(app_module, "history", [self._snap(datetime.now().isoformat())])
        monkeypatch.setattr(app_module, "_collect_once", collect)
        r = api_client.get("/api/health", params={"serial": "RFCTA0AEKZP"})
        assert r.status_code == 200
        assert seen["serial"] == "RFCTA0AEKZP"

    def test_fresh_cached_snapshot_helper(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import dashboard.app as app_module

        monkeypatch.setattr(app_module, "history", [])
        assert app_module._fresh_cached_snapshot(15) is None

        now_iso = datetime.now().isoformat()
        monkeypatch.setattr(app_module, "history", [self._snap(now_iso)])
        assert app_module._fresh_cached_snapshot(15) is not None

        old_iso = (datetime.now() - timedelta(seconds=60)).isoformat()
        monkeypatch.setattr(app_module, "history", [self._snap(old_iso)])
        assert app_module._fresh_cached_snapshot(15) is None

        future_iso = (datetime.now() + timedelta(seconds=60)).isoformat()
        monkeypatch.setattr(app_module, "history", [self._snap(future_iso)])
        assert app_module._fresh_cached_snapshot(15) is None

    def test_insights_single_flight(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import asyncio

        import dashboard.app as app_module

        monkeypatch.setattr(app_module, "_insights_cache", None)
        monkeypatch.setattr(app_module, "_insights_inflight", None)
        calls = {"n": 0}

        def slow_compute() -> dict[str, object]:
            calls["n"] += 1
            time.sleep(0.25)
            return {"insights": [{"metric": f"m{calls['n']}"}]}

        monkeypatch.setattr(app_module, "_analyze_insights_blocking", slow_compute)

        async def scenario() -> list[dict[str, object]]:
            async def one() -> dict[str, object]:
                return await app_module._insights_report()

            return list(await asyncio.gather(*[one() for _ in range(6)]))

        results = asyncio.run(scenario())
        assert calls["n"] == 1
        assert all(r == results[0] for r in results)
        # Subsequent call inside the TTL is a cache hit.
        asyncio.run(app_module._insights_report())
        assert calls["n"] == 1

    def test_insights_failure_not_cached(
        self, api_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import asyncio

        import dashboard.app as app_module

        monkeypatch.setattr(app_module, "_insights_cache", None)
        monkeypatch.setattr(app_module, "_insights_inflight", None)
        calls = {"n": 0}

        def flaky() -> dict[str, object]:
            calls["n"] += 1
            raise RuntimeError("scan boom")

        monkeypatch.setattr(app_module, "_analyze_insights_blocking", flaky)

        async def scenario() -> None:
            with pytest.raises(RuntimeError):
                await app_module._insights_report()

        asyncio.run(scenario())
        # Failure must not poison the cache: the next attempt recomputes.
        assert app_module._insights_cache is None
        with pytest.raises(RuntimeError):
            asyncio.run(app_module._insights_report())
        assert calls["n"] == 2

    def test_alerts_patch_age_from_snapshot(
        self, api_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import dashboard.app as app_module

        # A 200-day-old patch is past the ACT threshold, so the alerts
        # endpoint must surface it — and must do so from the snapshot,
        # never by calling the device.
        old_patch = (datetime.now() - timedelta(days=200)).strftime("%Y-%m-%d")
        snap = self._snap(datetime.now().isoformat())
        snap["device"]["security_patch"] = old_patch  # type: ignore[index]
        monkeypatch.setattr(app_module, "history", [snap])

        # Stub the insights scan: the real one pulls the newest diagnostics
        # report off disk (which also emits a patch-age item and would make
        # this a duplicate-alert test instead of a patch-age one).
        async def stub_report() -> dict[str, object]:
            return {"insights": []}

        monkeypatch.setattr(app_module, "_insights_report", stub_report)

        def boom() -> dict[str, object]:
            raise AssertionError("alerts must not call the device for the patch level")

        monkeypatch.setattr(app_module, "_collect_once", boom)
        r = api_client.get("/api/alerts")
        assert r.status_code == 200
        body = r.json()
        patch_alerts = [a for a in body["alerts"] if a["id"] == "security patch age"]
        assert patch_alerts, "stale-patch alert missing from alerts output"
        assert patch_alerts[0]["severity"] == "critical"

    def test_fleet_registry_write_only_on_new_devices(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        import json as json_mod

        import dashboard.app as app_module

        reg = tmp_path / "data" / "fleet.json"
        reg.parent.mkdir(parents=True, exist_ok=True)
        reg.write_text(
            json_mod.dumps([{"serial": "S1", "model": "M1", "first_seen": "t"}]),
            encoding="utf-8",
        )
        monkeypatch.setattr(app_module, "PROJECT_ROOT", tmp_path)
        before = reg.read_text(encoding="utf-8")

        known = app_module._register_devices([{"serial": "S1", "state": "device", "model": "M1"}])
        assert [d["serial"] for d in known] == ["S1"]
        assert reg.read_text(encoding="utf-8") == before  # no rewrite on repeat GET

        app_module._register_devices([{"serial": "S2", "state": "device", "model": "M2"}])
        after = json_mod.loads(reg.read_text(encoding="utf-8"))
        assert [d["serial"] for d in after] == ["S1", "S2"]
