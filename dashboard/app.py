#!/usr/bin/env python3
"""Galaxy S22+ Monitoring Dashboard (staged build - stub)."""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "phone-lib" / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "diagnostics"))

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException, Depends, Header  # noqa: E402
from fastapi.responses import HTMLResponse, JSONResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from fastapi.templating import Jinja2Templates  # noqa: E402
from fastapi.security import APIKeyHeader  # noqa: E402

from phone import create_client  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

COLLECT_INTERVAL_S = 5
MAX_HISTORY = 17_280  # 24 h at 5 s cadence

STATIC_DIR = Path(__file__).resolve().parent / "static"
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

manager = None
client = None
history: list[dict] = []


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

    async def broadcast(self, message: dict) -> None:
        dead = []
        for ws in self.active:
            try:
                await ws.send_json(message)
            except Exception:  # noqa: BLE001 - any send failure drops the client
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()
client = None
history: list[dict] = []


def _collect_once() -> dict:
    """One blocking collection pass (runs in a worker thread)."""
    global client
    if client is None:
        client = create_client()
        if not client.is_connected:
            raise ConnectionError("No ADB device connected")

    device = client.device.get_device_info()
    battery = client.battery.get_battery_info()
    partitions = client.storage.get_storage_info()
    network = client.network.get_network_info()
    thermal = client.thermal.get_thermal_info()
    cpu_raw = client.device.get_cpu_info()
    mem = client.device.get_memory_info()
    running = client.apps.get_running_apps()
    rooted = client.root.is_rooted()

    per_core_mhz = [
        c.get("cpu MHz", 0) for c in cpu_raw.get("details", []) if isinstance(c, dict)
    ]
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
        },
        "storage": [
            {
                "mount_point": p.mount_point,
                "total_gb": round(p.total_gb, ),
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
            "usage_percent": round(
                (mem_total_kb - mem_avail_kb) / mem_total_kb * 100, 1
            ) if mem_total_kb else 0.0,
        },
        "apps": {"running_count": len(running), "running": running[:10]},
        "root": {"rooted": rooted},
    }
    return snapshot


async def collector_loop() -> None:
    """Periodically collect a snapshot, store it, and broadcast to WS clients."""
    global history
    while True:
        try:
            loop = asyncio.get_running_loop()
            metrics = await loop.run_in_executor(None, _collect_once)
            history.append(metrics)
            if len(history) > MAX_HISTORY:
                del history[: len(history) - MAX_HISTORY]
            await manager.broadcast({"type": "metrics", "data": metrics})
        except ConnectionError:
            # Device unplugged: keep the loop alive, retry after the interval.
            logger.warning("Device not connected; retrying in %ss", COLLECT_INTERVAL_S)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - collector must never die
            logger.error("Collector error: %s", exc)
        await asyncio.sleep(COLLECT_INTERVAL_S)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start/stop the background collector around the app lifetime."""
    task = asyncio.create_task(collector_loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="Galaxy S22+ Monitoring Dashboard",
    description="Real-time device monitoring via ADB",
    version="1.0.0",
    lifespan=lifespan,
)

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard page."""
    return templates.TemplateResponse(request, "dashboard.html")


@app.get("/api/health")
async def api_health():
    """Current snapshot (triggers a fresh collection)."""
    loop = asyncio.get_running_loop()
    try:
        metrics = await loop.run_in_executor(None, _collect_once)
    except ConnectionError:
        return JSONResponse({"error": "Device not connected"}, status_code=503)
    except RuntimeError as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)
    return JSONResponse(metrics)


@app.get("/api/history")
async def api_history(hours: int = 24):
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
async def api_history_metric(metric: str, hours: int = 24):
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


@app.websocket("/ws/live")
async def ws_live(websocket: WebSocket):
    """Live updates: initial snapshot, then collector broadcasts."""
    await manager.connect(websocket)
    try:
        loop = asyncio.get_running_loop()
        try:
            initial = await loop.run_in_executor(None, _collect_once)
            await websocket.send_json({"type": "initial", "data": initial})
        except (ConnectionError, RuntimeError):
            await websocket.send_json({"type": "error", "data": "device not available"})
        while True:
            await websocket.receive_text()  # keepalive pings from the client
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as exc:  # noqa: BLE001 - never crash the WS handler
        logger.error("WebSocket error: %s", exc)
        manager.disconnect(websocket)


@app.post("/api/diagnostics/run")
async def api_diagnostics_run():
    """Trigger a full diagnostics run via DiagnosticsRunner."""
    from diagnostics.run_diagnostics import DiagnosticsRunner

    config_path = PROJECT_ROOT / "diagnostics" / "config.yaml"
    runner = DiagnosticsRunner(config_path)
    loop = asyncio.get_running_loop()
    exit_code = await loop.run_in_executor(None, runner.run)
    status = {0: "completed", 1: "issues_found", 2: "critical"}.get(exit_code, "error")
    return JSONResponse({"exit_code": exit_code, "status": status})


def main() -> None:
    """Entry point for `python dashboard/app.py`."""
    import uvicorn

    host = os.getenv("DASHBOARD_HOST", "127.0.0.1")
    port = int(os.getenv("DASHBOARD_PORT", "8080"))
    uvicorn.run("dashboard.app:app", host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
