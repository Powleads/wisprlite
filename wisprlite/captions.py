"""Pure SRT / WebVTT formatting from segment dicts.

A segment dict is {"start": float, "end": float, "text": str, "words": [...]}.
No dependencies, no I/O — trivially testable.
"""

from __future__ import annotations


def format_timestamp(seconds: float, vtt: bool = False) -> str:
    if seconds is None or seconds < 0:
        seconds = 0.0
    ms_total = int(round(seconds * 1000))
    h, ms_total = divmod(ms_total, 3_600_000)
    m, ms_total = divmod(ms_total, 60_000)
    s, ms = divmod(ms_total, 1000)
    sep = "." if vtt else ","
    return f"{h:02d}:{m:02d}:{s:02d}{sep}{ms:03d}"


def to_srt(segments) -> str:
    lines = []
    for i, seg in enumerate(segments, 1):
        lines.append(str(i))
        lines.append(f"{format_timestamp(seg['start'])} --> {format_timestamp(seg['end'])}")
        lines.append((seg.get("text") or "").strip())
        lines.append("")
    return ("\n".join(lines).strip() + "\n") if lines else ""


def to_vtt(segments) -> str:
    out = ["WEBVTT", ""]
    for seg in segments:
        out.append(f"{format_timestamp(seg['start'], vtt=True)} --> {format_timestamp(seg['end'], vtt=True)}")
        out.append((seg.get("text") or "").strip())
        out.append("")
    return "\n".join(out).strip() + "\n"
