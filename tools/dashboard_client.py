#!/usr/bin/env python3
"""CLI client for the dashboard REST API (what remote agents/bots call).

stdlib-only (urllib). Auth: X-API-Key from .env (GROQ_BOT_API_KEY) or
--key. Default base URL is the local dashboard; use --base-url with the
tailnet address (http://100.83.120.93:8081) to control the phone from
anywhere on the tailnet.

Usage:
    python tools/dashboard_client.py health
    python tools/dashboard_client.py trends battery.level --period hourly
    python tools/dashboard_client.py repair-actions
    python tools/dashboard_client.py diagnose            # POST diagnostics run
    python tools/dashboard_client.py repair clear_app_caches --confirm
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import socket
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
DEFAULT_BASE = "http://localhost:8081"

# Private/internal IP ranges to block for SSRF protection.
# 100.64.0.0/10 (CGNAT, includes Tailscale 100.x.x.x) is ALLOWED.
_PRIVATE_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),  # link-local
    ipaddress.ip_network("::1/128"),  # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),  # IPv6 ULA
]


def _validate_base_url(base_url: str, allow_private: bool = False) -> None:
    """Validate base URL against SSRF: block private/internal IPs.

    Tailscale CGNAT (100.64.0.0/10) is explicitly allowed.
    """
    if not base_url.lower().startswith(("http://", "https://")):
        raise ValueError("--base-url must use http:// or https://")

    parsed = urllib.parse.urlparse(base_url)
    host = parsed.hostname or ""
    if not host:
        raise ValueError("--base-url must include a hostname")

    # Resolve host to IPs (A + AAAA)
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as e:
        raise ValueError(f"could not resolve {host}: {e}") from e

    for info in infos:
        ip_str = info[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        # Allow Tailscale CGNAT (100.64.0.0/10) - only for IPv4
        if ip.version == 4:
            if (
                ipaddress.IPv4Address("100.64.0.0")
                <= ip
                <= ipaddress.IPv4Address("100.127.255.255")
            ):
                continue
        # Block other private ranges
        for net in _PRIVATE_NETWORKS:
            if ip in net:
                if allow_private:
                    continue
                raise ValueError(
                    f"--base-url resolves to private IP {ip_str} ({host}); "
                    "use --allow-private to override (not recommended)"
                )


def load_api_key() -> str | None:
    env = REPO / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("GROQ_BOT_API_KEY="):
                return line.split("=", 1)[1].strip()
    return None


def request(
    base: str,
    path: str,
    key: str | None,
    method: str = "GET",
    body: dict[str, Any] | None = None,
    allow_private: bool = False,
) -> tuple[int, dict[str, Any]]:
    """Fetch base+path. Re-validates against SSRF on every call so no
    fetch can bypass the private-IP blocklist, even if a caller skips
    main()'s upfront validation."""
    _validate_base_url(base, allow_private=allow_private)
    req = urllib.request.Request(base.rstrip("/") + path, method=method)
    if key:
        req.add_header("X-API-Key", key)
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, data=data, timeout=120) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except json.JSONDecodeError:
            return e.code, {"detail": e.reason}
    except urllib.error.URLError as e:
        raise SystemExit(f"dashboard unreachable at {base}: {e.reason}") from e


def print_result(label: str, status: int, payload: dict[str, Any]) -> int:
    print(f"[{status}] {label}")
    print(json.dumps(payload, indent=2)[:2000])
    return 0 if status < 400 else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-url", default=DEFAULT_BASE)
    parser.add_argument("--key", default=None, help="API key (default: .env)")
    parser.add_argument(
        "--allow-private",
        action="store_true",
        help="Allow private IPs (e.g., localhost, LAN) - NOT recommended for production",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("health")
    sub.add_parser("metrics")
    sub.add_parser("repair-actions")
    sub.add_parser("repair-history")
    sub.add_parser("diagnose")
    sub.add_parser("insights")
    sub.add_parser("alerts")
    p_t = sub.add_parser("trends")
    p_t.add_argument("metric")
    p_t.add_argument("--period", choices=["hourly", "daily", "stats"], default="hourly")
    p_t.add_argument("--hours", type=int, default=24)
    p_r = sub.add_parser("repair")
    p_r.add_argument("action")
    p_r.add_argument(
        "--confirm", action="store_true", help="required to execute; without it the call is refused"
    )
    args = parser.parse_args(argv)
    _validate_base_url(args.base_url, allow_private=args.allow_private)
    key = args.key or load_api_key()

    if args.cmd == "health":
        s, p = request(args.base_url, "/api/health", key, allow_private=args.allow_private)
    elif args.cmd == "metrics":
        s, p = request(
            args.base_url, "/api/trends/metrics?hours=24", key, allow_private=args.allow_private
        )
    elif args.cmd == "repair-actions":
        s, p = request(args.base_url, "/api/repair/actions", key, allow_private=args.allow_private)
    elif args.cmd == "repair-history":
        s, p = request(args.base_url, "/api/repair/history", key, allow_private=args.allow_private)
    elif args.cmd == "insights":
        s, p = request(args.base_url, "/api/insights", key, allow_private=args.allow_private)
    elif args.cmd == "alerts":
        s, p = request(args.base_url, "/api/alerts", key, allow_private=args.allow_private)
    elif args.cmd == "diagnose":
        s, p = request(
            args.base_url,
            "/api/diagnostics/run",
            key,
            method="POST",
            body={},
            allow_private=args.allow_private,
        )
    elif args.cmd == "trends":
        s, p = request(
            args.base_url,
            f"/api/trends/{args.period}/{args.metric}?hours={args.hours}",
            key,
            allow_private=args.allow_private,
        )
    else:  # repair
        if not args.confirm:
            print("refusing to execute a repair without --confirm", file=sys.stderr)
            return 2
        s, p = request(
            args.base_url,
            "/api/repair/execute",
            key,
            method="POST",
            body={"action": args.action, "confirm": True},
            allow_private=args.allow_private,
        )
    return print_result(args.cmd, s, p)


if __name__ == "__main__":
    raise SystemExit(main())
