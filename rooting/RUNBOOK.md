# RUNBOOK — Rooting the Galaxy S22+ (SM-S906B)

> ## ⚠️ READ FIRST — IRREVERSIBLE CONSEQUENCES
>
> - **Bootloader unlock wipes ALL data** on the phone (internal storage included).
> - **Knox eFuse trips permanently**: Samsung Pay/Wallet, Secure Folder, Samsung Pass
>   are lost **forever**, even after relocking or reflashing stock.
> - Warranty: software-related claims can be denied; hardware claims generally survive
>   but expect scrutiny. This is your device — decide with that knowledge.
> - **The Odin flash is manual.** This toolkit automates everything *around* the flash
>   (backup, preflight, verification, modules) — never the flash itself.

## Overview

| Stage | Tool | Manual? |
|---|---|---|
| 0. Preconditions | `phone-root preflight` | automated check |
| 1. Backup | `phone-root backup --yes` | automated |
| 2. OEM unlock + BL unlock | — | **manual** |
| 3. Firmware download | SamFw Tool / samfirm.js | manual (verify CSC match!) |
| 4. Magisk AP patch | Magisk app on phone | manual |
| 5. Odin flash | Odin | **manual** |
| 6. Verify | `phone-root verify` | automated |
| 7. Modules | `phone-root modules ...` | automated (gated) |

## Stage 0 — Preconditions

```bash
phone-root preflight          # must print GO
```

All blocking checks must pass: model = SM-S906B, `oem_unlock_allowed=1`
(enable Developer options → OEM unlocking on the phone first), battery ≥ 50 %.

## Stage 1 — Backup (backup-first gate)

```bash
phone-root backup --dry-run   # review
phone-root backup --yes       # writes data/backup-<ts>/
```

Verify `data/backup-<ts>/BACKUP-MANIFEST.json` exists and `apks/` is populated.
Extra safety (recommended): also copy photos you care about to a PC folder outside
`data/` and confirm Samsung Cloud/Google backup is current. Keep the backup until the
device is restored and stable.

## Stage 2 — Unlock the bootloader (manual)

1. Phone: Settings → About phone → Software information → tap **Build number** ×7.
2. Developer options → enable **OEM unlocking** (requires internet).
3. Power off. Hold **Vol− + Vol+** and plug the USB cable (connected to PC) → Download Mode.
4. Long-press **Vol+** when prompted → bootloader unlock. The device wipes and reboots.
5. The device reboots unrooted; Knox is now tripped (`Knox warranty void: 0x1` in
   Download Mode). Re-do: skip Setup Wizard as much as possible, re-enable USB debugging
   and OEM unlocking (Developer options returns after tapping Build number again).

## Stage 3 — Download exact firmware (manual)

- Use **SamFw Tool** (Windows GUI) or `samfirm.js`/Samloader.
- Model: **SM-S906B** · CSC must match your region (check `phone-root preflight` CSC output).
- You get a multi-file package: **BL, AP, CP, CSC** (CSC full-wipes again — use only if needed).
- Keep the extracted files; you need `AP_*.tar.md5` next.

## Stage 4 — Patch AP with Magisk (manual, on phone)

1. Install the Magisk app (`Magisk-v27+.apk` from github.com/topjohnwu/Magisk/releases)
   on the phone (adb install or direct download).
2. Copy `AP_*.tar.md5` to the phone storage (`adb push` or MTP).
3. Magisk app → **Install** → **Select and Patch a File** → choose the AP tar → wait.
4. Pull the result: `adb pull /sdcard/Download/magisk_patched-*.tar ./data/`

## Stage 5 — Flash (manual, Odin)

1. Boot Download Mode again.
2. Odin (3.14.4 or newer): load **BL** → BL slot, **AP** → your `magisk_patched-*.tar`
   (NOT the stock AP), **CP** → CP slot, **CSC** → CSC slot (avoid HOME_CSC for a clean flash).
3. Options: Auto Reboot on; do NOT flash anything to USERDATA unless you want a wipe.
4. Start. First boot takes 5–15 minutes — do not touch it.
5. When it boots, complete setup, re-enable USB debugging, install the Magisk app.

## Stage 6 — Verify

```bash
phone-root verify
```

Expect: `su_available PASS`, `magisk PASS` with a version, `knox tripped` (expected),
battery/storage readable. Then check Play Integrity manually (Play Store → Settings →
About → "Device is certified") — if not certified, install PlayIntegrityFix:

```bash
phone-root modules recommend
```

## Stage 7 — Modules

```bash
phone-root modules list
phone-root modules install <module.zip> --yes
phone-root modules disable <id> --yes
phone-root modules remove <id> --yes
```

## Rollback to full stock

1. Download stock firmware for SM-S906B (Stage 3).
2. Odin flash **BL + AP + CP + CSC** (full CSC = clean wipe) with the stock AP.
3. Device returns to 100 % stock; **Knox stays tripped** and bootloader can be re-locked
   via Download Mode (long-press Vol+ flow) — Knox does not recover either way.

## References

- [XDA — Root Galaxy S22 Plus (B/E/N/0), unlock bootloader](https://xdaforums.com/t/guide-to-root-galaxy-s22-plus-b-e-n-0-unlock-bootloader-and-flash-official-firmware-noob-friendly.4404351)
- [awesome-android-root — How to root a Samsung phone](https://github.com/awesome-android-root/awesome-android-root/blob/main/docs/rooting-guides/how-to-root-samsung-phone.md)
- [Magisk — topjohnwu/Magisk](https://github.com/topjohnwu/Magisk)
- [Knox eFuse permanence discussion](https://www.reddit.com/r/androidroot/comments/nsklxu/)
