"""Filesystem path confinement helpers.

SAST hardening: any file path assembled from config values, template
substitution, or caller-provided strings is resolved and verified to stay
inside its intended root before it is used for reads or writes.
"""

from __future__ import annotations

from pathlib import Path


class PathEscapeError(ValueError):
    """Raised when a candidate path resolves outside its allowed root."""


def confined_path(root: str | Path, candidate: str | Path) -> Path:
    """Resolve ``candidate`` and require it to land inside ``root``.

    ``..`` segments and symlinked ancestors are normalized by the resolve
    step, so a candidate can never name anything outside ``root`` — the
    result is either ``root`` itself or a path beneath it.

    Raises:
        PathEscapeError: if the resolved candidate escapes the root.
    """
    root_resolved = Path(root).resolve()
    candidate_resolved = Path(candidate).resolve()

    if candidate_resolved == root_resolved or root_resolved in candidate_resolved.parents:
        return candidate_resolved

    raise PathEscapeError(
        f"Path {str(candidate)!r} resolves outside allowed root {str(root_resolved)!r}"
    )
