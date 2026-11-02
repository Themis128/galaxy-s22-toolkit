#!/usr/bin/env python3
"""
Galaxy S22+ Monitoring Dashboard

FastAPI + WebSocket + Chart.js real-time monitoring dashboard.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path

# Add phone-lib and diagnostics to path before importing phone
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "phone-lib" / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "diagnostics"))

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect  # noqa: E402
from fastapi.responses import HTMLResponse, JSONResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from fastapi.templating import Jinja2Templates  # noqa: E402

from phone import (  # noqa: E402
    create_client,
    DeviceModule,
    BatteryModule,
    StorageModule,
    LogcatModule,
    NetworkModule,
    ThermalModule,
    AppsModule,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manage WebSocket connections."""
    
    def __init__(self):
        self.active_connections: list[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"Client connected. Total: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"Client disconnected. Total: {len(self.active_connections)}")
    
    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients."""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)
        
        for conn in disconnected:
            self.disconnect(conn)


manager = ConnectionManager()
client = None
device_module = None
battery_module = None
storage_module = None
logcat_module = None
network_module = None
thermal_module = None
apps_module = None

history: list[dict] = []
MAX_HISTORY = 1440  # 24 hours at 1-minute intervals


def init_phone_client():
    """Initialize phone client."""
    global client, device_module, battery_module, storage_module
    global logcat_module, network_module, thermal_module, apps_module
    
    try:
        client = create_client()
        device_module = DeviceModule(client)
        battery_module = BatteryModule(client)
        storage_module = StorageModule(client)
        logcat_module = LogcatModule(client)
        network_module = NetworkModule(client)
        thermal_module = ThermalModule(client)
        apps_module = AppsModule(client)
        logger.info("Phone client initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize phone client: {e}")
        return False


async def collect_metrics() -> dict:
    """Collect all metrics from device."""
    if not client:
        if not init_phone_client():
            return {"error": "Device not connected"}
    
    try:
        metrics = {}
        
        # Device info (cached)
        device_info = device_module.get_device_info()
        metrics["device"] = {
            "model": device_info.model,
            "android_version": device_info.android_version,
            "api_level": device_info.api_level,
            "security_patch": device_info.security_patch,
        }
        
        # Battery
        battery = battery_module.get_battery_info()
        metrics["battery"] = {
            "level": battery.level,
            "health": battery.health.value,
            "status": battery.status.value,
            "temperature_c": round(battery.temperature_c, 1),
            "temperature_f": round(battery.temperature_f, 1),
            "voltage_mv": battery.voltage_mv,
            "current_ma": battery.current_ma,
            "charge_cycles": battery.charge_cycles,
            "capacity_mah": battery.capacity_mah,
            "technology": battery.technology,
        }
        
        # Storage
        partitions = storage_module.get_storage_info()
        metrics["storage"] = [
            {
                "mount_point": p.mount_point,
                "total_gb": round(p.total_gb, 2),
                "used_gb": round(p.used_gb, 2),
                "free_gb": round(p.free_gb, 2),
                "usage_percent": round(p.usage_percent, 1),
                "filesystem": p.filesystem,
            }
            for p in partitions
        ]
        
        # Network
        network = network_module.get_network_info()
        metrics["network"] = {
            "wifi_connected": network.wifi_connected,
            "wifi_ssid": network.wifi_ssid,
            "wifi_signal_dbm": network.wifi_signal_dbm,
            "wifi_frequency_mhz": network.wifi_frequency_mhz,
            "wifi_ip": network.wifi_ip,
            "mobile_connected": network.mobile_connected,
            "mobile_operator": network.mobile_operator,
            "mobile_signal_dbm": network.mobile_signal_dbm,
            "mobile_network_type": network.mobile_network_type,
            "mobile_ip": network.mobile_ip,
            "dns_servers": network.dns_servers,
            "gateway": network.gateway,
            "internet_reachable": network.internet_reachable,
        }
        
        # Thermal
        thermal = thermal_module.get_thermal_info()
        metrics["thermal"] = {
            "overall_status": thermal.overall_status.value,
            "cpu_throttling": thermal.cpu_throttling,
            "gpu_throttling": thermal.gpu_throttling,
            "zones": [
                {
                    "name": z.name,
                    "temp_c": round(z.temp_c, 1),
                    "type": z.type.value,
                    "is_critical": z.is_critical,
                }
                for z in thermal.zones
            ],
        }
        
        # Apps
        running = apps_module.get_running_apps()
        metrics["apps"] = {
            "running_count": len(running),
            "running": running[:10],
        }
        
        # Timestamp
        metrics["timestamp"] = datetime.now().isoformat()
        
        return metrics
        
    except Exception as e:
        logger.error(f"Error collecting metrics: {e}")
        return {"error": str(e)}


async def metrics_collector():
    """Background task to collect metrics periodically."""
    while True:
        try:
            metrics = await collect_metrics()
            
            if "error" not in metrics:
                # Add to history
                history.append(metrics)
                if len(history) > MAX_HISTORY:
                    history.pop(0)
                
                # Broadcast to WebSocket clients
                await manager.broadcast({
                    "type": "metrics",
                    "data": metrics
                })
            
        except Exception as e:
            logger.error(f"Metrics collector error: {e}")
        
        await asyncio.sleep(60)  # Collect every minute


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting Galaxy S22+ Monitoring Dashboard")
    init_phone_client()
    
    # Start background collector
    collector_task = asyncio.create_task(metrics_collector())
    
    yield
    
    # Shutdown
    collector_task.cancel()
    try:
        await collector_task
    except asyncio.CancelledError:
        pass
    logger.info("Dashboard shutdown complete")


app = FastAPI(
    title="Galaxy S22+ Monitoring Dashboard",
    description="Real-time device monitoring via ADB",
    version="1.0.0",
    lifespan=lifespan,
)

# Static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard page."""
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/api/health")
async def health_check():
    """Current health snapshot."""
    metrics = await collect_metrics()
    return JSONResponse(metrics)


@app.get("/api/history")
async def get_history(hours: int = 24):
    """Get historical metrics."""
    cutoff = datetime.now() - timedelta(hours=hours)
    filtered = [
        m for m in history
        if datetime.fromisoformat(m["timestamp"]) > cutoff
    ]
    return JSONResponse(filtered)


@app.get("/api/history/{metric_type}")
async def get_metric_history(metric_type: str, hours: int = 24):
    """Get history for specific metric type."""
    cutoff = datetime.now() - timedelta(hours=hours)
    filtered = [
        m for m in history
        if datetime.fromisoformat(m["timestamp"]) > cutoff
    ]
    
    # Extract specific metric
    result = []
    for m in filtered:
        if metric_type in m:
            entry = {"timestamp": m["timestamp"], metric_type: m[metric_type]}
            result.append(entry)
    
    return JSONResponse(result)


@app.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    await manager.connect(websocket)
    try:
        # Send initial data
        metrics = await collect_metrics()
        await websocket.send_json({"type": "initial", "data": metrics})
        
        # Keep connection alive
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)


@app.post("/api/diagnostics/run")
async def run_diagnostics():
    """Trigger full diagnostics run."""
    # Import and run diagnostics
    from diagnostics.run_diagnostics import DiagnosticsRunner
    
    config_path = PROJECT_ROOT / "diagnostics" / "config.yaml"
    runner = DiagnosticsRunner(config_path)
    
    # Run in thread pool to avoid blocking
    loop = asyncio.get_event_loop()
    exit_code = await loop.run_in_executor(None, runner.run)
    
    return JSONResponse({
        "exit_code": exit_code,
        "status": "completed" if exit_code == 0 else "issues_found" if exit_code == 1 else "critical" if exit_code == 2 else "error"
    })


def main():
    """Main entry point."""
    import uvicorn
    
    host = os.getenv("DASHBOARD_HOST", "0.0.0.0")
    port = int(os.getenv("DASHBOARD_PORT", "8080"))
    reload = os.getenv("DASHBOARD_RELOAD", "false").lower() == "true"
    
    uvicorn.run(
        "dashboard.app:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info"
    )


if __name__ == "__main__":
    main()