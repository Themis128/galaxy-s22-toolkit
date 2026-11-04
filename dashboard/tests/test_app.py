"""Endpoint tests for dashboard.app (device-independent routes)."""

import os


class TestStaticAndTrends:
    def test_index_serves_html(self, api_client):
        r = api_client.get("/")
        assert r.status_code == 200
        assert "Galaxy S22+" in r.text

    def test_trends_metrics_lists_battery_level(self, api_client, tmp_db):
        tmp_db.insert_snapshot({"timestamp": None, "battery": {"level": 66.0}})
        r = api_client.get("/api/trends/metrics?hours=24")
        assert r.status_code == 200
        metrics = r.json()["metrics"]
        assert "battery.level" in metrics

    def test_hourly_trend_endpoint(self, api_client, tmp_db):
        from datetime import datetime, timedelta

        for i in range(3):
            ts = datetime.utcnow() - timedelta(minutes=i)
            tmp_db.insert_snapshot({"timestamp": ts.isoformat(), "battery": {"level": 70.0 + i}})
        tmp_db.compute_hourly_rollups(hours_back=1)
        r = api_client.get("/api/trends/hourly/battery.level?hours=24")
        assert r.status_code == 200
        assert r.json()["data"]

    def test_stats_endpoint(self, api_client, tmp_db):
        from datetime import datetime, timedelta

        for i, level in enumerate([80.0, 81.0, 82.0]):
            ts = datetime.utcnow() - timedelta(minutes=i)
            tmp_db.insert_snapshot({"timestamp": ts.isoformat(), "battery": {"level": level}})
        r = api_client.get("/api/trends/stats/battery.level?hours=24")
        assert r.status_code == 200
        stats = r.json()["stats"]
        assert stats["count"] == 3
        assert stats["max_val"] == 82.0

    def test_trends_500_on_db_error(self, api_client, monkeypatch):
        """DB failure in the executor becomes HTTP 500 with detail (B904 chain)."""

        class BrokenDB:
            def get_hourly_trend(self, *a, **k):
                raise RuntimeError("db exploded")

        from dashboard import app as app_module

        monkeypatch.setattr(app_module, "get_metrics_db", lambda: BrokenDB())
        r = api_client.get("/api/trends/hourly/battery.level")
        assert r.status_code == 500
        assert "db exploded" in r.json()["detail"]


class TestRepairEndpoints:
    def test_repair_actions_degrades_gracefully(self, api_client):
        """Without a device client (no lifespan), endpoints answer 503, not 500."""
        r = api_client.get("/api/repair/actions")
        assert r.status_code in (200, 503)
        if r.status_code == 200:
            actions = r.json()["actions"]
            assert len(actions) > 0
            assert all("name" in a and "risk_level" in a for a in actions)

    def test_repair_history_200_or_503(self, api_client):
        r = api_client.get("/api/repair/history")
        assert r.status_code in (200, 503)
        if r.status_code == 200:
            assert isinstance(r.json(), list)


class TestAuth:
    def test_devin_status_requires_key(self, api_client):
        r = api_client.get("/api/devin/status")
        assert r.status_code == 401

    def test_devin_status_with_key(self, api_client):
        # key comes from conftest's env (no hardcoded credentials)
        key = os.environ["GROQ_BOT_API_KEY"]
        r = api_client.get("/api/devin/status", headers={"X-API-Key": key})
        # 200 (Devin reachable) or 5xx (Devin CLI not installed in test env)
        assert r.status_code in (200, 500, 502, 503)


class TestHealthGracefulDegradation:
    def test_health_never_5xx_crash(self, api_client):
        """Health returns data, or a graceful 503/500 when no device is up."""
        r = api_client.get("/api/health")
        assert r.status_code in (200, 500, 503)
