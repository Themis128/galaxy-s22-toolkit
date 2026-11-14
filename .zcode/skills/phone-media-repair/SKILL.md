---
name: phone-media-repair
description: Detect truncated photos/videos (MP4 moov check, JPEG EOI check) and attempt repair with untrunc or an ffmpeg remux - the Wondershare corrupted-media repair equivalent
version: 1.0.0
author: Galaxy S22+ Toolkit
tags:
  - android
  - media
  - repair
---

# Media Repair Skill

Find truncated recordings/photos and attempt honest repair. Scan works on
a local tree (default: the phone mirror) or on the phone over ADB
(base64-sampled head/tail, capped walk).

## Commands

```bash
phone-media-repair scan                      # verdicts over the phone mirror
phone-media-repair scan --remote             # walk DCIM/Pictures/Movies on the phone
phone-media-repair repair broken.mp4 --reference good.mp4   # untrunc (same device!)
phone-media-repair repair broken.mp4         # ffmpeg remux fallback
```

## Honesty note

ffmpeg remux fixes container-level breakage only. Truncated MP4 streams
need untrunc with a reference file recorded by the SAME device. Originals
are never modified — repairs land in `<name>.fixed.<ext>`.
