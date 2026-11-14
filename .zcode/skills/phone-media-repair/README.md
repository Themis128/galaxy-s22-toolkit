# phone-media-repair

Truncated-media triage + repair (Wondershare corrupted-media repair
equivalent). `scan` groups media files into intact / truncated / unknown
(MP4: ftyp-without-moov; JPEG: SOI-without-EOI); `repair` prefers untrunc
with a `--reference` file from the same device, falls back to an ffmpeg
`-c copy` remux, and always writes a NEW `.fixed.` file.

Implementation: `tools/media_repair.py` (+ `tools/test_media_repair.py`).
