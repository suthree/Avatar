#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REQUIRED_FILES = ("task.json", "prd.md", "design.md", "implement.md")
REQUIRED_JSON_FIELDS = ("id", "title", "type", "status", "risk", "created_at", "acceptance")
ALLOWED_STATUSES = {"planning", "in_progress", "implemented", "avatar_verify", "done", "blocked", "cancelled"}


def _trellis_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _task_dir(task_id: str) -> Path:
    return _trellis_root() / "tasks" / task_id


def validate(task_id: str) -> int:
    task_dir = _task_dir(task_id)
    errors = []
    if not task_dir.is_dir():
        errors.append(f"missing task directory: {task_dir}")
    for name in REQUIRED_FILES:
        path = task_dir / name
        if not path.is_file():
            errors.append(f"missing required file: {path}")
        elif path.stat().st_size == 0:
            errors.append(f"empty required file: {path}")

    task_json = task_dir / "task.json"
    data = {}
    if task_json.is_file():
        try:
            data = json.loads(task_json.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"invalid JSON in {task_json}: {exc}")
    for field in REQUIRED_JSON_FIELDS:
        if field not in data:
            errors.append(f"task.json missing field: {field}")
    if data.get("id") and data["id"] != task_id:
        errors.append(f"task.json id {data['id']!r} does not match directory {task_id!r}")
    if data.get("status") and data["status"] not in ALLOWED_STATUSES:
        errors.append(f"task.json status {data['status']!r} is not allowed")
    if "acceptance" in data and not isinstance(data["acceptance"], list):
        errors.append("task.json acceptance must be a list")

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"OK: {task_id}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate Avatar Trellis task structure.")
    sub = parser.add_subparsers(dest="command", required=True)
    validate_parser = sub.add_parser("validate", help="validate a task directory")
    validate_parser.add_argument("task_id")
    args = parser.parse_args(argv)
    if args.command == "validate":
        return validate(args.task_id)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
