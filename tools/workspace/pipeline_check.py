#!/usr/bin/env python3
"""Validate the canonical application tracker without scanning the workspace."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

VALID_STAGES = {
    "Evaluating", "Prepared", "Applied", "Screening", "Interview Loop",
    "Final-Offer", "Negotiation", "Closed", "Superseded",
}
REQUIRED_FIELDS = ("Application ID", "Stage", "Last event", "Event source", "Next", "Owner", "Due")
FIELD_RE = re.compile(r"^- ([A-Za-z][A-Za-z ]*):\s*(.*?)\s*$")
HEADING_RE = re.compile(r"^### ([a-z0-9_]+) \| (.+)$")


def parse_records(text: str) -> tuple[list[dict[str, object]], list[str]]:
    records: list[dict[str, object]] = []
    errors: list[str] = []
    area: str | None = None
    current: dict[str, object] | None = None
    fields: dict[str, list[str]] = {}

    def finish() -> None:
        nonlocal current, fields
        if current is None:
            return
        current["fields"] = fields
        records.append(current)
        app_id = str(current["heading_id"])
        for name in REQUIRED_FIELDS:
            count = len(fields.get(name, []))
            if count != 1:
                errors.append(f"{app_id}: expected one {name} field, found {count}")
            elif not fields[name][0].strip():
                errors.append(f"{app_id}: {name} must not be empty; use Unknown or Unassigned when appropriate")
        ids = fields.get("Application ID", [])
        if len(ids) == 1 and ids[0] != app_id:
            errors.append(f"{app_id}: heading ID does not match Application ID field")
        stages = fields.get("Stage", [])
        if len(stages) == 1 and stages[0] not in VALID_STAGES:
            errors.append(f"{app_id}: invalid stage {stages[0]!r}")
        if area == "Active" and stages == ["Closed"]:
            errors.append(f"{app_id}: closed application appears under Active")
        if area == "Closed" and stages and stages != ["Closed"]:
            errors.append(f"{app_id}: non-closed application appears under Closed")
        current = None
        fields = {}

    for line_no, line in enumerate(text.splitlines(), 1):
        if line.startswith("## "):
            finish()
            area = line[3:].strip()
            continue
        match = HEADING_RE.match(line)
        if match:
            finish()
            if area not in {"Active", "Closed"}:
                errors.append(f"line {line_no}: application record outside Active or Closed")
            current = {"heading_id": match.group(1), "heading": match.group(2), "area": area, "line": line_no}
            fields = {}
            continue
        if current is not None:
            match = FIELD_RE.match(line)
            if match and match.group(1) in REQUIRED_FIELDS:
                fields.setdefault(match.group(1), []).append(match.group(2))
    finish()

    seen: set[str] = set()
    for record in records:
        app_id = str(record["heading_id"])
        if app_id in seen:
            errors.append(f"duplicate Application ID: {app_id}")
        seen.add(app_id)
    if not records:
        # A new workspace has no applications. Only the explicit empty skeleton
        # is valid, so malformed application content cannot pass as an empty list.
        allowed = {"", "# Application pipeline", "No applications recorded yet.", "## Active", "## Closed"}
        if any(line.strip() not in allowed for line in text.splitlines()) or not all(
            heading in text.splitlines() for heading in ("## Active", "## Closed")
        ):
            errors.append("no valid application records or empty pipeline skeleton found")
    return records, errors


def check_event_sources(records: list[dict[str, object]], root: Path) -> list[str]:
    """Check only the explicitly declared Event source fields for local paths."""
    errors: list[str] = []
    for record in records:
        fields = record["fields"]
        assert isinstance(fields, dict)
        sources = fields.get("Event source", [])
        if len(sources) != 1:
            continue
        refs = re.findall(r"`([^`]+)`", sources[0])
        if not refs:
            errors.append(f"{record['heading_id']}: Event source must name a local file in backticks")
        for ref in refs:
            if not (root / ref).is_file():
                errors.append(f"{record['heading_id']}: Event source file does not exist: {ref}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pipeline", nargs="?", default="memory/pipeline.md", help="pipeline Markdown file")
    parser.add_argument("--check-files", action="store_true", help="verify only declared Event source paths")
    args = parser.parse_args(argv)
    path = Path(args.pipeline)
    text = path.read_text(encoding="utf-8")
    records, errors = parse_records(text)
    if args.check_files:
        errors.extend(check_event_sources(records, Path.cwd()))
    if errors:
        print("\n".join(f"ERROR: {error}" for error in errors), file=sys.stderr)
        return 1
    print(f"Pipeline valid: {len(records)} records, {sum(1 for r in records if r['area'] == 'Active')} active, {sum(1 for r in records if r['area'] == 'Closed')} closed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
