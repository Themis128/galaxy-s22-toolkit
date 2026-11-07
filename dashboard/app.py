#!/usr/bin/env python3
"""Galaxy Monitoring Dashboard with Devin control API for Groq bot."""

from __future__ import annotations

import asyncio
import logging
import os
import re
import subprocess
import sys
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from phone import create_client

PROJECT_ROOT = Path(__file__).resolve().parents[1]
# Repo root must be importable for `from dashboard.metrics_db import ...`
# when launched as `python dashboard/app.py` (sys.path[0] is dashboard/).
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "phone-lib" / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "diagnostics"))

from fastapi import (  # noqa: E402
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import HTMLResponse, JSONResponse  # noqa: E402
from fastapi.security import APIKeyHeader  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from fastapi.templating import Jinja2Templates  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from dashboard.metrics_db import get_metrics_db, init_metrics_db  # noqa: E402

if TYPE_CHECKING:
    from phone import create_client
    from phone.capabilities import detect_profile
    from phone.exceptions import PhoneError
else:
    from phone import create_client  # type: ignore[import-untyped]
    from phone.capabilities import detect_profile  # type: ignore[import-untyped]
    from phone.exceptions import PhoneError  # type: ignore[import-untyped]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

COLLECT_INTERVAL_S = 5
MAX_HISTORY = 17_280  # 24 h at 5 s cadence (in-memory ring buffer for WS live)
MAX_DB_SNAPSHOTS = 172_800  # ~10 days at 5 s cadence (persisted to SQLite)

STATIC_DIR = Path(__file__).resolve().parent / "static"
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

# API Key authentication for Groq bot via Tailscale
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

# Load API key and Tailscale allowlist from environment
GROQ_BOT_API_KEY = os.getenv("GROQ_BOT_API_KEY", "dev-key-change-in-production")
TAILSCALE_ALLOWLIST = os.getenv("TAILSCALE_ALLOWLIST", "").split(",")  # Comma-separated IPs
TAILSCALE_ALLOWLIST = [ip.strip() for ip in TAILSCALE_ALLOWLIST if ip.strip()]

# Devin working directory (can be overridden via env)
DEVIN_WORKDIR = Path(os.getenv("DEVIN_WORKDIR", str(Path.home() / "Devin")))

manager: ConnectionManager | None = None
client: Any = None  # PhoneClient type but no stubs
history: list[dict[str, Any]] = []


async def verify_api_key(
    api_key: str = Depends(api_key_header),
    x_forwarded_for: str | None = Header(None),
    request: Request = None,  # type: ignore[assignment]
) -> str:
    """Verify API key and optionally Tailscale IP allowlist."""
    if api_key != GROQ_BOT_API_KEY:
        client_host = request.client.host if request and request.client else "unknown"
        logger.warning("Invalid API key attempt from %s", client_host)
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Check Tailscale allowlist if configured
    if TAILSCALE_ALLOWLIST:
        client_ip = request.client.host if request and request.client else ""
        # Also check X-Forwarded-For for reverse proxy scenarios
        if x_forwarded_for:
            client_ip = x_forwarded_for.split(",")[0].strip()

        if client_ip not in TAILSCALE_ALLOWLIST:
            logger.warning("IP %s not in Tailscale allowlist", client_ip)
            raise HTTPException(status_code=403, detail="IP not authorized")

    return api_key


class CommandRequest(BaseModel):
    """Request model for Devin command execution."""

    command: str
    workdir: str | None = None
    timeout: int = 300


class FileRequest(BaseModel):
    """Request model for file operations."""

    path: str
    content: str | None = None


class ConnectionManager:
    """Tracks WebSocket clients and broadcasts snapshots."""

    def __init__(self) -> None:
        self.active: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active.append(websocket)
        logger.info("Client connected (total %d)", len(self.active))

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active:
            self.active.remove(websocket)
        logger.info("Client disconnected (total %d)", len(self.active))

    async def broadcast(self, message: dict[str, Any]) -> None:
        dead = []
        for ws in self.active:
            try:
                await ws.send_json(message)
            except Exception:  # noqa: BLE001 - any send failure drops the client
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


def _device_wireless_settings() -> dict[str, Any] | None:
    """device.wireless_adb from diagnostics/config.yaml (host-side fallback).

    PHONE_ADB_HOST (set by docker-compose) overrides the config's tailnet
    host: inside the container only the phone's LAN IP is reachable, so the
    auto-reconnect must dial the same address the startup `adb connect`
    used — otherwise a dropped transport can never self-heal.
    """
    try:
        import yaml

        with open(PROJECT_ROOT / "diagnostics" / "config.yaml", encoding="utf-8") as f:
            device_cfg = (yaml.safe_load(f) or {}).get("device", {})
        wireless = device_cfg.get("wireless_adb") or None
        if wireless:
            wireless = {**wireless, "preferred_serial": device_cfg.get("serial")}
        env_host = os.getenv("PHONE_ADB_HOST")
        if env_host and wireless:
            wireless["host"] = env_host
        return wireless
    except Exception:
        return None


def _ensure_client() -> Any:
    """Return a live phone client, reconnecting when the transport dropped.

    Wireless ADB transports die silently (phone TCP listener reset, network
    blips). The old code connected once at startup and never retried - the
    alert board then silently went blind. create_client's auto-connect +
    preferred_serial resolution does the recovery for us.
    """
    global client
    if client is not None and client.is_connected:
        return client
    client = create_client(
        os.getenv("PHONE_ADB_SERIAL") or None,
        wireless=_device_wireless_settings(),
    )
    if not client.is_connected:
        raise ConnectionError("No ADB device connected")
    return client


def _collect_once() -> dict[str, Any]:
    """One blocking collection pass (runs in a worker thread)."""
    global client
    client = _ensure_client()

    device = client.device.get_device_info()
    battery = client.battery.get_battery_info()
    partitions = client.storage.get_storage_info()
    network = client.network.get_network_info()
    thermal = client.thermal.get_thermal_info()
    cpu_raw = client.device.get_cpu_info()
    mem = client.device.get_memory_info()
    running = client.apps.get_running_apps()
    # Full root/Magisk state for the root card (cheap when unrooted: one
    # `which su` + Knox getprops per tick).
    root_info = client.root.get_root_info()

    # Detect device profile for multi-Galaxy compatibility
    device_profile = detect_profile(client.device)

    per_core_mhz = [c.get("cpu MHz", 0) for c in cpu_raw.get("details", []) if isinstance(c, dict)]
    if not any(per_core_mhz):
        # /proc/cpuinfo lacks freq on modern Android; read cpufreq sysfs instead
        try:
            freq_out = client.execute(
                "shell",
                "for f in /sys/devices/system/cpu/cpu[0-9]*/cpufreq/scaling_cur_freq; "
                "do echo $f=$(cat $f 2>/dev/null); done",
            )
            per_core_mhz = []
            for line in freq_out.strip().split("\n"):
                if "=" in line:
                    val = line.rsplit("=", 1)[1]
                    per_core_mhz.append(int(val) // 1000 if val.isdigit() else 0)
        except Exception:  # noqa: BLE001 - freqs are best-effort
            per_core_mhz = []
    mem_total_kb = int(mem.get("MemTotal", 0))
    mem_avail_kb = int(mem.get("MemAvailable", mem.get("MemFree", 0)))

    snapshot = {
        "timestamp": datetime.now().isoformat(),
        "device": {
            "model": device.model,
            "android_version": device.android_version,
            "api_level": device.api_level,
            "security_patch": device.security_patch,
        },
        "device_profile": {
            "model": device_profile.model,
            "marketing_name": device_profile.marketing_name,
            "series": device_profile.series,
            "year_class": device_profile.year_class,
            "chipset": device_profile.chipset,
            "api_level": device_profile.api_level,
            "one_ui": device_profile.one_ui,
            "is_samsung": device_profile.is_samsung,
            "flags": list(device_profile.flags),
        },
        "battery": {
            "level": battery.level,
            "health": battery.health.value,
            "status": battery.status.value,
            "temperature_c": round(battery.temperature_c, 1),
            "temperature_f": round(battery.temperature_f, 1),
            "voltage_mv": battery.voltage_mv,
            "technology": battery.technology,
            "plugged_type": battery.plugged_type,
            "current_capacity_mah": battery.current_capacity_mah,
            "charge_cycles": battery.charge_cycles,
            "current_ma": battery.current_ma,
            "charge_counter_uah": battery.charge_counter_uah,
        },
        "storage": [
            {
                "mount_point": p.mount_point,
                "total_gb": round(
                    p.total_gb,
                ),
                "used_gb": round(p.used_gb, 2),
                "free_gb": round(p.free_gb, 2),
                "usage_percent": round(p.usage_percent, 1),
                "filesystem": p.filesystem,
            }
            for p in partitions
        ],
        "network": {
            "wifi_connected": network.wifi_connected,
            "wifi_ssid": network.wifi_ssid,
            "wifi_signal_dbm": network.wifi_signal_dbm,
            "wifi_ip": network.wifi_ip,
            "mobile_connected": network.mobile_connected,
            "mobile_type": network.mobile_type,
            "mobile_ip": network.mobile_ip,
            "dns_servers": network.dns_servers,
            "gateway": network.gateway,
            "internet_reachable": network.internet_reachable,
        },
        "thermal": {
            "status": thermal.status.value,
            "cpu_throttled": thermal.cpu_throttled,
            "gpu_throttled": thermal.gpu_throttled,
            "zones": [
                {"name": z.name, "temp_c": round(z.temp_c, 1), "type": z.type}
                for z in thermal.zones
            ],
        },
        "cpu": {
            "count": cpu_raw.get("count", 0),
            "per_core_mhz": per_core_mhz,
        },
        "memory": {
            "total_mb": round(mem_total_kb / 1024, 1),
            "available_mb": round(mem_avail_kb / 1024, 1),
            "usage_percent": round((mem_total_kb - mem_avail_kb) / mem_total_kb * 100, 1)
            if mem_total_kb
            else 0.0,
        },
        "apps": {"running_count": len(running), "running": running[:10]},
        "root": {
            "rooted": root_info.rooted,
            "su_path": root_info.su_path,
            "magisk_version": root_info.magisk_version,
            "denylist_enabled": root_info.denylist_enabled,
            "modules_dir_present": root_info.modules_dir_present,
            "knox_status": root_info.knox_status,
        },
    }
    return snapshot


async def collector_loop() -> None:
    """Periodically collect a snapshot, store it, and broadcast to WS clients."""
    global history
    db = get_metrics_db()
    tick = 0
    while True:
        try:
            loop = asyncio.get_running_loop()
            metrics = await loop.run_in_executor(None, _collect_once)
            history.append(metrics)
            if len(history) > MAX_HISTORY:
                del history[: len(history) - MAX_HISTORY]
            if manager is not None:
                await manager.broadcast({"type": "metrics", "data": metrics})
            # Persist to SQLite (non-blocking in executor)
            await loop.run_in_executor(None, db.insert_snapshot, metrics)
            # Refresh hourly/daily rollups every ~60 s so the trend charts
            # have data right after a restart (the upserts are idempotent;
            # daily depends on hourly, so keep the order).
            tick += 1
            if tick % 12 == 0:
                await loop.run_in_executor(None, db.compute_hourly_rollups, 2)
                await loop.run_in_executor(None, db.compute_daily_rollups, 2)
        except ConnectionError:
            # Device unplugged: keep the loop alive, retry after the interval.
            logger.warning("Device not connected; retrying in %ss", COLLECT_INTERVAL_S)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - collector must never die
            logger.error("Collector error: %s", exc)
            # Drop the cached client so the next tick reconnects (e.g. the
            # device appeared after startup, as with `adb connect` later on)
            global client
            client = None
        await asyncio.sleep(COLLECT_INTERVAL_S)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Start/stop the background collector around the app lifetime."""
    global manager
    # Initialize metrics database and WebSocket manager
    init_metrics_db(max_snapshots=MAX_DB_SNAPSHOTS)
    manager = ConnectionManager()
    task = asyncio.create_task(collector_loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    manager = None


app = FastAPI(
    title="Galaxy Toolkit",
    description="Real-time device monitoring via ADB (Samsung Galaxy S/Note/A)",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware to allow ZCode integrated browser and other origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request) -> HTMLResponse:
    """Main dashboard page."""
    return templates.TemplateResponse(request, "dashboard.html")


@app.get("/api/health")
async def api_health() -> JSONResponse:
    """Current snapshot (triggers a fresh collection)."""
    loop = asyncio.get_running_loop()
    try:
        metrics = await loop.run_in_executor(None, _collect_once)
    except (ConnectionError, OSError, PhoneError):
        # OSError covers FileNotFoundError when the adb binary itself is
        # missing (bare CI runners); PhoneError covers CommandFailedError
        # when the transport dies mid-collection — both degrade to
        # "device unreachable" instead of a bare text 500 the UI cannot
        # parse.
        return JSONResponse({"error": "Device not connected"}, status_code=503)
    except RuntimeError as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)
    return JSONResponse(metrics)


@app.get("/api/history")
async def api_history(hours: int = 24) -> JSONResponse:
    """Time-series of stored snapshots."""
    cutoff = datetime.now() - timedelta(hours=hours)
    out = []
    for m in history:
        try:
            if datetime.fromisoformat(m["timestamp"]) > cutoff:
                out.append(m)
        except (KeyError, ValueError):
            continue
    return JSONResponse(out)


@app.get("/api/history/{metric}")
async def api_history_metric(metric: str, hours: int = 24) -> JSONResponse:
    """Time-series of one metric section."""
    cutoff = datetime.now() - timedelta(hours=hours)
    out = []
    for m in history:
        try:
            if datetime.fromisoformat(m["timestamp"]) > cutoff and metric in m:
                out.append({"timestamp": m["timestamp"], metric: m[metric]})
        except (KeyError, ValueError):
            continue
    return JSONResponse(out)


# ===== Historical Trends API (persisted SQLite) =====


@app.get("/api/trends/metrics")
async def api_trends_metrics(hours: int = 24) -> JSONResponse:
    """List metric paths that have persisted data in the window."""
    db = get_metrics_db()
    try:
        metrics = await asyncio.get_running_loop().run_in_executor(
            None, db.list_available_metrics, hours
        )
    except Exception as exc:
        logger.error("Failed to list metrics: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return JSONResponse({"metrics": metrics, "count": len(metrics)})


@app.get("/api/trends/hourly/{metric_path:path}")
async def api_trends_hourly(metric_path: str, hours: int = 24) -> JSONResponse:
    """Hourly averaged trend for a metric (dot-notation path, e.g. battery.level)."""
    db = get_metrics_db()
    try:
        data = await asyncio.get_running_loop().run_in_executor(
            None, db.get_hourly_trend, metric_path, hours
        )
    except Exception as exc:
        logger.error("Failed to get hourly trend: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return JSONResponse({"metric": metric_path, "hours": hours, "data": data})


@app.get("/api/trends/daily/{metric_path:path}")
async def api_trends_daily(metric_path: str, days: int = 30) -> JSONResponse:
    """Daily averaged trend for a metric."""
    db = get_metrics_db()
    try:
        data = await asyncio.get_running_loop().run_in_executor(
            None, db.get_daily_trend, metric_path, days
        )
    except Exception as exc:
        logger.error("Failed to get daily trend: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return JSONResponse({"metric": metric_path, "days": days, "data": data})


@app.get("/api/trends/stats/{metric_path:path}")
async def api_trends_stats(metric_path: str, hours: int = 24) -> JSONResponse:
    """Min/max/avg/count stats for a metric over the window."""
    db = get_metrics_db()
    try:
        stats = await asyncio.get_running_loop().run_in_executor(
            None, db.get_metric_stats, metric_path, hours
        )
    except Exception as exc:
        logger.error("Failed to get metric stats: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return JSONResponse({"metric": metric_path, "hours": hours, "stats": stats})


@app.post("/api/trends/rollup")
async def api_trends_rollup(hours_back: int = 2, days_back: int = 2) -> JSONResponse:
    """Manually trigger hourly/daily rollup computation."""
    db = get_metrics_db()
    try:
        hourly = await asyncio.get_running_loop().run_in_executor(
            None, db.compute_hourly_rollups, hours_back
        )
        daily = await asyncio.get_running_loop().run_in_executor(
            None, db.compute_daily_rollups, days_back
        )
    except Exception as exc:
        logger.error("Rollup computation failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return JSONResponse({"hourly_inserted": hourly, "daily_inserted": daily})


@app.get("/alerts", response_class=HTMLResponse)
async def alerts_page(request: Request) -> HTMLResponse:
    """Human-readable alert board (severity-sorted, auto-refresh)."""
    alerts_mod = _load_tool("alerts")
    loop = asyncio.get_running_loop()
    # Shallow-copies the list so the patch-age append never mutates the cache.
    insights = list((await _insights_report())["insights"])
    # Patch age comes straight from the connected phone here (the
    # container has no diagnostics reports to read).
    try:
        from datetime import date

        patch = await loop.run_in_executor(
            None, lambda: _ensure_client().device.get_security_patch()
        )
        patch_days = (date.today() - datetime.strptime(patch[:10], "%Y-%m-%d").date()).days
        insights.append(
            {
                "metric": "security patch age",
                "value": patch_days,
                "unit": f"days (patch {patch[:10]})",
                "verdict": ("OK" if patch_days < 90 else "WATCH" if patch_days <= 180 else "ACT"),
            }
        )
    except Exception as exc:
        logger.warning("alerts: patch age unavailable: %s", exc)
    alerts = alerts_mod.evaluate(insights)
    return templates.TemplateResponse(request, "alerts.html", {"alerts": alerts})


def _load_tool(name: str) -> Any:
    import importlib.util

    spec = importlib.util.spec_from_file_location(name, PROJECT_ROOT / "tools" / f"{name}.py")
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module {name}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_insights_cache: tuple[float, dict[str, Any]] | None = None
INSIGHTS_TTL_S = 60


def _load_insights_module() -> Any:
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "insights", PROJECT_ROOT / "tools" / "insights.py"
    )
    if spec is None or spec.loader is None:
        raise ImportError("Could not load insights module")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _analyze_insights_blocking() -> dict[str, Any]:
    """Full SQL scan of the raw snapshots — heavy; runs in the executor."""
    import sqlite3

    mod = _load_insights_module()
    db = get_metrics_db()
    conn = sqlite3.connect(f"file:{db.db_path}?mode=ro", uri=True)
    try:
        return cast(dict[str, Any], mod.analyze(conn))
    finally:
        conn.close()


async def _insights_report() -> dict[str, Any]:
    """Insights with a 60 s TTL cache; the analysis runs in the executor so
    the event loop never blocks (a 7-day scan takes tens of seconds and
    previously stalled every other request)."""
    global _insights_cache
    loop = asyncio.get_running_loop()
    now = time.monotonic()
    if _insights_cache is not None and now - _insights_cache[0] < INSIGHTS_TTL_S:
        return _insights_cache[1]
    report = await loop.run_in_executor(None, _analyze_insights_blocking)
    _insights_cache = (now, report)
    return report


@app.get("/api/alerts")
async def api_alerts() -> JSONResponse:
    """Active alerts from the current metrics history (stateless)."""
    insights_mod = _load_tool("insights")
    alerts_mod = _load_tool("alerts")
    loop = asyncio.get_running_loop()
    # Shallow-copies the list so the patch-age append never mutates the cache.
    insights = list((await _insights_report())["insights"])
    # Patch age comes straight from the connected phone here (the
    # container has no diagnostics reports to read).
    try:
        from datetime import date

        patch = await loop.run_in_executor(
            None, lambda: _ensure_client().device.get_security_patch()
        )
        patch_days = (date.today() - datetime.strptime(patch[:10], "%Y-%m-%d").date()).days
        insights.append(
            {
                "metric": "security patch age",
                "value": patch_days,
                "unit": f"days (patch {patch[:10]})",
                "verdict": ("OK" if patch_days < 90 else "WATCH" if patch_days <= 180 else "ACT"),
            }
        )
    except Exception as exc:
        logger.warning("alerts: patch age unavailable: %s", exc)
    return JSONResponse(
        {
            "alerts": alerts_mod.evaluate(insights),
            "generated": insights_mod.datetime.now(insights_mod.timezone.utc)
            .replace(tzinfo=None)
            .isoformat()
            + "Z",
        }
    )


@app.get("/api/insights")
async def api_insights() -> JSONResponse:
    """Degradation insights computed from the raw history (60 s cache)."""
    return JSONResponse(await _insights_report())


@app.websocket("/ws/live")
async def ws_live(websocket: WebSocket) -> None:
    """Live updates: initial snapshot, then collector broadcasts."""
    if manager is None:
        await websocket.accept()
        await websocket.send_json({"type": "error", "data": "service not ready"})
        await websocket.close(code=1011)
        return
    await manager.connect(websocket)
    try:
        loop = asyncio.get_running_loop()
        try:
            initial = await loop.run_in_executor(None, _collect_once)
            await websocket.send_json({"type": "initial", "data": initial})
        except (ConnectionError, RuntimeError, PhoneError):
            await websocket.send_json({"type": "error", "data": "device not available"})
        while True:
            await websocket.receive_text()  # keepalive pings from the client
    except WebSocketDisconnect:
        if manager is not None:
            manager.disconnect(websocket)
    except Exception as exc:  # noqa: BLE001 - never crash the WS handler
        logger.error("WebSocket error: %s", exc)
        if manager is not None:
            manager.disconnect(websocket)


@app.post("/api/diagnostics/run")
async def api_diagnostics_run() -> JSONResponse:
    """Trigger a full diagnostics run via DiagnosticsRunner."""
    try:
        from diagnostics.run_diagnostics import DiagnosticsRunner
    except ImportError as exc:
        # Image without the diagnostics package (or broken install)
        return JSONResponse({"error": f"Diagnostics unavailable: {exc}"}, status_code=503)
    config_path = PROJECT_ROOT / "diagnostics" / "config.yaml"
    try:
        runner = DiagnosticsRunner(config_path)
        loop = asyncio.get_running_loop()
        exit_code = await loop.run_in_executor(None, runner.run)
    except Exception as exc:  # noqa: BLE001 - a crashing run must not yield a bare 500
        logger.error("Diagnostics run failed: %s", exc)
        return JSONResponse({"error": f"Diagnostics run failed: {exc}"}, status_code=500)
    status = {0: "completed", 1: "issues_found", 2: "critical"}.get(exit_code, "error")
    # Summarize the freshly written report so the UI can show WHY it exited
    # non-zero instead of a bare exit code.
    checks = _latest_diagnostics_results() or []
    non_pass = [
        {
            "name": c.get("name"),
            "status": str(c.get("status", "")),
            "message": str(c.get("message", ""))[:160],
        }
        for c in checks
        if str(c.get("status", "")).lower() not in ("pass", "ok")
    ][:5]
    passed = sum(1 for c in checks if str(c.get("status", "")).lower() in ("pass", "ok"))
    return JSONResponse(
        {
            "exit_code": exit_code,
            "status": status,
            "checks_total": len(checks),
            "checks_passed": passed,
            "non_passing": non_pass,
        }
    )


# ===== Repair API (for auto-repair with user approval) =====


class RepairActionRequest(BaseModel):
    """Request model for repair action execution."""

    action_name: str
    kwargs: dict[str, Any] = {}
    # Non-auto-approve actions require explicit confirmation from the UI
    confirm: bool = False


class RepairMultipleRequest(BaseModel):
    """Request model for multiple repair actions."""

    action_names: list[str]
    kwargs: dict[str, Any] = {}
    confirm: bool = False


class RepairApprovalRequest(BaseModel):
    """Request model for repair approval."""

    action_name: str
    approved: bool


@app.get("/api/repair/actions")
async def api_repair_actions() -> JSONResponse:
    """Get available repair actions, optionally filtered by diagnostics results."""
    from phone.repair import RepairModule

    if client is None:
        return JSONResponse({"error": "Device not connected"}, status_code=503)

    repair_module = RepairModule(client)

    # Use the most recent saved diagnostics report instead of re-running
    # diagnostics on every request (a full run takes ~13s)
    diagnostics_results = _latest_diagnostics_results()

    actions = await repair_module.get_pending_actions(diagnostics_results)

    return JSONResponse(
        {
            "actions": [
                {
                    "name": a.name,
                    "description": a.description,
                    "category": a.category,
                    "risk_level": a.risk_level,
                    "requires_root": a.requires_root,
                    "estimated_duration_s": a.estimated_duration_s,
                    "auto_approve": a.auto_approve,
                }
                for a in actions
            ],
            "total": len(actions),
        }
    )


def _latest_diagnostics_results() -> list[dict[str, Any]] | None:
    """Load check results from the newest saved health report (or None)."""
    reports_dir = PROJECT_ROOT / "diagnostics" / "reports"
    try:
        report_files = sorted(reports_dir.glob("health_report_*.json"))
        if not report_files:
            return None
        import json

        with open(report_files[-1], encoding="utf-8") as f:
            report = json.load(f)
        return report.get("check_results") or report.get("results") or report.get("checks") or None
    except Exception as exc:
        logger.warning("Could not load latest diagnostics report: %s", exc)
        return None


@app.post("/api/repair/execute")
async def api_repair_execute(request: RepairActionRequest) -> JSONResponse:
    """Execute a single repair action."""
    from phone.repair import RepairModule

    if client is None:
        return JSONResponse({"error": "Device not connected"}, status_code=503)

    repair_module = RepairModule(client, history_path=_repair_history_path())

    # Server-side approval gate: non-auto-approve actions need confirm=True
    action = next(
        (a for a in RepairModule.AVAILABLE_ACTIONS if a.name == request.action_name),
        None,
    )
    if action is None:
        return JSONResponse({"error": f"Unknown action: {request.action_name}"}, status_code=400)
    if not action.auto_approve and not request.confirm:
        return JSONResponse(
            {
                "status": "confirmation_required",
                "action_name": action.name,
                "description": action.description,
                "risk_level": action.risk_level,
                "message": "This action requires explicit confirmation (set confirm=true).",
            },
            status_code=202,
        )

    result = await repair_module.execute_action(request.action_name, **request.kwargs)
    _notify_repair_toast(result)
    return JSONResponse(_repair_result_json(result))


def _repair_result_json(result: Any) -> dict[str, Any]:
    """Serialize a RepairResult as a plain dict (nestable in JSON payloads)."""
    return {
        "action_name": result.action.name,
        "success": result.success,
        "message": result.message,
        "details": result.details,
        "duration_ms": result.duration_ms,
        "timestamp": result.timestamp.isoformat(),
        "requires_reboot": result.requires_reboot,
    }


def _repair_history_path() -> str | None:
    """Repair history file path from diagnostics/config.yaml (repair section)."""
    try:
        import yaml

        with open(PROJECT_ROOT / "diagnostics" / "config.yaml", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        rel = (cfg.get("repair") or {}).get("history_file")
        return str(PROJECT_ROOT / rel) if rel else None
    except Exception:
        return None


def _notify_repair_toast(result: Any) -> None:
    """Fire a desktop toast for a completed repair (best-effort, non-blocking)."""
    try:
        from phone.notify import DesktopNotifier

        notifier = DesktopNotifier(app_id="Galaxy Toolkit")
        emoji = "succeeded" if result.success else "failed"
        notifier.notify(
            f"Repair {emoji}: {result.action.name}",
            result.message,
            long=not result.success,
        )
    except Exception as exc:
        logger.debug("Repair toast not shown: %s", exc)


@app.post("/api/repair/execute-multiple")
async def api_repair_execute_multiple(request: RepairMultipleRequest) -> JSONResponse:
    """Execute multiple repair actions sequentially."""
    from phone.repair import RepairModule

    if client is None:
        return JSONResponse({"error": "Device not connected"}, status_code=503)

    repair_module = RepairModule(client, history_path=_repair_history_path())

    # Enforce confirmation for any requested non-auto-approve action
    gated = [
        a
        for a in RepairModule.AVAILABLE_ACTIONS
        if a.name in request.action_names and not a.auto_approve
    ]
    if gated and not request.confirm:
        return JSONResponse(
            {
                "status": "confirmation_required",
                "actions": [{"action_name": a.name, "risk_level": a.risk_level} for a in gated],
                "message": "Some actions require explicit confirmation (set confirm=true).",
            },
            status_code=202,
        )

    results = []
    try:
        results = await repair_module.execute_multiple(request.action_names, **request.kwargs)
    except Exception as exc:  # noqa: BLE001 - a raising action must not yield a bare 500
        logger.error("Bulk repair failed: %s", exc)
        return JSONResponse(
            {
                "error": f"Bulk repair failed: {exc}",
                "successful": 0,
                "total": len(request.action_names),
                "results": [],
            },
            status_code=500,
        )
    for r in results:
        _notify_repair_toast(r)
    succeeded = sum(1 for r in results if r.success)
    skipped = sum(1 for r in results if not r.success and (r.message or "").startswith("Skipped:"))
    return JSONResponse(
        {
            "results": [_repair_result_json(r) for r in results],
            "total": len(results),
            "successful": succeeded,
            "skipped": skipped,
            "failed": len(results) - succeeded - skipped,
        }
    )


@app.get("/api/repair/history")
async def api_repair_history() -> JSONResponse:
    """Get repair action history (persisted JSONL)."""
    from phone.repair import RepairModule

    if client is None:
        return JSONResponse({"error": "Device not connected"}, status_code=503)

    repair_module = RepairModule(client, history_path=_repair_history_path())

    return JSONResponse(
        {
            "history": [_repair_result_json(r) for r in repair_module.history],
            "total": len(repair_module.history),
        }
    )


# ===== Device File Manager (Phone Manager pillar) =====

_DEVICE_PATH_RE = re.compile(r"^[A-Za-z0-9/._\- ()]+$")
_PULLS_DIR = Path(os.getenv("DEVICE_PULLS_DIR", str(PROJECT_ROOT / "data" / "pulls")))


def _device_client_or_503() -> tuple[Any, JSONResponse | None]:
    try:
        return _ensure_client(), None
    except (ConnectionError, OSError, PhoneError) as exc:
        return None, JSONResponse({"error": f"Device not connected: {exc}"}, status_code=503)


def _list_device_dir_blocking(c: Any, path: str) -> list[dict[str, Any]]:
    """Parse `ls -la <path>` from the device into typed entries."""
    out = c.execute("shell", "ls", "-la", path)
    entries: list[dict[str, Any]] = []
    for line in out.splitlines():
        m = re.match(
            r"^([\-dl][rwxsStT\-]{9})\s+\S+\s+\S+\s+\S+\s+(\d+)\s+"
            r"\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}\s+(.+)$",
            line.rstrip(),
        )
        if not m:
            continue
        perms, size, name = m.group(1), int(m.group(2)), m.group(3)
        kind = "dir" if perms.startswith("d") else ("link" if perms.startswith("l") else "file")
        if name in (".", ".."):
            continue
        entries.append({"name": name, "kind": kind, "size": size})
    entries.sort(key=lambda e: (e["kind"] != "dir", e["name"].lower()))
    return entries


def _device_pull_blocking(c: Any, remote: str, dest_dir: Path) -> dict[str, Any]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    name = remote.rstrip("/").split("/")[-1] or "device-item"
    c.pull(remote, str(dest_dir / name))
    # Report the host-visible relative path (the container binds
    # ./data/pulls -> /app/data/pulls so the file lands on the host).
    return {"local_path": f"data/pulls/{name}", "name": name}


@app.get("/api/device/files")
async def api_device_files(path: str = "/sdcard/") -> JSONResponse:
    """List a directory on the device (Phone Manager browse)."""
    if not _DEVICE_PATH_RE.fullmatch(path):
        return JSONResponse({"error": "Invalid device path"}, status_code=400)
    c, err = _device_client_or_503()
    if err is not None:
        return err
    loop = asyncio.get_running_loop()
    try:
        entries = await loop.run_in_executor(None, _list_device_dir_blocking, c, path)
    except PhoneError as exc:
        return JSONResponse({"error": str(exc)}, status_code=502)
    return JSONResponse({"path": path, "entries": entries, "total": len(entries)})


class DevicePullRequest(BaseModel):
    remote_path: str


@app.post("/api/device/files/pull")
async def api_device_files_pull(request: DevicePullRequest) -> JSONResponse:
    """Pull a file or directory from the device into data/pulls/."""
    if not _DEVICE_PATH_RE.fullmatch(request.remote_path):
        return JSONResponse({"error": "Invalid device path"}, status_code=400)
    c, err = _device_client_or_503()
    if err is not None:
        return err
    loop = asyncio.get_running_loop()
    try:
        result = await loop.run_in_executor(
            None, _device_pull_blocking, c, request.remote_path, _PULLS_DIR
        )
    except PhoneError as exc:
        return JSONResponse({"error": str(exc)}, status_code=502)
    return JSONResponse(result)


class DeviceDeleteRequest(BaseModel):
    path: str
    confirm: bool = False


@app.post("/api/device/files/delete")
async def api_device_files_delete(request: DeviceDeleteRequest) -> JSONResponse:
    """Delete a FILE on the device. Confirm-gated; directories refused."""
    if not _DEVICE_PATH_RE.fullmatch(request.path):
        return JSONResponse({"error": "Invalid device path"}, status_code=400)
    if request.path.rstrip("/") in ("/sdcard", "/sdcard/", "/"):
        return JSONResponse({"error": "Refusing to delete a root path"}, status_code=400)
    if not request.confirm:
        return JSONResponse(
            {
                "status": "confirmation_required",
                "path": request.path,
                "message": "Device file deletion requires explicit confirmation (set confirm=true).",
            },
            status_code=202,
        )
    c, err = _device_client_or_503()
    if err is not None:
        return err
    loop = asyncio.get_running_loop()

    def delete_file() -> None:
        listing = c.execute("shell", "ls", "-la", request.path)
        # Only plain files: refuse dirs and missing paths by inspecting perms.
        first = next((ln for ln in listing.splitlines() if ln.strip().startswith("-")), None)
        if first is None:
            raise PhoneError("Path is not a plain file (missing or a directory)")
        c.execute("shell", "rm", "--", request.path)

    try:
        await loop.run_in_executor(None, delete_file)
    except PhoneError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return JSONResponse({"deleted": request.path})


# ===== Root / Magisk API (root card) =====

# Magisk module ids are directory names under /data/adb/modules; this
# whitelist keeps shell metacharacters and path traversal out of the su
# command line.
_MODULE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")

_MODULE_ACTIONS = ("enable", "disable", "remove")


class ModuleActionRequest(BaseModel):
    """Request model for Magisk module state changes (confirm-gated)."""

    confirm: bool = False


def _root_client_or_503() -> tuple[Any, JSONResponse | None]:
    """Live client for root endpoints, or the 503 response to return."""
    try:
        return _ensure_client(), None
    except (ConnectionError, OSError) as exc:
        return None, JSONResponse({"error": f"Device not connected: {exc}"}, status_code=503)


@app.get("/api/root")
async def api_root() -> JSONResponse:
    """Full root/Magisk state (root card source of truth)."""
    c, err = _root_client_or_503()
    if err is not None:
        return err
    info = await asyncio.get_running_loop().run_in_executor(None, c.root.get_root_info)
    return JSONResponse({"root": info.model})


@app.get("/api/root/modules")
async def api_root_modules() -> JSONResponse:
    """List installed Magisk modules (empty list pre-root)."""
    c, err = _root_client_or_503()
    if err is not None:
        return err
    modules = await asyncio.get_running_loop().run_in_executor(None, c.root.list_modules)
    return JSONResponse({"modules": modules, "total": len(modules)})


@app.post("/api/root/modules/{module_id}/{action}")
async def api_root_module_action(
    module_id: str, action: str, request: ModuleActionRequest
) -> JSONResponse:
    """Enable/disable/remove a Magisk module. Requires `confirm: true`."""
    if action not in _MODULE_ACTIONS:
        return JSONResponse(
            {"error": f"Unknown module action: {action}. Use enable|disable|remove"},
            status_code=400,
        )
    if not _MODULE_ID_RE.fullmatch(module_id):
        return JSONResponse({"error": "Invalid module id"}, status_code=400)
    if not request.confirm:
        return JSONResponse(
            {
                "status": "confirmation_required",
                "module_id": module_id,
                "action": action,
                "message": "Module changes require explicit confirmation (set confirm=true).",
            },
            status_code=202,
        )

    c, err = _root_client_or_503()
    if err is not None:
        return err
    loop = asyncio.get_running_loop()
    try:
        await loop.run_in_executor(None, c.root.set_module_state, module_id, action, True)
    except Exception as exc:  # noqa: BLE001 - surface su failures honestly
        return JSONResponse(
            {"success": False, "error": str(exc), "module_id": module_id, "action": action},
            status_code=500,
        )
    return JSONResponse(
        {
            "success": True,
            "module_id": module_id,
            "action": action,
            "message": (
                f"Module {module_id} {action}d. Takes effect on the next reboot "
                "(disable/remove are marker files Magisk applies at boot)."
            ),
        }
    )


# ===== Devin Control API (for Groq bot via Tailscale) =====


@app.get("/api/devin/status", dependencies=[Depends(verify_api_key)])
async def devin_status() -> JSONResponse:
    """Get Devin status - check if Devin processes are running."""
    try:
        # Check for Devin-related processes
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq devin*", "/FO", "CSV"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        processes = result.stdout.strip().split("\n") if result.stdout else []

        # Check if Devin workdir exists
        workdir_exists = DEVIN_WORKDIR.exists()

        return JSONResponse(
            {
                "status": "running" if len(processes) > 1 else "stopped",
                "workdir": str(DEVIN_WORKDIR),
                "workdir_exists": workdir_exists,
                "processes": processes[1:] if len(processes) > 1 else [],
            }
        )
    except OSError as exc:
        # Devin CLI/workdir/tools missing (e.g. inside the Docker
        # container) - degrade like /api/health instead of a raw 500.
        logger.warning("Devin endpoint unavailable: %s", exc)
        raise HTTPException(
            status_code=503, detail=f"Devin environment unavailable: {exc}"
        ) from exc
    except Exception as exc:
        logger.error("Devin status check failed: %s", exc)
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.post("/api/devin/execute", dependencies=[Depends(verify_api_key)])
async def devin_execute(request: CommandRequest) -> JSONResponse:
    """Execute a shell command in the Devin working directory."""
    workdir = Path(request.workdir) if request.workdir else DEVIN_WORKDIR

    if not workdir.exists():
        raise HTTPException(status_code=404, detail=f"Working directory not found: {workdir}")

    # Security: restrict to workdir and subdirectories
    try:
        workdir.resolve().relative_to(DEVIN_WORKDIR.resolve())
    except ValueError:
        raise HTTPException(
            status_code=403, detail="Access denied: path outside Devin workdir"
        ) from None

    try:
        proc = await asyncio.create_subprocess_shell(
            request.command,
            cwd=str(workdir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=request.timeout,
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise HTTPException(
                status_code=408, detail=f"Command timed out after {request.timeout}s"
            ) from None

        return JSONResponse(
            {
                "exit_code": proc.returncode,
                "stdout": stdout.decode("utf-8", errors="replace"),
                "stderr": stderr.decode("utf-8", errors="replace"),
                "command": request.command,
                "workdir": str(workdir),
            }
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Command execution failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/devin/files", dependencies=[Depends(verify_api_key)])
async def devin_list_files(path: str = ".") -> JSONResponse:
    """List files in Devin working directory."""
    target_path = (DEVIN_WORKDIR / path).resolve()

    # Security: restrict to workdir and subdirectories
    try:
        target_path.relative_to(DEVIN_WORKDIR.resolve())
    except ValueError:
        raise HTTPException(
            status_code=403, detail="Access denied: path outside Devin workdir"
        ) from None

    if not target_path.exists():
        raise HTTPException(status_code=404, detail="Path not found")

    if target_path.is_file():
        # Return file info
        stat = target_path.stat()
        return JSONResponse(
            {
                "type": "file",
                "path": str(target_path.relative_to(DEVIN_WORKDIR)),
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            }
        )

    # List directory contents
    items = []
    for item in target_path.iterdir():
        try:
            stat = item.stat()
            items.append(
                {
                    "name": item.name,
                    "path": str(item.relative_to(DEVIN_WORKDIR)),
                    "type": "directory" if item.is_dir() else "file",
                    "size": stat.st_size if item.is_file() else None,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                }
            )
        except Exception:
            pass  # Skip items we can't stat

    return JSONResponse(
        {
            "path": str(target_path.relative_to(DEVIN_WORKDIR)) or ".",
            "items": sorted(items, key=lambda x: (x["type"] == "file", x["name"].lower())),
        }
    )


@app.get("/api/devin/files/read", dependencies=[Depends(verify_api_key)])
async def devin_read_file(path: str) -> JSONResponse:
    """Read a file from Devin working directory."""
    target_path = (DEVIN_WORKDIR / path).resolve()

    # Security: restrict to workdir and subdirectories
    try:
        target_path.relative_to(DEVIN_WORKDIR.resolve())
    except ValueError:
        raise HTTPException(
            status_code=403, detail="Access denied: path outside Devin workdir"
        ) from None

    if not target_path.exists() or not target_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    # Limit file size to 1MB for safety
    if target_path.stat().st_size > 1_048_576:
        raise HTTPException(status_code=413, detail="File too large (max 1MB)")

    try:
        content = target_path.read_text(encoding="utf-8")
        return JSONResponse(
            {
                "path": str(target_path.relative_to(DEVIN_WORKDIR)),
                "content": content,
                "size": len(content),
            }
        )
    except UnicodeDecodeError:
        raise HTTPException(status_code=415, detail="File is not valid UTF-8 text") from None
    except OSError as exc:
        # Devin CLI/workdir/tools missing (e.g. inside the Docker
        # container) - degrade like /api/health instead of a raw 500.
        logger.warning("Devin endpoint unavailable: %s", exc)
        raise HTTPException(
            status_code=503, detail=f"Devin environment unavailable: {exc}"
        ) from exc
    except Exception as exc:
        logger.error("File read failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/devin/files/write", dependencies=[Depends(verify_api_key)])
async def devin_write_file(request: FileRequest) -> JSONResponse:
    """Write a file to Devin working directory."""
    target_path = (DEVIN_WORKDIR / request.path).resolve()

    # Security: restrict to workdir and subdirectories
    try:
        target_path.relative_to(DEVIN_WORKDIR.resolve())
    except ValueError:
        raise HTTPException(
            status_code=403, detail="Access denied: path outside Devin workdir"
        ) from None

    # Create parent directories if needed
    target_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        if request.content is not None:
            target_path.write_text(request.content, encoding="utf-8")
        else:
            target_path.write_text("", encoding="utf-8")

        return JSONResponse(
            {
                "path": str(target_path.relative_to(DEVIN_WORKDIR)),
                "size": target_path.stat().st_size,
                "status": "written",
            }
        )
    except OSError as exc:
        # Devin CLI/workdir/tools missing (e.g. inside the Docker
        # container) - degrade like /api/health instead of a raw 500.
        logger.warning("Devin endpoint unavailable: %s", exc)
        raise HTTPException(
            status_code=503, detail=f"Devin environment unavailable: {exc}"
        ) from exc
    except Exception as exc:
        logger.error("File write failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.delete("/api/devin/files", dependencies=[Depends(verify_api_key)])
async def devin_delete_file(path: str) -> JSONResponse:
    """Delete a file from Devin working directory."""
    target_path = (DEVIN_WORKDIR / path).resolve()

    # Security: restrict to workdir and subdirectories
    try:
        target_path.relative_to(DEVIN_WORKDIR.resolve())
    except ValueError:
        raise HTTPException(
            status_code=403, detail="Access denied: path outside Devin workdir"
        ) from None

    if not target_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    if target_path.is_dir():
        raise HTTPException(status_code=400, detail="Cannot delete directories via this endpoint")

    try:
        target_path.unlink()
        return JSONResponse(
            {
                "path": str(target_path.relative_to(DEVIN_WORKDIR)),
                "status": "deleted",
            }
        )
    except OSError as exc:
        # Devin CLI/workdir/tools missing (e.g. inside the Docker
        # container) - degrade like /api/health instead of a raw 500.
        logger.warning("Devin endpoint unavailable: %s", exc)
        raise HTTPException(
            status_code=503, detail=f"Devin environment unavailable: {exc}"
        ) from exc
    except Exception as exc:
        logger.error("File delete failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/devin/logs", dependencies=[Depends(verify_api_key)])
async def devin_logs(lines: int = 100) -> JSONResponse:
    """Get recent Devin logs from the working directory."""
    log_files = list(DEVIN_WORKDIR.rglob("*.log"))

    if not log_files:
        return JSONResponse({"logs": [], "message": "No log files found"})

    # Get the most recent log file
    latest_log = max(log_files, key=lambda f: f.stat().st_mtime)

    try:
        content = latest_log.read_text(encoding="utf-8", errors="replace")
        log_lines = content.strip().split("\n")
        return JSONResponse(
            {
                "log_file": str(latest_log.relative_to(DEVIN_WORKDIR)),
                "lines": log_lines[-lines:] if len(log_lines) > lines else log_lines,
                "total_lines": len(log_lines),
            }
        )
    except OSError as exc:
        # Devin CLI/workdir/tools missing (e.g. inside the Docker
        # container) - degrade like /api/health instead of a raw 500.
        logger.warning("Devin endpoint unavailable: %s", exc)
        raise HTTPException(
            status_code=503, detail=f"Devin environment unavailable: {exc}"
        ) from exc
    except Exception as exc:
        logger.error("Log read failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def main() -> None:
    """Entry point for `python dashboard/app.py`."""
    import uvicorn

    # 8080 is commonly taken on this machine (e.g. env-manager-frontend);
    # override with DASHBOARD_PORT when a specific port is required.
    host = os.getenv("DASHBOARD_HOST", "127.0.0.1")
    port = int(os.getenv("DASHBOARD_PORT", "8081"))
    # Pass the app object directly: dashboard/ has no __init__.py, so the
    # "dashboard.app" import string cannot resolve from every working dir.
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
