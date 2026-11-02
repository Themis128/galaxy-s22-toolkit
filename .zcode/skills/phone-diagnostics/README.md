# Phone Diagnostics Skill

Comprehensive health check for Android devices: battery health, storage usage, network connectivity, thermal status, and crash/ANR detection from logcat.

## Installation

```bash
pip install -e .
```

## Usage

```bash
# Run full diagnostic suite
phone-diagnostics run

# Full diagnostic report as JSON
phone-diagnostics run --json

# Custom log check window (default: 60 minutes)
phone-diagnostics run --log-minutes 120

# Quick device info check
phone-diagnostics device

# Quick battery health check
phone-diagnostics battery

# Check storage usage
phone-diagnostics storage

# Check for crashes in last 2 hours
phone-diagnostics logs -m 120

# Network connectivity status
phone-diagnostics network

# Thermal status
phone-diagnostics thermal

# Full report as JSON for automation
phone-diagnostics run --json --quiet
```

See [SKILL.md](SKILL.md) for full documentation.