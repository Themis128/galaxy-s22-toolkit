# phone-repair

Approved repair actions for the Galaxy S22+ toolkit. Wraps
`phone.repair.RepairModule` with the toolkit's approval policy and persistent
JSONL history.

## Install

```bash
pip install -e .zcode/skills/phone-repair
```

## Usage

```bash
phone-repair list        # all actions with risk levels
phone-repair recommend   # based on the latest saved diagnostics report
phone-repair run auto    # run all auto-approve (low-risk) actions
phone-repair run flush_dns clear_logcat_buffers
phone-repair history     # persisted JSONL history
```

See SKILL.md for the full command reference and safety model.
