"""Read-only, byte-bounded context preview for explicit Git file candidates.

This does not decide which repository instructions are authoritative, and the
byte count is not a tokenizer or a model context-window estimate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
import os
import subprocess
from dataclasses import dataclass


class TaskError(ValueError):
    """Invalid local task description."""


class GitError(ValueError):
    """Git metadata cannot be read."""


def _git(repo: Path, *args: str) -> bytes:
    # Fixed Git arguments only; inherited GIT_DIR/WORK_TREE cannot redirect reads.
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    try:
        result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True,
                                timeout=10, check=False, env=env)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GitError("Git is unavailable or timed out") from exc
    if result.returncode:
        raise GitError("Git metadata is unavailable; use an existing checkout")
    return result.stdout


@dataclass(frozen=True)
class Task:
    identifier: str
    branch: str
    scope: tuple[str, ...]
    sources: tuple[str, ...]
    checks: tuple[str, ...]
    must_do: tuple[str, ...]
    must_not: tuple[str, ...]
    acceptance: tuple[str, ...]
    stop_rule: str


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise TaskError(f"Duplicate task field: {key}")
        result[key] = value
    return result


def parse_task(path: Path) -> Task:
    try:
        with path.open("rb") as stream:
            raw = stream.read(65_537)
        if len(raw) > 65_536:
            raise TaskError("Task exceeds 64 KiB")
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_pairs)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise TaskError("Task must be readable UTF-8 JSON") from exc
    if not isinstance(data, dict) or set(data) != set(Task.__dataclass_fields__):
        raise TaskError("Task fields do not match the supplied example")
    for key in ("identifier", "branch", "stop_rule"):
        if not isinstance(data[key], str) or not data[key].strip():
            raise TaskError(f"Task {key} must be nonempty text")
    for key in ("scope", "sources", "checks", "must_do", "must_not", "acceptance"):
        if not isinstance(data[key], list) or not data[key] or any(not isinstance(item, str) or not item.strip() for item in data[key]):
            raise TaskError(f"Task {key} must contain nonempty strings")
        data[key] = tuple(data[key])
    return Task(**data)


class ContextError(ValueError):
    """The requested context cannot be selected safely."""


_MAX_FILE_BYTES = 65_536
_MAX_CANDIDATES = 64
_WORDS = re.compile(r"[\w]+", re.UNICODE)


def _encoded_size(value: dict) -> int:
    # Count the exact compact CLI representation, including its final newline.
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")) + 1


def _final_size(value: dict) -> int:
    value["used_bytes"] = 0
    while value["used_bytes"] != _encoded_size(value):
        value["used_bytes"] = _encoded_size(value)
    return value["used_bytes"]


def _tracked(repo: Path) -> set[str]:
    try:
        root = _git(repo, "rev-parse", "--show-toplevel").decode("utf-8").strip()
        if Path(root).resolve() != repo.resolve():
            raise ContextError("repo must be the Git root")
        result = _git(repo, "ls-files", "--cached", "-z")
        return {name.decode("utf-8") for name in result.split(b"\0") if name}
    except (OSError, GitError, UnicodeError) as exc:
        raise ContextError(f"Cannot inspect tracked files: {exc}") from exc


def _read_candidate(repo: Path, name: str, tracked: set[str]) -> tuple[str, str]:
    posix = PurePosixPath(name)
    if (not name or "\\" in name or posix.is_absolute() or
            any(part in ("", ".", "..", ".git") for part in name.split("/")) or name not in tracked):
        raise ContextError(f"Invalid or untracked candidate: {name!r}")
    path = repo
    for part in posix.parts:
        path = path / part
        if path.is_symlink():
            raise ContextError(f"Symlink candidate: {name!r}")
    if not path.is_file() or not path.resolve().is_relative_to(repo.resolve()):
        raise ContextError(f"Not a regular in-repo file: {name!r}")
    try:
        with path.open("rb") as stream:
            raw = stream.read(_MAX_FILE_BYTES + 1)
        if len(raw) > _MAX_FILE_BYTES:
            raise ContextError(f"Candidate exceeds 64 KiB: {name!r}")
        if b"\0" in raw:
            raise ContextError(f"Binary candidate: {name!r}")
        return raw.decode("utf-8"), hashlib.sha256(raw).hexdigest()
    except (OSError, UnicodeError) as exc:
        raise ContextError(f"Cannot read UTF-8 candidate {name!r}: {exc}") from exc


def build_pack(task: Task, repo: Path, query: str, candidates: list[str], budget_bytes: int) -> dict:
    if type(budget_bytes) is not int or not 256 <= budget_bytes <= 1_048_576:
        raise ContextError("budget_bytes must be between 256 and 1048576")
    if not isinstance(query, str) or not query.strip() or len(query) > 256:
        raise ContextError("query must contain 1-256 characters")
    if len(candidates) > _MAX_CANDIDATES or len(candidates) != len(set(candidates)):
        raise ContextError("At most 64 distinct candidate paths are allowed")
    mandatory = {"task_id": task.identifier, "branch": task.branch,
                 "scope": list(task.scope), "sources": list(task.sources),
                 "checks": list(task.checks), "must_do": list(task.must_do),
                 "must_not": list(task.must_not), "acceptance": list(task.acceptance),
                 "stop_rule": task.stop_rule}
    result = {"schema_version": 1, "mandatory": mandatory, "optional": [],
              "omitted": [], "budget_bytes": budget_bytes}
    if _final_size(result) > budget_bytes:
        raise ContextError("Mandatory context exceeds byte budget; no clauses were shortened")

    tracked = _tracked(repo)
    try:
        actual_branch = _git(repo, "symbolic-ref", "--short", "HEAD").decode("utf-8").strip()
    except (GitError, UnicodeError) as exc:
        raise ContextError("Use a named feature branch") from exc
    if actual_branch != task.branch or not actual_branch.startswith("feature/"):
        raise ContextError("Checkout must match the task's feature branch")
    words = set(_WORDS.findall(query.casefold()))
    ranked = []
    for name in candidates:
        content, digest = _read_candidate(repo, name, tracked)
        lines = content.splitlines(keepends=True)
        matched = [i for i, line in enumerate(lines) if words & set(_WORDS.findall(line.casefold()))]
        score = 4 * len(words & set(_WORDS.findall(name.casefold()))) + len(matched)
        if not score:
            result["omitted"].append(name)
            continue
        indexes = sorted({j for i in matched[:8] for j in range(max(i - 1, 0), min(i + 2, len(lines)))})
        if not indexes:
            indexes = list(range(min(8, len(lines))))
        excerpt = "".join(f"{i + 1}: {lines[i]}" for i in indexes)
        ranked.append((-score, name, {"path": name, "sha256": digest, "excerpt": excerpt}))
    for _, name, snippet in sorted(ranked):
        result["optional"].append(snippet)
        if _final_size(result) > budget_bytes:
            result["optional"].pop()
            result["omitted"].append(name)
    result["omitted"].sort()
    if _final_size(result) > budget_bytes:
        # Include output metadata in the cap; mandatory content is never truncated.
        while result["optional"] and result["used_bytes"] > budget_bytes:
            result["omitted"].append(result["optional"].pop()["path"])
            result["omitted"].sort()
            _final_size(result)
        if result["used_bytes"] > budget_bytes:
            raise ContextError("Mandatory context and metadata exceed byte budget")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Preview a bounded offline context pack")
    parser.add_argument("task", type=Path)
    parser.add_argument("repo", type=Path)
    parser.add_argument("query")
    parser.add_argument("--file", action="append", default=[])
    parser.add_argument("--budget-bytes", type=int, required=True)
    args = parser.parse_args()
    try:
        output = build_pack(parse_task(args.task), args.repo, args.query,
                            args.file, args.budget_bytes)
    except (TaskError, ContextError) as exc:
        print(f"INVALID CONTEXT: {exc}", file=sys.stderr)
        return 2
    # Bytes written are identical to those counted, including on Windows.
    sys.stdout.buffer.write((json.dumps(output, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
