#!/usr/bin/env python3
"""Battle test: hammer the live dashboard API to surface stalls, flakes, and N/A drift.

Read-only GET endpoints only — nothing mutating (no diagnostics/run, no repair
execute, no file delete). Safe to run against the production tailnet instance.

Usage:
    python tools/battle_test.py [--base http://127.0.0.1:8081] [--rounds 6] [--workers 12]
"""

from __future__ import annotations

import argparse
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from urllib import request as urlreq
from urllib.error import HTTPError

# Public, read-only endpoints. Protected /api/devin/* are probed separately
# for auth-enforcement (401/403 without a key), never for content.
ENDPOINTS: list[str] = [
    "/",
    "/alerts",
    "/whatsapp",
    "/api/health",
    "/api/history",
    "/api/history/battery.level",
    "/api/trends/metrics",
    "/api/trends/hourly/battery.level",
    "/api/trends/daily/battery.level",
    "/api/trends/stats/battery.level",
    "/api/alerts",
    "/api/insights",
    "/api/whatsapp/exports",
    "/api/whatsapp/chats?q=hello",
    "/api/fleet",
    "/api/repair/actions",
    "/api/rounds" if False else "/api/repair/history",
    "/api/device/files",
    "/api/backup/status",
]

# Endpoints that may legitimately return an empty/error payload when the
# backing data is missing — recorded, not counted as failures.
DEGRADED_OK = {"/api/whatsapp/exports", "/api/whatsapp/chats?q=hello"}


def hit(url: str, timeout: float = 6.0) -> tuple[int, float, int]:
    """One request. Returns (status, latency_ms, body_len); status 0 = transport error."""
    t0 = time.perf_counter()
    try:
        with urlreq.urlopen(url, timeout=timeout) as r:
            return r.status, (time.perf_counter() - t0) * 1000, len(r.read())
    except HTTPError as e:
        return e.code, (time.perf_counter() - t0) * 1000, 0
    except Exception:
        return 0, (time.perf_counter() - t0) * 1000, 0


def pctl(xs: list[float], p: float) -> float:
    if not xs:
        return 0.0
    s = sorted(xs)
    idx = min(len(s) - 1, int(round(p / 100 * (len(s) - 1))))
    return s[idx]


def summarize(latencies: list[float]) -> dict[str, float]:
    return {
        "n": len(latencies),
        "mean": statistics.mean(latencies) if latencies else 0.0,
        "p50": pctl(latencies, 50),
        "p95": pctl(latencies, 95),
        "max": max(latencies) if latencies else 0.0,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", default="http://127.0.0.1:8081")
    ap.add_argument("--rounds", type=int, default=6)
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--timeout", type=float, default=6.0)
    args = ap.parse_args(argv)

    print(f"Battle test vs {args.base}  ({args.rounds} rounds x {args.workers} workers)")
    print("=" * 72)

    all_lat: list[float] = []
    failures: dict[str, list[str]] = {}
    slow: dict[str, float] = {}
    per_ep: dict[str, list[float]] = {ep: [] for ep in ENDPOINTS}

    for round_no in range(1, args.rounds + 1):
        t_round = time.perf_counter()
        jobs: list[tuple[str, str]] = [(ep, f"{args.base}{ep}") for ep in ENDPOINTS]
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            results = list(pool.map(lambda j: (j[0], *hit(j[1], args.timeout)), jobs))
        for ep, status, ms, _size in results:
            per_ep[ep].append(ms)
            all_lat.append(ms)
            if ms > 2000:
                slow[ep] = max(slow.get(ep, 0.0), ms)
            if status == 0:
                failures.setdefault(ep, []).append("transport-error/000")
            elif status >= 500:
                failures.setdefault(ep, []).append(f"HTTP {status}")
            elif status in (404, 405) and ep not in DEGRADED_OK:
                failures.setdefault(ep, []).append(f"HTTP {status} (unexpected)")
        print(
            f"  round {round_no}/{args.rounds}: "
            f"{len(results)} reqs in {(time.perf_counter() - t_round) * 1000:.0f} ms"
        )

    print("\nPer-endpoint latency (ms)  [n = requests, across all rounds]")
    print("-" * 72)
    for ep, lats in per_ep.items():
        s = summarize(lats)
        flag = ""
        if ep in failures:
            flag = f"  << FAIL {failures[ep][0]}"
        elif s["max"] > 2000:
            flag = "  << SLOW"
        print(
            f"  {ep:<38} n={s['n']:<4} p50={s['p50']:>7.0f}  p95={s['p95']:>7.0f}  "
            f"max={s['max']:>7.0f}{flag}"
        )

    # ---- Insights stall probe: the endpoint with the event-loop-stall history.
    print("\nInsights stall probe (3 concurrent bursts of 12, no pacing)")
    print("-" * 72)
    insights_url = f"{args.base}/api/insights"
    worst = 0.0
    errs = 0
    for burst in range(3):
        with ThreadPoolExecutor(max_workers=12) as pool:
            outs = list(pool.map(lambda _: hit(insights_url, args.timeout), range(12)))
        for status, ms, _ in outs:
            worst = max(worst, ms)
            if status == 0 or status >= 500:
                errs += 1
        print(f"  burst {burst + 1}/3: 12 reqs, worst {max(m for _, m, _ in outs):.0f} ms")
    # Post-burst single should be a cache-hit (TTL 60 s): fast, not a cold compute.
    status, ms, _ = hit(insights_url, args.timeout)
    print(f"  post-burst single: {status} in {ms:.0f} ms (worst burst req: {worst:.0f} ms)")

    # ---- Auth enforcement: protected endpoints must NOT serve content without a key.
    print("\nAuth enforcement probe (expect 401/403, content = failure)")
    print("-" * 72)
    for ep in ("/api/devin/status", "/api/devin/files"):
        status, _ms, size = hit(f"{args.base}{ep}", args.timeout)
        verdict = "OK" if status in (401, 403) else f"UNEXPECTED ({status}, {size}B)"
        print(f"  {ep:<24} -> {status}  {verdict}")

    # ---- Verdict
    print("\n" + "=" * 72)
    total_reqs = len(all_lat)
    err_count = sum(len(v) for v in failures.values())
    s = summarize(all_lat)
    print(
        f"TOTAL {total_reqs} requests | errors {err_count} | "
        f"p50 {s['p50']:.0f} ms | p95 {s['p95']:.0f} ms | max {s['max']:.0f} ms"
    )
    if failures:
        print("FAILURES:")
        for ep, msgs in failures.items():
            print(f"  {ep}: {msgs[:3]}{' ...' if len(msgs) > 3 else ''}")
    if slow:
        print("SLOW (>2s): " + ", ".join(f"{ep} {ms:.0f}ms" for ep, ms in slow.items()))
    verdict = "PASS" if err_count == 0 and not slow else "FAIL"
    print(f"\nVERDICT: {verdict}")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
