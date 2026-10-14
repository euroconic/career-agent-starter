"""Safely publish one file after validation, using a same-directory atomic replace.

The caller must choose exactly one precondition: ``expected_sha256`` for an
existing destination, or ``must_be_absent=True`` for a new destination. The
precondition is checked before staging and again immediately before replacement.
This detects changes during validation, but does not provide a cross-process
compare-and-swap guarantee for changes in the tiny interval after the final
check. It is a single-file operation, not a multi-file transaction.
"""
from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path
from typing import Callable


class PublishConflict(RuntimeError):
    """The destination did not satisfy its expected state."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _check_precondition(destination: Path, expected_sha256: str | None, must_be_absent: bool) -> None:
    if destination.is_symlink():
        raise PublishConflict(f"destination must not be a symbolic link: {destination}")
    if must_be_absent:
        if destination.exists():
            raise PublishConflict(f"destination must be absent: {destination}")
        return
    if expected_sha256 is None:
        raise ValueError("provide expected_sha256 or set must_be_absent=True")
    if not destination.is_file():
        raise PublishConflict(f"expected destination file is missing: {destination}")
    actual = sha256_file(destination)
    if actual.lower() != expected_sha256.lower():
        raise PublishConflict(f"destination changed: expected {expected_sha256}, found {actual}")


def publish_bytes(
    destination: str | Path,
    payload: bytes,
    *,
    validator: Callable[[Path], None],
    expected_sha256: str | None = None,
    must_be_absent: bool = False,
) -> None:
    """Validate staged bytes, then atomically publish them at ``destination``.

    ``validator`` receives the temporary staged path and should raise on any
    invalid content. On validation or precondition failure, the staged file is
    removed and the prior destination bytes are left untouched.
    """
    if (expected_sha256 is None) == (not must_be_absent):
        raise ValueError("choose exactly one of expected_sha256 or must_be_absent=True")
    target = Path(destination)
    if not target.parent.is_dir():
        raise FileNotFoundError(f"destination directory does not exist: {target.parent}")
    _check_precondition(target, expected_sha256, must_be_absent)

    fd, staged_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".stage", dir=target.parent)
    staged = Path(staged_name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        validator(staged)
        _check_precondition(target, expected_sha256, must_be_absent)
        os.replace(staged, target)
    finally:
        try:
            staged.unlink()
        except FileNotFoundError:
            pass
